# AI Medical Dashboard

A natural language medical records system powered by AI. Manage patients, visits, prescriptions, and billing using conversational commands.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Next.js](https://img.shields.io/badge/Next.js-16-black)
![Groq](https://img.shields.io/badge/Groq-Compound--Beta-orange)

## ✨ Features

- **Natural Language Interface** - Talk to your database in plain English
- **AI-Powered SQL Generation** - Automatically converts requests to SQL queries
- **Real-time Updates** - WebSocket-powered live dashboard updates
- **Rich Data Display** - Tables, success cards, and formatted responses
- **Multi-table Support** - Patients, visits, prescriptions, billing, and audit logs
- **Context-Aware** - Understands conversation history for follow-up queries

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────────────────────────────┐
│   Next.js UI    │◄────┤           WebSocket                  │
│   (Port 3000)   │     │         Real-time Updates            │
└────────┬────────┘     └──────────────────────────────────────┘
         │                              ▲
         │ REST API                     │
         ▼                              │
┌─────────────────┐     ┌───────────────┴──────────────────────┐
│   FastAPI       │────►│         LangGraph Agent              │
│   (Port 8000)   │     │  ┌─────────┐  ┌─────────┐  ┌───────┐ │
└─────────────────┘     │  │ Analyze │─►│Gen SQL  │─►│Execute│ │
                        │  └─────────┘  └─────────┘  └───────┘ │
                        │         │                      │     │
                        │         ▼                      ▼     │
                        │  ┌─────────────────────────────────┐ │
                        │  │      Groq Compound Model        │ │
                        │  │   (GPT-OSS 120B + Llama 4)      │ │
                        │  └─────────────────────────────────┘ │
                        └──────────────────────────────────────┘
                                         │
                                         ▼
                        ┌──────────────────────────────────────┐
                        │          SQLite Database             │
                        │  patients | visits | prescriptions   │
                        │       billing | audit_log            │
                        └──────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- Groq API Key ([Get one here](https://console.groq.com))

### Backend Setup

```bash
cd backend

# Create virtual environment (optional)
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Set environment variable
# Create .env file with:
# GROQ_API_KEY=your_api_key_here

# Run server
uvicorn main:app --reload
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to access the dashboard.

## 💬 Example Commands

### Queries
- "Show all patients"
- "List pending bills"
- "Find female patients"
- "Show visits for patient Sarah"
- "Which patients have more than one visit?"

### Updates
- "Add a new patient named John, age 30, male"
- "Mark bill ID 2 as paid"
- "Update Sarah's phone to 555-1234"
- "Delete patient with ID 5"

### Complex Queries
- "Show full details of patients with two visits"
- "List all prescriptions with patient names"
- "Show billing summary by patient"

## 📁 Project Structure

```
AI-Medical-Dashboard/
├── backend/
│   ├── main.py              # FastAPI app entry
│   ├── requirements.txt     # Python dependencies
│   ├── api/
│   │   ├── router.py        # REST API routes
│   │   └── websocket.py     # WebSocket manager
│   ├── db/
│   │   ├── connection.py    # SQLite connection & seeding
│   │   └── schema.sql       # Database schema
│   └── langgraph/
│       └── agent.py         # LangGraph AI agent
├── frontend/
│   ├── app/
│   │   ├── page.tsx         # Main page
│   │   └── layout.tsx       # App layout
│   ├── components/
│   │   ├── ChatInterface.tsx # Chat UI
│   │   └── Dashboard.tsx     # Data dashboard
│   └── hooks/
│       └── useWebSocket.ts   # WebSocket hook
└── README.md
```

## 🗄️ Database Schema

| Table | Description |
|-------|-------------|
| `patients` | Patient records (name, age, gender, address, phone, notes) |
| `visits` | Visit records linked to patients (date, diagnosis, doctor) |
| `prescriptions` | Prescriptions linked to visits (medication, dosage) |
| `billing` | Billing records linked to patients (amount, status, date) |
| `audit_log` | Tracks all database changes |

## 🔧 Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Your Groq API key (required) |

### Model Selection

The agent uses Groq's Compound Beta model by default. To change, edit `backend/langgraph/agent.py`:

```python
GROQ_MODEL = "compound-beta"  # or "compound-beta-mini"
```

## 📝 License

MIT License - see [LICENSE](LICENSE) for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request
