# AI Medical Dashboard - Copilot Instructions

## Architecture Overview

This is a **natural language medical records system** with two main parts:
- **Backend** (`/backend`): FastAPI + LangGraph agent that converts natural language to SQL
- **Frontend** (`/frontend`): Next.js 16 dashboard with real-time updates via WebSocket

**Data Flow**: User chat → LangGraph agent (classify → generate SQL → execute → broadcast) → WebSocket notifies frontend → Dashboard refreshes

## Database Schema

SQLite database at `backend/medical.db` with these tables (see `backend/db/schema.sql`):
- `patients` (id, name, age, gender, address, phone, notes)
- `visits` (id, patient_id, date, diagnosis, doctor)
- `prescriptions` (id, visit_id, medication, dosage)
- `billing` (id, patient_id, amount, status, date)
- `audit_log` (id, time, operation, old_value, new_value, user)

Database auto-initializes with seed data on first run via `backend/db/connection.py`.

## LangGraph Agent Pattern

The agent in `backend/langgraph/agent.py` uses a **StateGraph** with this flow:
1. `classify_intent` - Determines UPDATE, QUERY, or UNKNOWN
2. `generate_sql` - LLM generates raw SQL (uses Groq/Llama 3.3)
3. `execute_sql` - Runs against SQLite, logs to audit_log
4. `emit_event` - Broadcasts table changes via WebSocket
5. `respond` - Returns natural language response

**State type**: `AgentState` with fields: messages, intent, sql_query, execution_result, error, table_changed

When modifying the agent, maintain this node pattern and ensure WebSocket broadcast happens after writes.

## API Endpoints

Backend runs on `http://localhost:8000`:
- `POST /api/chat` - Main chat endpoint (accepts `{message: string}`)
- `GET /api/patients|visits|prescriptions|billing|audit_log` - CRUD endpoints
- `WS /ws` - WebSocket for real-time updates (broadcasts `{table, action: "refresh"}`)

## Developer Workflow

```bash
# Backend (requires GROQ_API_KEY env var)
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

Backend listens on port 8000, frontend on port 3000.

## Key Conventions

- **Frontend components** use `"use client"` directive for client-side React
- **WebSocket hook** at `frontend/hooks/useWebSocket.ts` returns `lastMessage` for reactivity
- **API calls** from frontend use hardcoded `http://localhost:8000` URLs
- **LLM prompts** include explicit schema info (copy pattern from `generate_sql` node)
- **SQL safety**: DROP operations are blocked in `validate_operation` node
- All database writes are logged to `audit_log` table

## Adding New Features

**New database table**: Update `schema.sql`, add seed data in `connection.py`, create API route in `router.py`, add tab in `Dashboard.tsx`

**New agent capability**: Add node function in `agent.py`, wire into `StateGraph`, update intent classifier prompt

**Frontend data display**: Data tables auto-render columns from API response (see `Dashboard.tsx` dynamic table pattern)
