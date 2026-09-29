# SmartResolve

SmartResolve is a synthetic-data IT incident response MVP for a university class. It unifies ticket intake, network and security signals, incident correlation, and technician recommendations.

## Architecture

- `backend/app/routers/`: feature-owned HTTP APIs (`tickets`, `incidents`, `network`, `security`, `technicians`, `dashboard`).
- `backend/app/services/`: transparent business rules for classification, priority, similarity, anomaly/risk detection, and recommendations.
- `backend/app/models/`: SQLAlchemy SQLite tables. `seed.py` creates the Woodward demonstration scenario.
- `frontend/src/pages/`: API-backed operations dashboard, ticket intake, network actions, and incident detail/workflow.

## Run locally

Terminal 1:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Terminal 2:
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The API docs are at `http://localhost:8000/docs`.

## Demo flow

The seed data includes three Woodward Wi-Fi tickets and a 240 ms / 21% packet-loss event. Visit **Network**, create any anomaly (or use the seeded one), then correlation runs automatically. Open **Incidents** to inspect linked evidence and move it from Open → Investigating → Resolved.

## Test

```bash
cd backend
PYTHONPATH=. pytest
```
