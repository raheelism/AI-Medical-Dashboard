from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from backend.api.router import router as api_router
from backend.api.websocket import manager
from backend.langgraph.agent import app_graph
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage
from typing import List, Optional

app = FastAPI()

# In-memory conversation storage (per session)
# In production, use Redis or database for persistence
conversation_store: dict[str, List] = {}

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    session_id = request.session_id or "default"
    
    # Get or create conversation history for this session
    if session_id not in conversation_store:
        conversation_store[session_id] = []
    
    chat_history = conversation_store[session_id]
    
    # Add user message to history
    user_message = HumanMessage(content=request.message)
    
    # Invoke agent with full history context
    inputs = {
        "messages": [user_message],
        "chat_history": chat_history.copy()
    }
    result = await app_graph.ainvoke(inputs)
    final_message = result["messages"][-1].content
    
    # Update conversation history
    chat_history.append(user_message)
    chat_history.append(AIMessage(content=final_message))
    
    # Keep only last 20 messages to prevent memory bloat
    if len(chat_history) > 20:
        conversation_store[session_id] = chat_history[-20:]
    
    return {"response": final_message, "session_id": session_id}


@app.post("/api/chat/clear")
async def clear_chat(session_id: str = "default"):
    """Clear conversation history for a session."""
    if session_id in conversation_store:
        conversation_store[session_id] = []
    return {"message": "Conversation cleared", "session_id": session_id}

@app.get("/")
def root():
    return {"message": "Medical System API is running"}
