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
    chat_history: List[Any]  # Full conversation history for context
    intent: Optional[str]
    sql_query: Optional[str]
    execution_result: Optional[str]
    error: Optional[str]
    table_changed: Optional[str]
    row_id: Optional[int]
    update_data: Optional[dict]
    needs_clarification: Optional[bool]
    clarification_question: Optional[str]
    context_data: Optional[str]  # For storing relevant DB context

# --- LLM Setup ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable is not set")

# Create custom HTTP client with SSL verification disabled (for corporate networks)
http_client = httpx.Client(verify=False)

llm = ChatGroq(
    temperature=0.1,  # Slight temperature for more natural responses
    model_name="meta-llama/llama-4-scout-17b-16e-instruct",  # Using latest Llama 4 Scout model
    api_key=GROQ_API_KEY,
    http_client=http_client
)

# --- Helper Functions ---
def get_current_data_context():
    """Fetches current database state for context."""
    conn = get_db_connection()
    try:
        patients = conn.execute("SELECT id, name FROM patients").fetchall()
        patient_list = [{"id": p["id"], "name": p["name"]} for p in patients]
        return json.dumps({"patients": patient_list}, indent=2)
    except:
        return "{}"
    finally:
        conn.close()

def find_patient_by_name(name: str):
    """Searches for patients matching a name."""
    conn = get_db_connection()
    try:
        patients = conn.execute(
            "SELECT * FROM patients WHERE LOWER(name) LIKE LOWER(?)", 
            (f"%{name}%",)
        ).fetchall()
        return [dict(p) for p in patients]
    except:
        return []
    finally:
        conn.close()

# --- Nodes ---

def format_chat_history(chat_history: List[Any], max_turns: int = 10) -> str:
    """Formats chat history for context."""
    if not chat_history:
        return "No previous conversation."
    
    # Take last N turns
    recent_history = chat_history[-(max_turns * 2):]
    formatted = []
    for msg in recent_history:
        role = "User" if isinstance(msg, HumanMessage) or getattr(msg, 'type', '') == 'human' else "Assistant"
        content = msg.content if hasattr(msg, 'content') else str(msg)
        formatted.append(f"{role}: {content}")
    
    return "\n".join(formatted)


def analyze_request(state: AgentState):
    """Intelligently analyzes the user request and determines the best course of action."""
    messages = state["messages"]
    chat_history = state.get("chat_history", [])
    last_message = messages[-1].content
    
    # Get current database context
    context = get_current_data_context()
    
    # Format conversation history
    history_str = format_chat_history(chat_history)
    
    prompt = f"""You are an intelligent medical database assistant. Analyze the user's request carefully.

PREVIOUS CONVERSATION:
{history_str}

CURRENT DATABASE STATE:
{context}

USER REQUEST: "{last_message}"

Analyze and respond with a JSON object containing:
{{
    "intent": "UPDATE" | "QUERY" | "CHAT",
    "confidence": 0.0 to 1.0,
    "resolved_context": {{
        "table": "patients|visits|prescriptions|billing",
        "action": "select|insert|update|delete",
        "inferred_from_history": "what you inferred from conversation history"
    }},
    "reasoning": "brief explanation"
}}

CRITICAL RULES - BE SMART ABOUT CONTEXT:
1. ALWAYS use conversation history to resolve ambiguous references like "it", "that", "the same", "this one", etc.
2. If user just discussed a specific record (e.g., a pending bill), and then says "change status to paid", ASSUME they mean that record
3. If the last response showed query results, and user wants to modify something, use those results as context
4. For simple queries like "show pending bills" - just execute it, don't ask for clarification
5. ONLY set intent to require clarification if you truly cannot determine what the user wants even with history
6. Be AGGRESSIVE about inferring intent - users don't like being asked obvious questions
7. "pending bills" means billing table with status='Pending'
8. If user refers to something from the previous message, USE THAT CONTEXT

Examples of GOOD inference:
- History shows "pending bill for patient 2", user says "mark it as paid" -> UPDATE billing SET status='Paid' WHERE patient_id=2 AND status='Pending'
- History shows "1 record found with ID 2", user says "update that" -> refers to ID 2
- User says "change the status to paid" after seeing pending bills -> update those pending bills

NEVER ask for clarification if:
- The answer is obvious from conversation history
- It's a simple query (show, list, get, find)
- User is referring to something just discussed

Return ONLY the JSON object, no other text."""

    response = llm.invoke([SystemMessage(content=prompt)])
    
    try:
        # Parse the JSON response
        response_text = response.content.strip()
        # Clean up potential markdown
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
        response_text = response_text.strip()
        
        analysis = json.loads(response_text)
        
        intent = analysis.get("intent", "QUERY")
        confidence = analysis.get("confidence", 0.8)  # Default higher confidence
        
        # Handle chat/greeting
        if intent == "CHAT":
            return {
                "intent": "CHAT",
                "needs_clarification": False,
                "context_data": context
            }
        
        # For UPDATE and QUERY, proceed without clarification - let SQL generation handle it
        return {
            "intent": intent,
            "needs_clarification": False,
            "context_data": context,
            "resolved_context": analysis.get("resolved_context", {})
        }
        
    except json.JSONDecodeError:
        # Fallback - just proceed with the request
        intent = "QUERY" if any(w in last_message.lower() for w in ["show", "list", "get", "find", "search", "pending"]) else "UPDATE"
        return {"intent": intent, "needs_clarification": False, "context_data": context}


