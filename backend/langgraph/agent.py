from typing import TypedDict, Optional, List, Any
import os
import ssl
import httpx
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage
from backend.db.connection import get_db_connection
from backend.api.websocket import manager
import json
import asyncio
from groq import Groq

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

# Initialize native Groq client for Compound model support with custom HTTP client
groq_client = Groq(api_key=GROQ_API_KEY, http_client=http_client)

# Using Groq Compound model - integrates GPT-OSS 120B and Llama 4 with web search & tools
GROQ_MODEL = "compound-beta"  # Options: "compound-beta", "compound-beta-mini"


class GroqLLMWrapper:
    """Wrapper to make native Groq client compatible with LangChain-style invoke."""
    
    def __init__(self, client: Groq, model: str):
        self.client = client
        self.model = model
    
    def invoke(self, messages: List[Any]) -> Any:
        """Invoke the Groq model with messages."""
        # Convert LangChain messages to Groq format
        groq_messages = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                groq_messages.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                groq_messages.append({"role": "user", "content": msg.content})
            elif hasattr(msg, 'content'):
                # Generic message with content
                role = getattr(msg, 'type', 'user')
                if role == 'human':
                    role = 'user'
                elif role == 'ai':
                    role = 'assistant'
                groq_messages.append({"role": role, "content": msg.content})
        
        # Groq Compound model requires the last message to be 'user' role
        # If we only have system messages, convert the last one to user role
        if groq_messages and groq_messages[-1]["role"] == "system":
            # Move system content to a user message
            system_content = groq_messages[-1]["content"]
            groq_messages[-1] = {"role": "user", "content": system_content}
        
        # Call Groq API
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=groq_messages,
            temperature=0.1
        )
        
        # Return a response object with .content attribute
        class Response:
            def __init__(self, content):
                self.content = self._clean_compound_response(content)
            
            def _clean_compound_response(self, content: str) -> str:
                """Remove Compound model's reasoning preambles from response."""
                import re
                if not content:
                    return content
                
                cleaned = content.strip()
                
                # Remove markdown bold headers like **Reasoning...** or **Summary**
                cleaned = re.sub(r'\*\*[^*]+\*\*\s*', '', cleaned)
                
                # Remove lines starting with "- " that look like reasoning bullets
                lines = cleaned.split('\n')
                result_lines = []
                for line in lines:
                    stripped = line.strip()
                    # Skip bullet points that are reasoning/meta-commentary
                    if stripped.startswith('- ') and any(word in stripped.lower() for word in [
                        'combining', 'therefore', 'this means', 'based on', 'from the', 
                        'the data', 'the json', 'the result', 'the above', 'the record',
                        'key details', 'summary', 'yields', 'earlier work', 'reasoning'
                    ]):
                        continue
                    result_lines.append(line)
                
                cleaned = '\n'.join(result_lines).strip()
                
                # If still has bullet points at start, try to get just the core content
                if cleaned.startswith('- '):
                    # Take the text after the last bullet if it's a single line answer
                    lines = [l for l in cleaned.split('\n') if l.strip()]
                    if lines:
                        # Get last non-bullet line, or strip the bullet from last line
                        for line in reversed(lines):
                            if not line.strip().startswith('- '):
                                cleaned = line.strip()
                                break
                        else:
                            # All lines are bullets, strip bullet from last one
                            cleaned = lines[-1].strip()[2:].strip()
                
                return cleaned
        
        return Response(completion.choices[0].message.content)


# Create LLM instance using the wrapper
llm = GroqLLMWrapper(groq_client, GROQ_MODEL)

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
    "intent": "UPDATE" | "QUERY" | "CHAT" | "BULK_INSERT",
    "confidence": 0.0 to 1.0,
    "resolved_context": {{
        "table": "patients|visits|prescriptions|billing",
        "action": "select|insert|update|delete|bulk_insert",
        "inferred_from_history": "what you inferred from conversation history"
    }},
    "reasoning": "brief explanation"
}}

INTENT CLASSIFICATION:
- "QUERY": Any SELECT operation (show, list, find, get, search, display, how many, count, etc.)
- "UPDATE": Single INSERT, UPDATE, or DELETE operation
- "BULK_INSERT": When user wants to add MULTIPLE records at once (e.g., "add 5 patients", "create dummy data", "populate with sample records", "add realistic test data")
- "CHAT": Greetings, help requests, general questions not about data

CRITICAL RULES:
1. Use conversation history to understand context ("it", "that one", "the same", etc.)
2. Be aggressive about inferring intent - don't ask unnecessary questions
3. For bulk data requests (add multiple records, dummy data, sample data, populate) -> use BULK_INSERT
4. Simple queries should just execute, not ask for clarification

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
        
        return {
            "intent": intent,
            "needs_clarification": False,
            "context_data": context,
            "resolved_context": analysis.get("resolved_context", {})
        }
        
    except json.JSONDecodeError:
        # Fallback - just proceed with the request
        intent = "QUERY" if any(w in last_message.lower() for w in ["show", "list", "get", "find", "search"]) else "UPDATE"
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

