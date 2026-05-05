# OHS Management API

Production-ready FastAPI backend scaffold for an Occupational Health and Safety Management System.

## Stack

- FastAPI
- PostgreSQL
- SQLAlchemy 2
- Alembic
- JWT authentication
- Role-based access control

## Modules

- Users
- Roles
- Sites
- Incidents
- Hazards
- Inspections
- Corrective actions
- Safety KPIs
- Safety communications
- Behaviour observations
- Incident investigations / root cause analysis
- Legal compliance register
- Job safety analysis / risk assessment
- Contractor safety management
- Equipment / PPE / emergency equipment register
- Occupational health / medical surveillance
- Emergency management & drills
- Document control
- Audit management
- Notification delivery (email / SMS)
- Background jobs / scheduler
- Permits
- Approval workflows
- Audit logs

## Quick Start

1. Create an environment file:

```bash
cp .env.example .env
```

2. Set a strong `SECRET_KEY` in `.env`.

3. Start the stack:

```bash
docker compose up --build
```

4. Check service health:

```bash
curl http://localhost:8000/api/v1/health
```

5. Bootstrap the first admin user:

```bash
curl -X POST http://localhost:8000/api/v1/auth/bootstrap-admin \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","full_name":"System Admin","password":"ChangeMe123!"}'
```

6. Log in:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=ChangeMe123!"
```

API docs are available at `http://localhost:8000/docs`.

## API Notes

Core list endpoints for incidents, hazards, inspections, and corrective actions return a stable pagination envelope:

```json
{
  "items": [],
  "total": 0,
  "skip": 0,
  "limit": 100
}
```

Export endpoints are available under `/api/v1/exports` for authenticated users. CSV exports use stable headers, and HTML report endpoints return print-ready pages. Coverage now includes incidents, hazards, inspections, corrective actions, incident investigations, legal compliance items, JSAs, contractors, asset register records, medical surveillance, emergency drills, document control, and audits.

Evidence attachments are available under `/api/v1/attachments/{entity_type}/{entity_id}` for incidents, hazards, inspections, corrective actions, permits, training, compliance acknowledgements, safety communications, behaviour observations, incident investigations, legal compliance items, JSAs, contractors, asset register records, medical surveillance, emergency drills, document control records, and audits. Files are stored locally in `uploads/` during development with generated filenames, while original filenames remain available through attachment metadata and the authenticated download endpoint.

Safety KPI records are available under `/api/v1/safety-kpis` and store hours worked for a reporting period. The API calculates:

- `TRIFR = (recordable incidents * 1,000,000) / hours worked`
- `LTIFR = (lost time incidents * 1,000,000) / hours worked`

Incident records now include `is_recordable` and `is_lost_time` flags so the KPI calculations are derived from the underlying incident log rather than manually keyed rates.

Enterprise feature pack endpoints:

- Incident investigations: `/api/v1/incident-investigations`
- Legal compliance register: `/api/v1/legal-compliance`
- JSA / risk assessments: `/api/v1/jsas`
- Contractor safety management: `/api/v1/contractors`
- Equipment / PPE register: `/api/v1/asset-register`
- Occupational health / medical surveillance: `/api/v1/medical-surveillance`
- Emergency drills: `/api/v1/emergency-drills`
- Document control: `/api/v1/documents`
- Audit management: `/api/v1/audits`
- Notification delivery logs: `/api/v1/notification-deliveries`
- Background job runs: `/api/v1/job-runs`

Enterprise feature pack rules:

- Incident investigations must link to an existing incident, and high or critical incidents must have a completed investigation before closure.
- Final investigation approval, JSA approval, and contractor approval-for-work actions are restricted to authorized roles.
- Legal compliance items notify owners when reviews are due soon or overdue, and non-compliant items appear on the dashboard.
- JSAs send review reminders, require approval before operational use, and expire automatically when approved records pass their review date.
- Contractors cannot be approved for work until induction and compliance documents are complete and not expired.
- Asset register items notify recipients when inspections are due, overdue, or when an item is marked defective.
- Medical surveillance records derive `due`, `overdue`, or `completed` state from due and completion dates, notify on due soon / overdue states, and surface compliance exposure on the dashboard.
- Emergency drills track scheduling, attendance, issues, and corrective actions, and generate due-soon or overdue reminders for relevant operational roles.
- Controlled documents support versioning, approval workflow requests, expiry reminders, and acknowledgement assignment that creates linked compliance acknowledgement records.
- Audit records support audit scoring, linked corrective action IDs, open-audit reminders, and dashboard compliance visibility.
- Notification delivery attempts are logged per channel with `sent`, `failed`, or `skipped` outcomes for email and SMS delivery.
- Scheduler runs can be triggered on demand through `/api/v1/job-runs/run-scheduled` and optionally on startup when `SCHEDULER_ENABLED=true`.

Controlled approval workflows are available for:

- Incident closure
- Corrective action verification
- Permit approval
- High and critical hazard review
- Controlled document approval

Approval requests are stored in `approval_workflows`, surfaced on the approvals workspace and related detail pages, and generate audit logs plus request, approval, and rejection notifications.

Dashboard analytics endpoints are available under `/api/v1/dashboard` and keep the existing overview, site summary, and trend responses intact while adding management-level analytics for:

- Risk: `/overview`, `/sites`, `/trends`, `/risk`
- Actions: `/actions`
- Compliance: `/compliance`
- Permits: `/permits`
- Approvals: `/approvals`
- Safety performance: KPI snapshots, TRIFR/LTIFR trends, communication activity, and behaviour observation distributions
- Enterprise pack analytics: investigations, legal compliance, JSAs, contractor readiness, asset condition / inspection exposure, medical surveillance, emergency drills, document control, and audits
- Executive summary: `/management-summary`