def generate_smart_sql(state: AgentState):
    """Generates SQL with intelligent context awareness."""
    intent = state["intent"]
    messages = state["messages"]
    chat_history = state.get("chat_history", [])
    last_message = messages[-1].content
    context = state.get("context_data", "{}")
    resolved_context = state.get("resolved_context", {})
    
    if intent in ["CHAT"]:
        return {}
    
    # Format recent conversation for context - include more turns for better context
    history_str = format_chat_history(chat_history, max_turns=10)
        
    prompt = f"""You are an expert SQL generator for a medical SQLite database. You MUST use conversation history to understand context.

DATABASE SCHEMA:
- patients (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, age INTEGER, gender TEXT, address TEXT, phone TEXT, notes TEXT)
- visits (id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id INTEGER, date TEXT, diagnosis TEXT, doctor TEXT)
- prescriptions (id INTEGER PRIMARY KEY AUTOINCREMENT, visit_id INTEGER, medication TEXT, dosage TEXT)
- billing (id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id INTEGER, amount REAL, status TEXT, date TEXT)
  - status values: 'Pending', 'Paid', 'Overdue'

CONVERSATION HISTORY (CRITICAL - use this to understand what the user is referring to):
{history_str}

CURRENT DATA CONTEXT:
{context}

USER REQUEST: "{last_message}"

CRITICAL CONTEXT RULES:
1. If user says "change status to Paid" after discussing pending bills, update ALL pending bills or the specific one shown
2. If user says "it", "that", "this one", "the same" - refer to the LAST discussed record from conversation history
3. If history shows a query result with specific IDs, and user wants to modify "it" - use those IDs
4. "pending bills" = SELECT * FROM billing WHERE status = 'Pending'
5. "mark as paid" or "change to paid" = UPDATE billing SET status = 'Paid' WHERE ...
6. When updating based on previous context, look for IDs, patient names, or conditions from the last query

EXAMPLES:
- History: "showed billing id=2 with status Pending", User: "change it to paid" -> UPDATE billing SET status = 'Paid' WHERE id = 2
- History: "found 1 pending bill", User: "mark as paid" -> UPDATE billing SET status = 'Paid' WHERE status = 'Pending'
- User: "show pending bills" -> SELECT * FROM billing WHERE status = 'Pending'

SQL RULES:
1. Return ONLY the SQL query - no markdown, no explanation, no extra text
2. For INSERT: NEVER include 'id' column (auto-generated)
3. For UPDATE/DELETE: Always use WHERE clause
4. Use date('now') for today's date

Generate the SQL query:"""

    response = llm.invoke([SystemMessage(content=prompt)])
    sql_query = response.content.strip()
    
    # Cleanup possible markdown
    sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
    
    # Remove any explanatory text that might have slipped through
    if "\n" in sql_query:
        # Take the first line that looks like SQL
        for line in sql_query.split("\n"):
            line = line.strip()
            if line.upper().startswith(("SELECT", "INSERT", "UPDATE", "DELETE")):
                sql_query = line
                break
    
    return {"sql_query": sql_query}