CONVERSATION HISTORY (CRITICAL - read carefully to understand context and previous operations):
{history_str}

CURRENT DATA CONTEXT:
{context}

USER REQUEST: "{last_message}"

CONTEXT UNDERSTANDING RULES:
1. READ THE CONVERSATION HISTORY CAREFULLY - it contains SQL that was executed and IDs that were affected
2. Look for patterns like "[SQL: UPDATE billing SET status = 'Paid' WHERE id = 2]" - this tells you record ID 2 was changed
3. "the one you just updated" / "the one I changed" / "leave that one" = the ID from the most recent UPDATE in history
4. "change the rest" / "all except that one" = use WHERE id != (the recently updated ID)
5. "all others" / "the remaining ones" = exclude the IDs mentioned in recent operations

CRITICAL EXAMPLES:
- History shows "[SQL: UPDATE billing SET status = 'Paid' WHERE id = 2]"
  User: "change the rest to Pending" 
  -> UPDATE billing SET status = 'Pending' WHERE id != 2

- History shows "updated record ID 5"
  User: "leave that one, update the others to Overdue"
  -> UPDATE billing SET status = 'Overdue' WHERE id != 5

- History shows "changed status to Paid for id=2"
  User: "keep that paid, mark others as pending"
  -> UPDATE billing SET status = 'Pending' WHERE id != 2

SIMPLE EXAMPLES:
- "show pending bills" -> SELECT * FROM billing WHERE status = 'Pending'
- "mark as paid" (after showing bill id=2) -> UPDATE billing SET status = 'Paid' WHERE id = 2
- "add new patient John" -> INSERT INTO patients (name) VALUES ('John')

COMPLEX JOIN/SUBQUERY EXAMPLES:
- "show visits with patient names" -> SELECT v.*, p.name FROM visits v JOIN patients p ON v.patient_id = p.id
- "patients with two visits" -> SELECT p.* FROM patients p WHERE p.id IN (SELECT patient_id FROM visits GROUP BY patient_id HAVING COUNT(*) = 2)
- "full details of patient with id 1" -> SELECT p.*, v.date, v.diagnosis, v.doctor FROM patients p LEFT JOIN visits v ON p.id = v.patient_id WHERE p.id = 1
- "all visits for patient John" -> SELECT v.* FROM visits v JOIN patients p ON v.patient_id = p.id WHERE p.name LIKE '%John%'
- "patients who have visits" -> SELECT DISTINCT p.* FROM patients p INNER JOIN visits v ON p.id = v.patient_id
- "count visits per patient" -> SELECT patient_id, COUNT(*) as visit_count FROM visits GROUP BY patient_id
- "patients with more than one visit" -> SELECT p.* FROM patients p WHERE p.id IN (SELECT patient_id FROM visits GROUP BY patient_id HAVING COUNT(*) > 1)

RELATIONSHIP NOTES:
- visits.patient_id references patients.id
- prescriptions.visit_id references visits.id  
- billing.patient_id references patients.id
- Use JOINs to connect related tables
- Use subqueries with IN or EXISTS for filtering by related table conditions

SQL RULES:
1. Return ONLY ONE SQL query - no markdown, no explanation, no multiple statements
2. For INSERT: NEVER include 'id' column (auto-generated)
3. For UPDATE/DELETE: Always use WHERE clause
4. NEVER use semicolons to separate multiple statements - only ONE statement allowed
5. Use != for "not equal" / "except" conditions
6. Use proper table aliases (p for patients, v for visits, etc.) in JOINs

Generate the SQL query:"""

    response = llm.invoke([SystemMessage(content=prompt)])
    sql_query = response.content.strip()
    
    # Debug logging
    print(f"[DEBUG] Raw LLM response: {sql_query[:500]}")
    
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
    
    # Ensure only one statement (remove anything after semicolon)
    if ";" in sql_query:
        sql_query = sql_query.split(";")[0].strip()
    
    print(f"[DEBUG] Final SQL query: {sql_query}")
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
        affected_ids = []
        
        if is_write:
            conn.commit()
            row_count = cursor.rowcount
            
            if row_count == 0:
                execution_result = "No records were affected. The specified record may not exist."
            else:
                # Get more context about what was done
                if "INSERT" in sql_query.upper():
                    last_id = cursor.lastrowid
                    affected_ids = [last_id]
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
            "table_changed": table_changed,
            "sql_query": sql_query  # Pass through for response context
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
        elif "only execute one statement" in error_msg.lower():
            return {"error": "I can only run one database operation at a time. Please break this into separate requests."}
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
            # Try to parse as JSON (for query results or structured responses)
            data = json.loads(result)
            
            # Check if it's already a formatted response object (from seed_data, etc.)
            if isinstance(data, dict) and "type" in data:
                return {"messages": [HumanMessage(content=json.dumps(data))]}
            
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
                
                # Generate simple summary without LLM (avoids Compound model reasoning)
                count = len(data)
                summary_templates = {
                    "patients": f"Found {count} patient{'s' if count != 1 else ''}.",
                    "visits": f"Found {count} visit{'s' if count != 1 else ''}.",
                    "prescriptions": f"Found {count} prescription{'s' if count != 1 else ''}.",
                    "billing": f"Found {count} billing record{'s' if count != 1 else ''}.",
                    "audit": f"Found {count} audit log entr{'ies' if count != 1 else 'y'}.",
                    "data": f"Found {count} record{'s' if count != 1 else ''}."
                }
                summary_text = summary_templates.get(table_type, f"{count} record{'s' if count != 1 else ''} found.")
                
                response_obj = {
                    "type": "table",
                    "table_type": table_type,
                    "message": summary_text,
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


def generate_bulk_insert(state: AgentState):
    """Uses LLM to generate multiple INSERT statements for bulk data requests."""
    messages = state["messages"]
    last_message = messages[-1].content
    context = state.get("context_data", "{}")
    
    prompt = f"""You are a data generator for a medical database. Generate realistic INSERT statements based on the user's request.