All dashboard analytics endpoints support optional `site_id`, `date_from`, and `date_to` filters. The management summary combines incident, risk, corrective action, compliance, permit, and approval snapshots with the top urgent items for executive review.

The executive dashboard includes dedicated widgets for:

- Open investigations
- Non-compliant legal items
- Pending JSA approvals
- Contractor compliance gaps
- Defective or overdue equipment
- Overdue medical surveillance
- Overdue emergency drills
- Expiring controlled documents
- Open audits

Enterprise RBAC is enforced in the backend and reflected in the frontend shell. Standard roles are:

- `admin`
- `ohs_manager`
- `safety_officer`
- `supervisor`
- `employee`

Supervisors and employees are site-scoped through `users.assigned_site_id`. Admin, OHS Manager, and Safety Officer accounts can access all sites by default.

Approval workflow RBAC summary:

- `admin` and `ohs_manager` can view all approvals and make final approve or reject decisions.
- `safety_officer` can request and view approvals but cannot make final decisions.
- `supervisor` can request and view approvals only for records in the assigned site.
- Direct approval decisions update the related record state where applicable: incidents receive closure metadata, corrective actions are verified and closed, permits are marked approved, and reviewed hazards receive reviewer timestamps.

## Local Development

Install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Run migrations:

```bash
alembic upgrade head
```

Local upload settings:

- `UPLOAD_DIR` defaults to `uploads`
- `ATTACHMENT_MAX_FILE_SIZE_BYTES` defaults to `10485760` (10 MB)
- Supported upload types: `jpg`, `jpeg`, `png`, `webp`, `pdf`, `doc`, `docx`, `xls`, `xlsx`, `csv`

Notification and scheduler settings:

- `SMTP_ENABLED`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_USE_TLS`
- `SMS_ENABLED`, `SMS_PROVIDER_NAME`
- `SCHEDULER_ENABLED`, `SCHEDULER_POLL_SECONDS`

Seed realistic demo data:

```bash
python scripts/seed_demo.py
```

The demo seed script is intentionally limited to local targets. It refreshes only records in the demo namespace (`DEMO-*` sites, `@demo.ohs.local` users, `Demo:` records) so it can be rerun safely without affecting non-demo local data.

Demo user password:

```text
DemoPass123!
```

Demo logins created by `python scripts/seed_demo.py`:

- `emma.ncube@demo.ohs.local` - `admin`
- `brian.phiri@demo.ohs.local` - `ohs_manager`
- `grace.tembo@demo.ohs.local` - `safety_officer`
- `ruth.zulu@demo.ohs.local` - `supervisor` - assigned to Lusaka Blending Plant
- `chipo.lungu@demo.ohs.local` - `supervisor` and `employee` - assigned to Ndola Distribution Warehouse
- `kelvin.mwila@demo.ohs.local` - `employee` - assigned to Solwezi Exploration Camp

Start the API:

```bash
uvicorn app.main:app --reload
```

Run tests:

```bash
pytest -q
```

Build the frontend:

```bash
cd frontend
npm run build
```

## Access Model

Default roles are seeded by migrations and normalized by the role service:

- `admin`
- `ohs_manager`
- `safety_officer`
- `supervisor`
- `employee`

Role summary:

- `admin`: full access to users, roles, sites, audit logs, dashboards, reports, exports, and all operational modules.
- `ohs_manager`: enterprise operational access across incidents, hazards, inspections, corrective actions, training, compliance, permits, investigations, legal compliance, JSAs, contractors, assets, medical surveillance, emergency drills, document control, audits, dashboards, reports, delivery logs, and job runs.
- `safety_officer`: operational access for incidents, hazards, inspections, corrective actions, safety KPIs, safety communications, behaviour observations, incident investigations, legal compliance, JSAs, contractors, asset registers, training, compliance, permits, medical surveillance, emergency drills, document control, audits, dashboards, exports, delivery logs, and job-run visibility without role management.
- `supervisor`: assigned-site access for incident and hazard reporting, safety communications, behaviour observation follow-up, corrective action updates on assigned work, permit requests, investigation/legal/contractor visibility, JSA creation and editing, asset register maintenance, emergency drill participation and upkeep, audit visibility, document visibility, quick reporting, and the limited dashboard including KPI visibility.
- `employee`: assigned-site reporting for incidents, hazards, and behaviour observations; read access to safety communications, JSAs, asset registers, and controlled documents; permit requests; notifications; quick reporting; and self-service training/compliance acknowledgements.

Enterprise permission groups:

- `investigations.view`, `investigations.create`, `investigations.edit`, `investigations.approve`
- `legal_compliance.view`, `legal_compliance.create`, `legal_compliance.edit`
- `jsa.view`, `jsa.create`, `jsa.edit`, `jsa.approve`
- `contractors.view`, `contractors.create`, `contractors.edit`, `contractors.approve`
- `assets.view`, `assets.create`, `assets.edit`
- `medical_surveillance.view`, `medical_surveillance.create`, `medical_surveillance.edit`
- `emergency_drills.view`, `emergency_drills.create`, `emergency_drills.edit`
- `documents.view`, `documents.create`, `documents.edit`, `documents.approve`
- `audits.view`, `audits.create`, `audits.edit`
- `notification_delivery.view`
- `job_runs.view`, `job_runs.manage`

The first user can be created only through `/api/v1/auth/bootstrap-admin` while the users table is empty. After that, user creation is restricted to `admin`, while role viewing and operational user lookup follow the RBAC rules above.