def validate_operation(state: AgentState):
    """Validates the SQL operation for safety and correctness."""
    sql_query = state.get("sql_query")
    if not sql_query:
        return {}
        
    sql_upper = sql_query.upper()
    
    # Block dangerous operations
    if "DROP" in sql_upper:
        return {"error": "DROP operations are not allowed for safety reasons."}
    
    if "TRUNCATE" in sql_upper:
        return {"error": "TRUNCATE operations are not allowed for safety reasons."}
    
    # Warn about DELETE without WHERE
    if "DELETE" in sql_upper and "WHERE" not in sql_upper:
        return {"error": "DELETE without WHERE clause is not allowed. Please specify which records to delete."}
    
    # Warn about UPDATE without WHERE
    if "UPDATE" in sql_upper and "WHERE" not in sql_upper:
        return {"error": "UPDATE without WHERE clause would affect all records. Please specify which records to update."}

    return {}


def execute_sql(state: AgentState):
    """Executes the SQL on the database."""
    sql_query = state.get("sql_query")
    if not sql_query:
        return {}

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        is_write = any(op in sql_query.upper() for op in ["UPDATE", "INSERT", "DELETE"])
        
        cursor.execute(sql_query)
        
        execution_result = ""
        table_changed = None
        
        if is_write:
            conn.commit()
            row_count = cursor.rowcount
            
            if row_count == 0:
                execution_result = "No records were affected. The specified record may not exist."
            else:
                # Get more context about what was done
                if "INSERT" in sql_query.upper():
                    last_id = cursor.lastrowid
                    execution_result = f"Successfully created new record (ID: {last_id})."
                elif "UPDATE" in sql_query.upper():
                    execution_result = f"Successfully updated {row_count} record(s)."
                elif "DELETE" in sql_query.upper():
                    execution_result = f"Successfully deleted {row_count} record(s)."
            
            # Determine which table changed
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
                execution_result = "No matching records found."
                
        conn.close()
        return {
            "execution_result": execution_result, 
            "table_changed": table_changed
        }
        
    except Exception as e:
        conn.close()
        error_msg = str(e)
        # Provide more helpful error messages
        if "UNIQUE constraint" in error_msg:
            return {"error": "A record with this information already exists. Please use different values or update the existing record."}
        elif "FOREIGN KEY constraint" in error_msg:
            return {"error": "Cannot complete this operation because it references a record that doesn't exist."}
        elif "no such column" in error_msg:
            return {"error": f"Invalid column reference in the query. Please check your field names."}
        return {"error": error_msg}


async def emit_event(state: AgentState):
    """Emits a WebSocket event if data changed."""
    table = state.get("table_changed")
    if table:
        message = {
            "table": table,
            "action": "refresh",
            "message": "Data updated via chatbot"
        }
        await manager.broadcast(message)
    return {}