DATABASE SCHEMA:
- patients (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, age INTEGER, gender TEXT, address TEXT, phone TEXT, notes TEXT)
- visits (id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id INTEGER, date TEXT, diagnosis TEXT, doctor TEXT)
- prescriptions (id INTEGER PRIMARY KEY AUTOINCREMENT, visit_id INTEGER, medication TEXT, dosage TEXT)
- billing (id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id INTEGER, amount REAL, status TEXT, date TEXT)
  - status values: 'Pending', 'Paid', 'Overdue'

CURRENT DATA (for reference - use existing patient IDs for visits/billing if needed):
{context}

USER REQUEST: "{last_message}"

RULES:
1. Generate realistic, varied data (different names, ages, conditions, etc.)
2. NEVER include 'id' columns - they are auto-generated
3. Use realistic medical data (proper diagnoses, medications, dosages)
4. For dates, use format 'YYYY-MM-DD' and recent dates (2025)
5. Return ONLY the SQL statements, one per line
6. Each INSERT should be a complete, valid SQL statement
7. If adding visits/prescriptions/billing, reference valid patient_ids from context or newly created patients
8. For "dummy data" or "sample data" requests, add data to ALL tables with proper relationships

Generate the INSERT statements:"""

    response = llm.invoke([SystemMessage(content=prompt)])
    sql_statements = response.content.strip()
    
    # Clean up the response
    sql_statements = sql_statements.replace("```sql", "").replace("```", "").strip()
    
    # Split into individual statements and execute each
    conn = get_db_connection()
    cursor = conn.cursor()
    
    success_count = 0
    errors = []
    tables_affected = set()
    
    for line in sql_statements.split("\n"):
        line = line.strip()
        if line and line.upper().startswith("INSERT"):
            # Remove trailing semicolon if present
            if line.endswith(";"):
                line = line[:-1]
            try:
                cursor.execute(line)
                success_count += 1
                # Track which table was affected
                if "patients" in line.lower():
                    tables_affected.add("patients")
                elif "visits" in line.lower():
                    tables_affected.add("visits")
                elif "prescriptions" in line.lower():
                    tables_affected.add("prescriptions")
                elif "billing" in line.lower():
                    tables_affected.add("billing")
            except Exception as e:
                errors.append(f"{line[:50]}... : {str(e)}")
    
    conn.commit()
    conn.close()
    
    if success_count > 0:
        table_list = ", ".join(tables_affected) if tables_affected else "database"
        result_msg = f"Successfully created {success_count} new record(s) in {table_list}."
        if errors:
            result_msg += f" ({len(errors)} statements failed)"
        return {
            "execution_result": result_msg,
            "table_changed": list(tables_affected)[0] if len(tables_affected) == 1 else "patients"
        }
    else:
        return {"error": f"Failed to insert data. Errors: {'; '.join(errors[:3])}"}


# --- Graph Construction ---
workflow = StateGraph(AgentState)

workflow.add_node("analyze", analyze_request)
workflow.add_node("generate_sql", generate_smart_sql)
workflow.add_node("validate", validate_operation)
workflow.add_node("execute_sql", execute_sql)
workflow.add_node("emit_event", emit_event)
workflow.add_node("respond", generate_response)
workflow.add_node("bulk_insert", generate_bulk_insert)

workflow.set_entry_point("analyze")

def route_after_analysis(state: AgentState):
    """Routes based on analysis results."""
    if state.get("needs_clarification"):
        return "respond"
    if state.get("intent") == "CHAT":
        return "respond"
    if state.get("intent") == "BULK_INSERT":
        return "bulk_insert"
    return "generate_sql"

workflow.add_conditional_edges("analyze", route_after_analysis)
workflow.add_edge("generate_sql", "validate")
workflow.add_edge("bulk_insert", "emit_event")

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
