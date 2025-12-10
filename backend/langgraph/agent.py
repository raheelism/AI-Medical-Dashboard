from typing import TypedDict, Optional, List, Any
import os
import ssl
import httpx
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from backend.db.connection import get_db_connection
from backend.api.websocket import manager
import json
import asyncio

# --- State Definition ---
class AgentState(TypedDict):
    messages: List[Any]
    intent: Optional[str]
    sql_query: Optional[str]
    execution_result: Optional[str]
    error: Optional[str]
    table_changed: Optional[str]
    row_id: Optional[int]
    update_data: Optional[dict]

# --- LLM Setup ---
# Using the key provided in the chat. In a real scenario, use os.getenv("GROQ_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable is not set")

# Create custom HTTP client with SSL verification disabled (for corporate networks)
http_client = httpx.Client(verify=False)

llm = ChatGroq(
    temperature=0,
    model_name="llama-3.3-70b-versatile", # Using a powerful model for SQL generation
    api_key=GROQ_API_KEY,
    http_client=http_client
)

# --- Nodes ---

def classify_intent(state: AgentState):
    """Determines if the user wants to QUERY or UPDATE data."""
    messages = state["messages"]
    last_message = messages[-1].content
    
    prompt = f"""
    You are an intent classifier for a medical database system.
    The available tables are: patients, visits, prescriptions, billing.
    
    User Input: "{last_message}"
    
    Classify the intent as one of:
    - UPDATE (if the user wants to modify, add, or delete data)
    - QUERY (if the user wants to view or search data)
    - UNKNOWN (if the request is unrelated)
    
    Return ONLY the classification word.
    """
    response = llm.invoke([SystemMessage(content=prompt)])
    intent = response.content.strip().upper()
    return {"intent": intent}

def generate_sql(state: AgentState):
    """Generates SQL for the request."""
    intent = state["intent"]
    messages = state["messages"]
    last_message = messages[-1].content
    
    if intent == "UNKNOWN":
        return {"error": "I didn't understand that request."}
        
    prompt = f"""
    You are a SQL expert for a SQLite database.
    Schema:
    - patients (id INTEGER PRIMARY KEY AUTOINCREMENT, name, age, gender, address, phone, notes)
    - visits (id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id, date, diagnosis, doctor)
    - prescriptions (id INTEGER PRIMARY KEY AUTOINCREMENT, visit_id, medication, dosage)
    - billing (id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id, amount, status, date)
    
    Generate a valid SQLite query for: "{last_message}"
    
    Rules:
    - Return ONLY the SQL query. No markdown, no explanation.
    - For INSERT statements, NEVER include the 'id' column - it is auto-generated.
    - If it's an UPDATE/INSERT/DELETE, make sure to reference existing columns.
    - For updates, try to identify the record uniquely (e.g., by name).
    """
    
    response = llm.invoke([SystemMessage(content=prompt)])
    sql_query = response.content.strip()
    # Cleanup possible markdown
    sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
    
    return {"sql_query": sql_query}

def validate_operation(state: AgentState):
    """Checks if the operation is safe/valid (e.g., patient exists)."""
    sql_query = state.get("sql_query")
    if not sql_query:
        return {} # Pass through if previous step failed
        
    # Basic validation: Prevent destructive Drop/Delete without explicit check (optional)
    if "DROP" in sql_query.upper():
         return {"error": "DROP operations are not allowed."}

    return {}

def execute_sql(state: AgentState):
    """Executes the SQL on the database."""
    sql_query = state.get("sql_query")
    if not sql_query:
        return {}

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if it's a read or write
        is_write = any(op in sql_query.upper() for op in ["UPDATE", "INSERT", "DELETE"])
        
        cursor.execute(sql_query)
        
        execution_result = ""
        table_changed = None
        row_id = None
        update_data = {}
        
        if is_write:
            conn.commit()
            row_count = cursor.rowcount
            if row_count == 0:
                 execution_result = "No records were updated. Please check if the patient exists."
            else:
                 execution_result = f"Success. {row_count} row(s) affected."
            
            # For the purpose of the demo, we need to know WHAT changed to broadcast.
            # This is tricky with raw SQL. We will do a best-effort parsing or heuristic.
            # Simpler: If "UPDATE patients", we say table "patients" changed.
            if "patients" in sql_query.lower():
                table_changed = "patients"
            elif "visits" in sql_query.lower():
                table_changed = "visits"
            elif "prescriptions" in sql_query.lower():
                table_changed = "prescriptions"
            elif "billing" in sql_query.lower():
                table_changed = "billing"
                
            # Log to audit_log
            conn.execute("INSERT INTO audit_log (operation, new_value, user) VALUES (?, ?, ?)", 
                         ("SQL Execution", sql_query, "chatbot"))
            conn.commit()
            
        else:
            rows = cursor.fetchall()
            if rows:
                execution_result = json.dumps([dict(row) for row in rows], indent=2)
            else:
                execution_result = "No results found."
                
        conn.close()
        return {
            "execution_result": execution_result, 
            "table_changed": table_changed
        }
        
    except Exception as e:
        conn.close()
        return {"error": str(e)}

async def emit_event(state: AgentState):
    """Emits a WebSocket event if data changed."""
    table = state.get("table_changed")
    if table:
        message = {
            "table": table,
            "action": "refresh", # Simple 'refresh' command tells frontend to reload table
            "message": "Data updated via chatbot"
        }
        await manager.broadcast(message)
    return {}

def generate_response(state: AgentState):
    """Generates the final natural language response."""
    error = state.get("error")
    result = state.get("execution_result")
    
    if error:
        return {"messages": [HumanMessage(content=f"Error: {error}")]}
        
    if result:
        # If it's a large JSON, summarize it
        if len(result) > 500:
            content = f"Operation successful. Result: {result[:500]}..."
        else:
            content = f"Here is the result: {result}"
        return {"messages": [HumanMessage(content=content)]}
    
    return {"messages": [HumanMessage(content="Done.")]}

# --- Graph Construction ---
workflow = StateGraph(AgentState)

workflow.add_node("classify", classify_intent)
workflow.add_node("generate_sql", generate_sql)
workflow.add_node("execute_sql", execute_sql)
workflow.add_node("emit_event", emit_event)
workflow.add_node("respond", generate_response)

workflow.set_entry_point("classify")

workflow.add_conditional_edges(
    "classify",
    lambda x: "generate_sql" if x["intent"] in ["UPDATE", "QUERY"] else "respond"
)

workflow.add_edge("generate_sql", "execute_sql")
workflow.add_edge("execute_sql", "emit_event")
workflow.add_edge("emit_event", "respond")
workflow.add_edge("respond", END)

app_graph = workflow.compile()