def generate_response(state: AgentState):
    """Generates intelligent, context-aware responses with rich formatting."""
    messages = state["messages"]
    last_message = messages[-1].content
    error = state.get("error")
    result = state.get("execution_result")
    needs_clarification = state.get("needs_clarification", False)
    clarification_question = state.get("clarification_question", "")
    intent = state.get("intent", "")
    sql_query = state.get("sql_query", "")
    
    # Handle clarification requests
    if needs_clarification:
        response_obj = {
            "type": "clarification",
            "message": clarification_question
        }
        return {"messages": [HumanMessage(content=json.dumps(response_obj))]}
    
    # Handle chat/greeting
    if intent == "CHAT":
        prompt = f"""You are a friendly medical database assistant. Respond naturally to this message:
"{last_message}"

Keep the response brief and helpful. Mention that you can help with:
- Viewing patient records, visits, prescriptions, and billing
- Adding new patients or records
- Updating existing information
- Searching for specific data

Respond conversationally:"""
        
        response = llm.invoke([SystemMessage(content=prompt)])
        response_obj = {
            "type": "text",
            "message": response.content.strip()
        }
        return {"messages": [HumanMessage(content=json.dumps(response_obj))]}
    
    # Handle errors with helpful suggestions
    if error:
        response_obj = {
            "type": "error",
            "message": error,
            "suggestion": "Please try rephrasing your request or provide more specific details."
        }
        return {"messages": [HumanMessage(content=json.dumps(response_obj))]}
    
    # Handle successful operations with rich data
    if result:
        try:
            # Try to parse as JSON (for query results)
            data = json.loads(result)
            if isinstance(data, list) and len(data) > 0:
                # Determine the table type from the data structure
                table_type = "data"
                if "diagnosis" in data[0]:
                    table_type = "visits"
                elif "medication" in data[0]:
                    table_type = "prescriptions"
                elif "amount" in data[0]:
                    table_type = "billing"
                elif "name" in data[0] and "age" in data[0]:
                    table_type = "patients"
                elif "operation" in data[0]:
                    table_type = "audit"
                
                # Generate a natural summary
                prompt = f"""Summarize this data briefly in 1 sentence:
Data: {json.dumps(data[:3])}
Count: {len(data)} records"""
                
                summary_response = llm.invoke([SystemMessage(content=prompt)])
                
                response_obj = {
                    "type": "table",
                    "table_type": table_type,
                    "message": summary_response.content.strip(),
                    "data": data,
                    "count": len(data)
                }
                return {"messages": [HumanMessage(content=json.dumps(response_obj))]}
        except json.JSONDecodeError:
            pass
        
        # Handle write operations (INSERT, UPDATE, DELETE)
        if "Successfully" in result or "created" in result.lower() or "updated" in result.lower() or "deleted" in result.lower():
            # Determine action type
            action_type = "created"
            if "updated" in result.lower():
                action_type = "updated"
            elif "deleted" in result.lower():
                action_type = "deleted"
            
            response_obj = {
                "type": "success",
                "action": action_type,
                "message": result
            }
            return {"messages": [HumanMessage(content=json.dumps(response_obj))]}
        
        # Default text response
        response_obj = {
            "type": "text",
            "message": result
        }
        return {"messages": [HumanMessage(content=json.dumps(response_obj))]}
    
    response_obj = {
        "type": "text",
        "message": "I've completed your request. Is there anything else you'd like me to help with?"
    }
    return {"messages": [HumanMessage(content=json.dumps(response_obj))]}


# --- Graph Construction ---
workflow = StateGraph(AgentState)

workflow.add_node("analyze", analyze_request)
workflow.add_node("generate_sql", generate_smart_sql)
workflow.add_node("validate", validate_operation)
workflow.add_node("execute_sql", execute_sql)
workflow.add_node("emit_event", emit_event)
workflow.add_node("respond", generate_response)

workflow.set_entry_point("analyze")

def route_after_analysis(state: AgentState):
    """Routes based on analysis results."""
    if state.get("needs_clarification"):
        return "respond"
    if state.get("intent") == "CHAT":
        return "respond"
    return "generate_sql"

workflow.add_conditional_edges("analyze", route_after_analysis)
workflow.add_edge("generate_sql", "validate")

def route_after_validation(state: AgentState):
    """Routes based on validation results."""
    if state.get("error"):
        return "respond"
    return "execute_sql"

workflow.add_conditional_edges("validate", route_after_validation)
workflow.add_edge("execute_sql", "emit_event")
workflow.add_edge("emit_event", "respond")
workflow.add_edge("respond", END)

app_graph = workflow.compile()
