# SmartResolve

SmartResolve is a synthetic-data IT incident response MVP for a university class. It unifies ticket intake, network and security signals, incident correlation, and technician recommendations.

## Architecture

- `backend/app/routers/`: feature-owned HTTP APIs (`tickets`, `incidents`, `network`, `security`, `technicians`, `dashboard`).
- `backend/app/services/`: transparent business rules for classification, priority, similarity, anomaly/risk detection, and recommendations.
- `backend/app/models/`: SQLAlchemy SQLite tables. `seed.py` creates the Woodward demonstration scenario.
- `frontend/src/pages/`: API-backed operations dashboard, ticket intake, network actions, and incident detail/workflow.
- `backend/app/routers/auth.py` and `portal.py`: local account registration/sign-in, user ticket ownership, follow-up messages, and controlled rule-based support guidance.
- `frontend/src/pages/Connect.jsx`: separate user portal at `/connect`.

## Separate portals and local authentication

- **SmartResolve Connect:** `http://localhost:5173/connect`. Users can register, sign in, chat with the rule-based support assistant, submit tickets, and track their own tickets and updates.
- **SmartResolve Operations:** `http://localhost:5173/operations`. Technicians and admins sign in with accounts provisioned locally. User accounts cannot open this portal; the frontend checks `/api/auth/me` and the backend also rejects unauthorized API requests.

Passwords use salted PBKDF2-SHA256 hashes. Signed bearer sessions expire after 24 hours. Operations tickets, incidents, network events, dashboard analytics, and technician APIs require technician or admin roles. Technician roster create/edit/delete operations require admin. Security event endpoints and security evidence on incidents require explicit security access (or admin). Users can only read or update messages on their own tickets. Technician replies are user-visible ticket updates, and ticket status is refreshed in Connect periodically.

Public registration always creates the `user` role, even if a caller submits a different role field. Create an Operations account with the local-only CLI. It runs the existing safe database migrations and synthetic seed before creating the account, so you do not need to access real university accounts or start the API first.

```bash
cd "/Users/ompanchal/Desktop/SmartResolve APP/backend"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SMARTRESOLVE_ENV=development
PYTHONPATH=. python -m app.provision --local-demo
```

The explicitly opted-in local defaults are **`demo.technician@smartresolve.local`** / **`SmartResolve-Demo-Only-2026!`**. These are local capstone demo credentials only; they are not UNC Charlotte accounts and must never be used in production. Override them with `SMARTRESOLVE_DEMO_TECH_EMAIL`, `SMARTRESOLVE_DEMO_TECH_PASSWORD`, and `SMARTRESOLVE_DEMO_TECH_NAME` if desired. The demo account is linked to the seeded Maya Chen technician and is authorized for synthetic security events.

Provisioning is repeatable: if that matching technician account already exists, the command leaves it untouched. To explicitly reset its password to the configured value (or the local default), run `PYTHONPATH=. python -m app.provision --local-demo --reset-password`. A production `SMARTRESOLVE_ENV` blocks local-demo mode. For a separately named Operations account, use `--email`, `--name`, and `--technician-id`; the CLI prompts for its password without echoing it. For local system administration, provision an admin with `--admin`; public registration cannot assign roles.

Set `SMARTRESOLVE_SECRET_KEY` to a long random value to keep tokens valid across backend restarts; if omitted, a private per-process random key is used and sessions expire when the server restarts. Set `VITE_API_URL` to the API origin when it is not `http://127.0.0.1:8000`.

## Run locally

Terminal 1 — provision the local technician, then start the backend:
```bash
cd "/Users/ompanchal/Desktop/SmartResolve APP/backend"
source .venv/bin/activate
export SMARTRESOLVE_ENV=development
export SMARTRESOLVE_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
PYTHONPATH=. python -m app.provision --local-demo
uvicorn app.main:app --reload
```

Terminal 2 — frontend:
```bash
cd "/Users/ompanchal/Desktop/SmartResolve APP/frontend"
npm install
npm run dev
```

Open `http://localhost:5173`. The API docs are at `http://localhost:8000/docs`.
Open `http://localhost:5173/connect` for SmartResolve Connect.
Open `http://localhost:5173/operations` for SmartResolve Operations.
On the login page, choose **Technician Login** and enter the local demo credentials above. For Connect, choose **User Login** and register a separate user account.

## Demo flow

The seed data includes three Woodward Wi-Fi tickets and a 240 ms / 21% packet-loss event. Visit **Network**, create any anomaly (or use the seeded one), then correlation runs automatically. Open **Incidents** to inspect linked evidence and move it from Open → Investigating → Resolved.

### Building availability monitor

The **Network Monitoring** page and Operations overview show availability for one endpoint per building. These are synthetic examples, not UNC Charlotte network measurements. Seeded states include Online (Woodward Hall and CCI), Offline (Atkins Library), Unknown (Student Union), and a deterministic status cycle (Demo Cycle Building). Each source is labeled **Simulated Demo**. The dashboard metrics are calculated from configured endpoints and their latest effective availability state. The backend runs a monitoring cycle every two minutes by default. Set `SMARTRESOLVE_MONITOR_INTERVAL_SECONDS` to a value from 30 to 3600 seconds to change it. Set `SMARTRESOLVE_MONITOR_ENABLED=false` only when intentionally disabling backend checks (for example, in tests). Operations views and Connect outage notices poll separately every 20 seconds. A database lease elects one worker to run checks when multiple API workers or reload processes are active.

Authorized Operations accounts can inspect history, run a check (rate-limited to once per 15 seconds per endpoint), and review ticket correlations. Offline status requires the configured number of consecutive failed checks. Stale data (more than three monitoring intervals old) and missing checks are shown as Unknown with a reason. An incident is only created or linked after a technician explicitly reviews the evidence. Admin accounts can add a demo endpoint with an Online, Offline, Unknown, or repeatable status cycle scenario. The cycle follows a persisted deterministic sequence of Online, Online, Failed, Failed, Unknown; it does not change on page refresh. A threshold of `1` is useful when demonstrating an immediate Offline result; a threshold of `2` requires two failed checks. The user portal only shows an outage notice when the requested building matches an Offline monitor, and still permits ticket submission.

Live monitoring is optional and disabled unless the server operator explicitly allowlists an endpoint. Set `SMARTRESOLVE_APPROVED_ENDPOINTS` on the backend to exact semicolon-separated HTTP(S) health-check URLs before configuring them in Operations. The service checks approved URLs only; it rejects IP literals, private/reserved DNS results, redirects, nonstandard ports, metadata hosts, and unapproved URLs. Configure only endpoints you own or have permission to check. Response time and status describe that single URL, not every network service in the building. Live checks are manually triggered and do not execute arbitrary scans.

## Test

```bash
cd backend
PYTHONPATH=. pytest
```
