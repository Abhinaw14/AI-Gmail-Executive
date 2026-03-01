# AI Context-Aware Gmail Executive Assistant

A production-style AI executive assistant that reads Gmail, reasons over Google Calendar, builds persistent RAG + Graph memory, orchestrates a multi-agent pipeline, generates context-aware replies with human-in-the-loop approval, and surfaces a React dashboard.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Google Gemini 2.0 Flash |
| Frontend | React 18 + Tailwind CSS + Vite |
| Backend | FastAPI (Python) |
| Vector Memory | ChromaDB (local embedded) |
| Graph Memory | NetworkX |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Gmail + Calendar | Google OAuth2 API |

## Quick Start

### 1. Prerequisites
- Python 3.10+
- Node.js 18+
- Google Cloud project with Gmail API + Calendar API enabled
- `credentials.json` OAuth2 file in project root

### 2. Run the Backend (FastAPI)
```bash
# Install Python dependencies (if not already done)
pip install -r requirements.txt

# Start the Python server (polls Gmail & runs AI background agent)
uvicorn api.main:app --reload --port 8000
```
*Note: On first start, a browser window will open for Google OAuth login. Approve access and `token.json` will be saved automatically.*

### 3. Run the Frontend (React / Vite)
Open a **new terminal tab** and run:
```bash
cd frontend

# Install Node dependencies (if not already done)
npm install

# Start the React UI dashboard
npm run dev
```
*The app will automatically open or be available at `http://localhost:5173`.*

## Project Structure

```
AMD_Slingshot/
├── credentials.json          ← Google OAuth2 (DO NOT COMMIT)
├── .env                      ← your secrets (DO NOT COMMIT)
├── requirements.txt
│
├── config.py                 ← central settings loader
├── db/                       ← SQLAlchemy models + engine
├── memory/                   ← ChromaDB + NetworkX memory
├── agents/                   ← multi-agent pipeline
├── utils/                    ← classifier, parser, style learner
├── api/                      ← FastAPI backend
└── frontend/                 ← React + Tailwind dashboard
```

## Agents

| Agent | Role |
|-------|------|
| Coordinator | Orchestrates all agents, routes decisions |
| Email Reader | Gmail API polling + parsing |
| Retrieval | Hybrid RAG + Graph context retrieval |
| Scheduler | Calendar availability + event creation |
| Task Planner | Extract tasks, push to Notion/Trello |
| Reply Generator | Context-aware draft with Gemini |
| Reporting | Daily/weekly intelligence reports |

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /emails` | Paginated inbox with classification |
| `GET /emails/{id}` | Full thread + retrieved context |
| `POST /emails/{id}/process` | Trigger coordinator agent |
| `GET /replies/pending` | Drafts awaiting approval |
| `POST /replies/{id}/approve` | Send approved reply |
| `GET /calendar/availability` | Free calendar slots |
| `GET /reports/daily` | Latest daily report |

## Environment Variables

See `.env.example` for the full list of required and optional variables.

## Architecture Flow

```
Email received → Email Reader Agent
→ Classifier (urgent / meeting / task / spam)
→ Retrieval Agent (ChromaDB + Graph context)
→ Scheduler Agent (calendar check if needed)
→ Reply Generator Agent (Gemini + RAG context)
→ Human Approval UI → Send
→ Memory update (vector + graph)
→ Reporting Agent (aggregated insights)
```
