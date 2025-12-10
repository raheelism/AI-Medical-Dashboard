from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from backend.api.router import router as api_router
from backend.api.websocket import manager
from backend.langgraph.agent import app_graph
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

app = FastAPI()

class ChatRequest(BaseModel):
    message: str

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
    inputs = {"messages": [HumanMessage(content=request.message)]}
    result = await app_graph.ainvoke(inputs)
    final_message = result["messages"][-1].content
    return {"response": final_message}

@app.get("/")
def root():
    return {"message": "Medical System API is running"}
