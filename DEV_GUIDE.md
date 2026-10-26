# ZmMH Dormitory Management System - Developer Guide & API Reference

> **Status:** Phase 2 Complete (Auth, Roles, Rooms, Settings, Audit, HRAR Catalog, Violations Lifecycle)  
> **Next Phase:** Phase 3 (Money - Charges, Payments, Receipts)  
> **Framework:** Flask 3.x with factory pattern + blueprints  
> **Database:** SQLite (dev) / PostgreSQL (Render prod)  
> **ORM:** Flask-SQLAlchemy 3.x + Flask-Migrate  
> **Auth:** Flask-Login + Werkzeug password hashing  
> **Forms:** Flask-WTF (CSRF enabled globally)  

---

# Tech Stack

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Framework | Flask | 3.0.3 | Web framework |
| ORM | Flask-SQLAlchemy | 3.1.1 | Database ORM |
| Migrations | Flask-Migrate | 4.0.7 | Database migrations (Alembic) |
| Authentication | Flask-Login | 0.6.3 | User sessions & login |
| Forms | Flask-WTF | 1.2.1 | Form handling + CSRF protection |
| Email | Flask-Mail | 0.9.1 | Email sending (temp passwords, etc.) |
| Environment | python-dotenv | 1.0.1 | Environment variable loading |
| Images | Pillow | 12.3.0 | Image processing |
| Server | Gunicorn | 22.0.0 | Production WSGI server |
| Database Driver | psycopg2-binary | 2.9.9 | PostgreSQL driver |
| Email Validation | email-validator | 2.2.0 | Email format validation |

---

## Folder Structure

```
zmmh/
├── run.py                      # Application entry point (create_app + run)
├── config.py                   # Configuration (DevConfig, ProdConfig)
├── requirements.txt            # Python dependencies
├── seed_roles.py               # Seed script for role catalog
├── seed_rooms.py               # Seed script for room catalog
├── seed_settings.py            # Seed script for settings catalog
├── .env                        # Local environment variables (NOT committed)
│
├── app/
│   ├── __init__.py             # Flask application factory (create_app)
│   ├── config.py               # App configuration classes
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── routes.py           # Login, logout, register, forgot, reset, bootstrap
│   │   └── forms.py            # LoginForm, ChangePasswordForm, CreateAccountForm, etc.
│   │
│   ├── roster/
│   │   ├── __init__.py
│   │   ├── models.py           # All SQLAlchemy models
│   │   ├── routes.py           # All roster/auth/roles/rooms/settings routes
│   │   ├── forms.py            # All WTForms forms
│   │   ├── default_roles.py    # Role catalog (17 roles)
│   │   ├── default_rooms.py    # Room catalog (20 rooms)
│   │   └── default_settings.py # Settings catalog (20 settings)
│   │
│   ├── violations/
│   │   ├── __init__.py         # Blueprint registration
│   │   ├── models.py           # ViolationRule, RuleVersion, ViolationRecord, Dispute, EscalationFlag
│   │   ├── forms.py            # RuleForm, LogViolationForm, DisputeForm, DecideDisputeForm
│   │   └── routes.py           # Rules admin, log, review, mine, disputes, auto-confirm job
│   │
│   └── utils/
│       ├── __init__.py
│       ├── decorators.py       # permission_required decorator
│       ├── email.py            # Email sending utilities
│       ├── photos.py           # Pillow photo upload helper (<=1280px)
│       └── settings.py         # Settings read/write helpers
│
├── app/templates/
│   ├── base.html               # Base template with navbar
│   ├── auth/
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── change_password.html
│   │   ├── create_account.html
│   │   ├── forgot.html
│   │   ├── reset.html
│   │   └── bootstrap.html
│   └── roster/
│       ├── roles.html
│       ├── role_edit.html
│       ├── rooms.html
│       ├── room_detail.html
│       ├── import.html
│       ├── settings.html
│       └── audit.html
│
├── migrations/                 # Flask-Migrate (Alembic) migration files
│   ├── versions/
│   │   ├── 1832d92c183b_phase1_models.py
│   │   └── b82d393e0f2c_phase1_4_residency_joined_at_left_at.py
│   │   └── c05781ef0981_phase2_1_violations_hrar.py

│   └── env.py
│
├── instance/                   # Instance folder (SQLite DB, runtime files)
│   └── zmmh.db                 # SQLite database (development only)
│
├── venv/                       # Python virtual environment (not committed)
└── .gitignore                  # Git ignore rules
```

---

## Database Schema

## Person (Permanent human record)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PK | Primary key |
| name | String(120) | Not Null | Full name |
| email | String(120) | Unique, Not Null | Email address (login contact) |
| birthday | Date | Nullable | Date of birth |
| address | String(255) | Nullable | Home address |
| contact_number | String(40) | Nullable | Phone number |
| emergency_contact | String(255) | Nullable | Emergency contact info |
| course_year | String(120) | Nullable | Course and year (e.g., "BSDC-4") |
| photo_path | String(255) | Nullable | Photo file path |
| cannot_reapply | Boolean | Default False | Cannot reapply after Failed/Expelled |
| created_at | DateTime | Default now() | Record creation timestamp |

## User (Login account, 1:1 with Person)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PK | Primary key |
| person_id | Integer | FK → Person.id, Unique | Links to Person |
| username | String(80) | Unique, Not Null | Login username |
| password_hash | String(255) | Not Null | Hashed password |
| is_active | Boolean | Default True | Account active status |
| must_change_password | Boolean | Default True | Force password change at next login |

## SchoolYear

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PK | Primary key |
| label | String(20) | Unique, Not Null | Year label (e.g., "2026-2027") |
| is_active | Boolean | Default False | Currently active year |

## Semester

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PK | Primary key |
| school_year_id | Integer | FK → SchoolYear.id | Parent year |
| name | String(20) | Not Null | Semester name ("Sem 1", "Sem 2", "Midyear") |
| is_active | Boolean | Default False | Currently active semester |

## Residency (Person IN a SchoolYear)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PK | Primary key |
| person_id | Integer | FK → Person.id | Permanent human |
| school_year_id | Integer | FK → SchoolYear.id | Which year |
| status | String(30) | Default "active" | active/retained/waitlisted/etc. |
| joined_at | Date | Nullable | First day counted (mid-year joiners) |
| left_at | Date | Nullable | Left date (soft-delete) |

## Room (Fixed dorm room)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PK | Primary key |
| name | String(80) | Unique, Not Null | Room name (e.g., "Melbourne") |
| capacity | Integer | Not Null | Number of beds |

## RoomAssignment (Who sleeps where, per semester)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PK | Primary key |
| residency_id | Integer | FK → Residency.id | Occupant |
| room_id | Integer | FK → Room.id | Room |
| semester_id | Integer | FK → Semester.id | Semester |
| is_big_brod | Boolean | Default False | The one stayer per room |
| move_reason | String(255) | Nullable | Reason for move |

## Role (Named bundle of permissions)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PK | Primary key |
| name | String(80) | Unique, Not Null | Role name |
| permissions | JSON | Default [] | List of permission strings |
| description | String(255) | Nullable | Description |

## RoleAssignment (Person has role in year)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PK | Primary key |
| residency_id | Integer | FK → Residency.id | Occupant |
| role_id | Integer | FK → Role.id | Role |
| school_year_id | Integer | FK → SchoolYear.id | Year |
| is_active | Boolean | Default True | Currently active |
| assigned_by | Integer | Nullable | Who assigned |

## PermissionGrant (Extra per-person permission)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PK | Primary key |
| residency_id | Integer | FK → Residency.id | Occupant |
| permission | String(80) | Not Null | Permission name |
| allow | Boolean | Default True | Allow or deny |
| expires_at | DateTime | Nullable | Expiration date |

## Setting (Editable system settings)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PK | Primary key |
| key | String(80) | Unique, NotNull | Setting key |
| value | String(255) | Not Null | Setting value |
| description | String(255) | Nullable | Description |

## AuditLog (Append-only change trail)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PK | Primary key |
| actor_id | Integer | Nullable | Who performed action |
| action | String(80) | Not Null | Action name |
| table_name | String(80) | Nullable | Table affected |
| record_id | Integer | Nullable | Record ID |
| old_value | Text | Nullable | Old value (JSON) |
| new_value | Text | Nullable | New value (JSON) |
| reason | String(255) | Nullable | Reason for change |
| created_at | DateTime | Default now() | When change occurred |

## Phase 2 Tables (HRAR + Violations)

### ViolationRule (HRAR catalog rule)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PK | Primary key |
| code | String(10) | Unique, Not Null | Rule code (e.g. 2.B) |
| section | Integer | Not Null | HRAR section number |
| section_title | String(120) | Nullable | Section title |
| title | String(200) | Not Null | Rule title |
| description | Text | Nullable | Rule text |
| severity | String(30) | Nullable | Severity label |
| points | Integer | Nullable | Points if confirmed |
| fine_type | String(40) | Nullable | none/fixed/per_day/per_month/per_incident |
| fine_amount | Integer | Nullable | Fine amount (PHP) |
| fine_meta | JSON | Nullable | Extra fine metadata |
| escalation | JSON | Nullable | Escalation ladder JSON |
| who_can_log | JSON | Nullable | Roles allowed to log |
| is_confidential | Boolean | Nullable | Confidential rule flag |
| confirmation | String(20) | Nullable | auto_48h / adviser |
| applies_when | String(20) | Nullable | always / closed_week |
| version | Integer | Nullable | Current version |
| is_active | Boolean | Nullable | Active rule |
| review_note | String(10) | Nullable | Review note |
| requires_victim_complaint | Boolean | Nullable | Requires victim complaint |
| penalty_options | JSON | Nullable | Penalty options |
| other_penalty | JSON | Nullable | Other penalty metadata |
| auto_source | String(30) | Nullable | Auto source label |
| note | Text | Nullable | Notes |

### RuleVersion (immutable snapshot on edit)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PK | Primary key |
| rule_id | Integer | FK -> ViolationRule.id | Rule |
| snapshot | JSON | Not Null | Full rule snapshot |
| changed_by | Integer | Nullable | Actor |
| changed_at | DateTime | Nullable | Changed timestamp |
| reason | String(255) | Nullable | Reason |

### ViolationRecord (one logged offense)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PK | Primary key |
| rule_id | Integer | FK -> ViolationRule.id | Rule |
| residency_id | Integer | FK -> Residency.id | Accused occupant |
| semester_id | Integer | FK -> Semester.id | Semester |
| reporter_id | Integer | Nullable | Reporter (NULL if anonymous) |
| is_anonymous | Boolean | Nullable | Anonymous flag |
| date | Date | Not Null | Incident date |
| time | Time | Nullable | Incident time |
| place | String(120) | Nullable | Place |
| notes | Text | Nullable | Notes |
| photo_path | String(255) | Nullable | Uploaded photo path |
| offense_count | Integer | Nullable | Nth offense this rule/semester |
| status | String(20) | Nullable | Logged/Confirmed/Dismissed/Under Review |
| confirmed_by | Integer | Nullable | Confirmer |
| confirmed_at | DateTime | Nullable | Confirmed timestamp |
| auto_confirm_at | DateTime | Nullable | Auto-confirm time (minor) |
| fine_amount | Integer | Nullable | Fine amount |
| fine_charge_id | Integer | Nullable | Phase 3 Charge link (stub now) |
| chosen_penalty | JSON | Nullable | Chosen penalty |
| notified_at | DateTime | Nullable | Notice timestamp |
| created_at | DateTime | Nullable | Created timestamp |

### Dispute

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PK | Primary key |
| violation_id | Integer | FK -> ViolationRecord.id | Violation |
| filed_by | Integer | Not Null | Filer (occupant) |
| reason | Text | Not Null | Dispute reason |
| filed_at | DateTime | Nullable | Filed timestamp |
| reviewed_by | Integer | Nullable | Reviewer |
| decision | String(20) | Nullable | upheld/dismissed |
| decision_reason | Text | Nullable | Decision reason |
| decided_at | DateTime | Nullable | Decision timestamp |

### EscalationFlag

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer | PK | Primary key |
| residency_id | Integer | FK -> Residency.id | Occupant |
| type | String(30) | Not Null | probation/expulsion_flag |
| reason | String(255) | Not Null | Reason |
| violation_id | Integer | FK -> ViolationRecord.id | Triggering violation |
| resolved | Boolean | Nullable | Resolved flag |
| created_at | DateTime | Nullable | Created timestamp |

---


---

## Routes & Endpoints Reference

## Authentication (`app/auth/routes.py`)

| URL | Methods | Auth Required | Description |
|-----|---------|---------------|-------------|
| `/login` | GET, POST | No | Login page - username/password form |
| `/logout` | GET | Yes | Log out current user |
| `/change-password` | GET, POST | Yes | Change password (forced on first login) |
| `/create-account` | GET, POST | Yes (`role.assign`) | Create new account (adviser only) |
| `/forgot` | GET, POST | No | Password reset request (email link) |
| `/reset/<token>` | GET, POST | No | Password reset from email link |
| `/bootstrap` | GET, POST | No | **One-time** first account creation (404 after first user exists) |
| `/seed-roles` | GET | Yes (`role.assign`) | Seed role catalog (404 once complete) |
| `/seed-rooms` | GET | Yes (`schoolyear.manage`) | Seed room catalog (404 once complete) |
| `/seed-settings` | GET | Yes (`schoolyear.manage`) | Seed settings catalog (404 once complete) |

## Roster & Management (`app/roster/routes.py`)

| URL | Methods | Auth Required | Description |
|-----|---------|---------------|-------------|
| `/admin/roles` | GET | `role.assign` | List occupants with roles; edit roles |
| `/admin/roles/<id>` | GET, POST | `role.assign` | Edit roles/grants for one occupant |
| `/roster/rooms` | GET | `roster.view` | List rooms with occupancy bars |
| `/roster/rooms/<id>` | GET, POST | `roster.view` | Room detail: assign occupants, Big Brod flag |
| `/roster/import` | GET, POST | `roster.edit` | CSV import with dry-run preview |
| `/roster/export` | GET | `roster.export` | CSV export of all occupants |
| `/roster/remove/<id>` | POST | `roster.edit` | Soft-delete occupant (set status=former) |
| `/roster/restore/<id>` | POST | `roster.edit` | Reactivate soft-deleted occupant |
| `/admin/settings` | GET, POST | `settings.view` | Settings page (grouped editable values) |
| `/admin/audit` | GET | `audit.view` | Audit log (filterable by action/actor) |
| `/admin/school-year` | GET, POST | `schoolyear.manage` | Create year/semester; activate year/semester |
| `/admin/school-year/<id>/activate` | POST | `schoolyear.manage` | Activate a specific year |
| `/admin/semester/<id>/activate` | POST | `schoolyear.manage` | Activate one semester within a year |
## Violations (`app/violations/routes.py`)

| URL | Methods | Auth Required | Description |
|-----|---------|---------------|-------------|
| `/violations/rules` | GET | `violations.view` | HRAR rules catalog list |
| `/violations/rules/add` | GET, POST | `violations.confirm` | Add rule (creates RuleVersion) |
| `/violations/rules/<id>/edit` | GET, POST | `violations.confirm` | Edit rule (creates RuleVersion, bumps version) |
| `/violations/rules/<id>/history` | GET | `violations.view` | Rule version history |
| `/violations/log` | GET, POST | `violations.log` | Log violation (multi-occupant, photo upload) |
| `/violations/review` | GET, POST | `violations.confirm` | Adviser review queue (confirm/dismiss) |
| `/violations/mine` | GET | login | Occupant's own violations |
| `/violations/dispute/<id>` | GET, POST | login | File dispute (within dispute window) |
| `/violations/disputes` | GET | `violations.confirm` | Dispute queue |
| `/violations/disputes/decide/<id>` | GET, POST | `violations.confirm` | Decide dispute (President + advisers) |
| `/jobs/auto-confirm` | GET | `violations.confirm` | Run minor 48h auto-confirm job |
| `/seed-hrar` | GET | `violations.confirm` | Seed HRAR catalog (404 once complete) |

---


---


---

## Blueprint Structure

| Blueprint | URL Prefix | Responsibility |
|-----------|-----------|----------------|
| `auth` | (root) | Login, logout, register, forgot/reset password, bootstrap, seed routes |
| `roster` | (root) | Rooms, roles, settings, audit, school years, import/export |
| `violations` | (root) | HRAR rules, violation log/review/mine/disputes, auto-confirm job |

Both blueprints register on the root URL prefix (`/`), so routes like `/login`, `/admin/roles`, `/roster/rooms` are at the root level. Blueprints are registered in the factory (`app/__init__.py`).

---

## Authentication System

## Login Flow

1. User visits `/login`
2. Submits username + password via POST (with CSRF token from `{{ form.hidden_tag() }}`)
3. System looks up user by `username` (lowercased before lookup)
4. Verifies password hash using Werkzeug `check_password_hash`
5. Checks `is_active` flag — inactive accounts cannot log in (same generic error as wrong password: "Invalid username or password.")
6. On success: `login_user()`, writes `user.login` audit row, then:
   - If `must_change_password=True`: redirect to `/change-password`
   - Else: redirect to `/me` (or `?next=` target)

## Password Reset Flow

1. User visits `/forgot`, enters email
2. System looks up Person by email, signs a **1-hour timed token** (itsdangerous `URLSafeTimedSerializer` with `SECRET_KEY` + `SECURITY_PASSWORD_SALT`)
3. Sends reset link via email (dev: prints `[DEV EMAIL]` to console)
4. User opens `/reset/<token>` — token validated with `max_age=3600`
5. User enters new password → password hash updated, `must_change_password=False`, `password.reset.done` audit row

**Gotcha learned:** forgot-password resets the account matching the **email typed**, not the logged-in session. Also, reset does NOT check `is_active` — an inactive account can reset but still can't log in (reactivate via `/admin/roles`).

## Bootstrap (First Account)

- `/bootstrap` works ONLY while `User.query.count() == 0`
- Creates Person + User (`must_change_password=True`) + SchoolYear 2026-2027 + Sem1/Sem2 + Super-admin role + Residency + RoleAssignment + AuditLog in ONE commit
- After the first user exists, `/bootstrap` returns **404 permanently** (backdoor-safe)

## Account Lifecycle

- **Create:** `/create-account` (adviser/super-admin, `role.assign`) → temp password emailed (dev: console print)
- **Deactivate:** `/admin/users/<id>/deactivate` → `is_active=False` (never hard-delete, spec §5.1); self-deactivation blocked
- **Reactivate:** `/admin/users/<id>/reactivate`
- **Rollout:** all seeders (`/seed-roles`, `/seed-rooms`, `/seed-settings`) 404 once complete, and self-heal stale permission bundles on re-visit

---


---

## Permission System

## Permission Checking (`app/utils/decorators.py`)

All permission checks go through one central decorator:

- `@permission_required("finance.view")` placed on routes (AFTER `@login_required`)
- `has_permission(user, permission)` helper (also injected into templates as `can(permission)` via context processor)
- Checks the user's active `RoleAssignment`s **in the active school year** — roles stack, permissions add up
- `PermissionGrant` rows act as per-person overrides (allow/deny, with optional expiry; **deny beats allow**)
- **Super-admin bypass is global**: `_all_assignments()` checks ANY year, so switching the active year can never lock out the super-admin (lesson learned during year-activation testing)
- Unauthorized access writes an `auth.forbidden` AuditLog row and returns 403

## Built-in Roles (`app/roster/default_roles.py` — 17 roles, single source of truth)

| Role | Key Permissions |
|------|-----------------|
| **Super-admin** | `[]` — bypasses ALL checks by name |
| **Adviser** | roster.view/export/view_private/edit, role.assign, schoolyear.manage, finance.view/edit, violations.view/log/confirm, events.view/edit, cleaning.view/edit, evaluation.view/enter/lock/release, settings.view, audit.view, tickets.view, announcements.post, clearance.edit |
| **President** | roster.view/export/view_private, announcements.post, tickets.view, disputes.review |
| **Secretary** | roster.view/export/view_private, events.view/edit, evaluation.enter |
| **Assistant Secretary** | events.view, events.attendance |
| **Treasurer** | finance.view/edit/receipts/expenses |
| **Assistant Treasurer** | finance.view/edit/receipts/expenses |
| **Auditor** | finance.view, audit.view (read-only: no `.edit` perms anywhere) |
| **VP Internal / VP External** | announcements.post |
| **Justice head** | violations.log, tickets.view |
| **Kitchen head** | violations.log, tickets.view |
| **IGP head** | violations.log, tickets.view |
| **Repairs head** | tickets.view |
| **SA** | cleaning.view/edit, tickets.view, violations.log, clearance.room_inspect |
| **Evaluator (temp)** | evaluation.view (ends via `is_active=False` at results release) |
| **Occupant** | `[]` — own data is implicit from login + residency |

> **Dual-view rule (Plate 2B):** every officer/SA keeps the full occupant view ("My Dorm") plus extra authority tabs driven by `can(permission)`. Roles are per-year, stack, and are assigned ONLY by advisers/super-admin via `/admin/roles`. There is no self-assign.

## Known Permission Strings

Register any new permission in `KNOWN_PERMISSIONS` (`app/roster/forms.py`) so it appears in the grant datalist: `roster.*`, `role.assign`, `schoolyear.manage`, `finance.*`, `violations.*`, `events.*`, `cleaning.*`, `evaluation.*`, `settings.view`, `audit.view`, `tickets.view`, `announcements.post`, `disputes.review`, `clearance.*`.

---


---

## Template Reference

## Base Template (`app/templates/base.html`)

Bootstrap 5, maroon navbar (`#5E1A0E`), PWA manifest, `flash` messages, and permission-gated nav links via `can()`:

| Condition | Link Shown |
|-----------|------------|
| `can("roster.view")` | Rooms |
| `can("role.assign")` | Roles |
| `can("settings.view")` | Settings |
| `can("audit.view")` | Audit |
| `can("schoolyear.manage")` | Years |
| authenticated | Me, Logout |
| anonymous | Login |

Blocks: `{% block head %}`, `{% block title %}`, `{% block content %}`.

## Auth Templates (`app/templates/auth/`)

| Template | Purpose |
|----------|---------|
| `login.html` | Login form (username + password, `form.hidden_tag()` for CSRF) |
| `change_password.html` | Forced change: current + new + confirm |
| `create_account.html` | Adviser-only create account (name + email) |
| `forgot.html` | Request reset link (email) |
| `reset.html` | Set new password from token link |
| `bootstrap.html` | One-time first account page ("self-destructs") |
| `me.html` | Profile + authority badges + action bar (Settings/Back) |

## Roster Templates (`app/templates/roster/`)

| Template | Purpose |
|----------|---------|
| `roles.html` | Occupant list with role pills, deactivate/reactivate, filter active/inactive |
| `role_edit.html` | Role checkboxes + grants table + deactivate button for one occupant |
| `rooms.html` | 20 room cards with occupancy bars, vacancy badges, Big Brod ★, Import/Export buttons |
| `room_detail.html` | Bed slots + vacant rows, assign form (Big Brod unique guard), capacity edit |
| `import.html` | Two-step CSV import: preview (new/skipped/errors, per-room counts) → Commit with `stage_token` |
| `settings.html` | 4 grouped cards (Evaluation weights, Status rules, Violations, Finance) with per-group Save |
| `audit.html` | Filterable audit log table (action / actor / q), read-only |
| `create_school_year.html` | List years + semesters with Activate buttons, plus create-year form (Sem1+Sem2+optional Midyear) |

> Every form uses `{{ form.hidden_tag() }}` or explicit `csrf_token` — Flask-WTF `CSRFProtect` is global.

---


---

## Configuration & Environment

## Environment Variables (`.env` — local only, never committed)

| Variable | Description | Default (dev) |
|----------|-------------|---------------|
| `SECRET_KEY` | Flask secret key for sessions/CSRF | `dev-only-change-me` |
| `FLASK_APP` | Entry point for flask CLI | `run.py` |
| `FLASK_ENV` | Environment mode | `development` |
| `DATABASE_URL` | Database connection string | `sqlite:///zmmh.db` |
| `SECURITY_PASSWORD_SALT` | Salt for password-reset tokens | `zmmh-reset-dev` |
| `MAIL_SUPPRESS_SEND` | Don't send emails (dev prints to console) | `True` |
| `MAIL_SERVER` | SMTP server | `localhost` |
| `MAIL_PORT` | SMTP port | `25` |

## Config Classes (`config.py`)

| Class | Used When | Notes |
|-------|-----------|-------|
| `DevConfig` | Local (`FLASK_ENV != production`) | SQLite, `MAIL_SUPPRESS_SEND=True`, SECRET_KEY fallback |
| `ProdConfig` | Render (`FLASK_ENV=production`) | Postgres from `DATABASE_URL` env, **fails fast** if `SECRET_KEY` missing |

## Deploy Environment Variables (Render)

| Key | Value |
|-----|-------|
| `SECRET_KEY` | generate: `python -c "import secrets;print(secrets.token_hex(32))"` |
| `FLASK_APP` | `run.py` |
| `FLASK_ENV` | `production` |
| `DATABASE_URL` | Neon pooled string ending `?sslmode=require` |
| `MAIL_SUPPRESS_SEND` | `True` (until Gmail App Password configured) |

**Start command (Render):** `flask db upgrade && gunicorn run:app` — migrations run on every boot, no shell needed.

---

## Setup & Installation

```bash
git clone https://github.com/FoolishBookButterfly/zmmh-dorm-system.git
cd zmmh-dorm-system/zmmh

python -m venv venv
source venv/bin/activate       # Linux/Mac
# venv\Scripts\activate        # Windows

pip install -r requirements.txt
cp .env.example .env           # edit as needed

flask db upgrade               # apply migrations

python seed_roles.py           # 17 roles (or visit /seed-roles once on live)
python seed_rooms.py           # 20 rooms (or /seed-rooms)
python seed_settings.py        # 20 settings (or /seed-settings)

flask run                      # http://127.0.0.1:5000
```

**First-run order:** if the DB is completely fresh, visit `/bootstrap` first (creates superadmin + year + semesters), then `/seed-roles`, `/seed-rooms`, `/seed-settings` once each.

---


---

## Database Migrations

```bash
flask db migrate -m "description of change"   # create migration after model changes
flask db upgrade                              # apply migrations
flask db downgrade                            # rollback one migration
flask db current                              # show current revision
```

## Existing Migrations

| Revision | Description |
|----------|-------------|
| `1832d92c183b` | Phase 1 models (all 12 initial tables) |
| `b82d393e0f2c` | Phase 1.4: `residency.joined_at` / `left_at` columns |

**Rules:** never edit an applied migration; never delete the production DB — always migrate. SQLite FK naming convention is configured in `app/__init__.py` (the `fk_%(table_name)s_...` metadata) so Alembic batch-alter tables on SQLite don't crash.

---

## Seed Scripts

| Script | Run With | Idempotent | What it does |
|--------|----------|-----------|--------------|
| `seed_roles.py` | `exec(open("seed_roles.py").read())` in `flask shell` | Yes (creates missing + **updates stale permission bundles**) | 17 roles from `default_roles.py` + ensures active year/Sem1/Sem2 |
| `seed_rooms.py` | same | Yes | 20 rooms / 120 beds from `default_rooms.py` |
| `seed_settings.py` | same | Yes | 20 settings from `default_settings.py` |

Live-server equivalents (no shell needed): `/seed-roles`, `/seed-rooms`, `/seed-settings` — each **404s permanently once complete**, and re-visits self-heal permission bundles that drifted from the catalog. Audit-logged (`seed.roles`, etc.).

**Catalog pattern:** edit `app/roster/default_*.py` (single source of truth) → both shell scripts and seed routes stay in sync.

---


---

# Phase 2 Roadmap — HRAR Catalog + Violations Lifecycle

**Roadmap target: Nov 2–7** (spec §10). This is the trickiest logic in the system — get it right and evaluation (Phase 5) becomes easy. Spec source: §5.4 + decisions §2 items 2, 5, 8.

## What Phase 2 Delivers

1. **HRAR rule catalog** — CRUD for `ViolationRule` + versioned edits (`RuleVersion`)
2. **Violation logging** — one or more occupants, date/time/place/notes/photo
3. **Lifecycle** — `Logged` → `Confirmed`/`Dismissed`, with 48-hour auto-confirm for minors
4. **Disputes** — occupant files within 3 days (editable setting) → `Under Review`, points paused
5. **Escalation flags** — offense counts per rule per semester raise a flag for adviser decision (NEVER auto-probation/expulsion)
6. **Confidential cases** — visible only to advisers, Justice head, and parties involved

## New Models (spec §9 — Violations block)

| Model | Key Fields |
|-------|-----------|
| `ViolationRule` | code (e.g. "2.B"), section, title, description, points, fine_type (none/fixed/per_day/per_month/per_incident), fine_amount, escalation JSON, who_can_log list, is_confidential |
| `RuleVersion` | rule_id, snapshot JSON, changed_by, changed_at (edits never mutate history) |
| `ViolationRecord` | rule_id, residency_id, reporter_id, date, time, place, notes, photo_path, offense_count (auto: prior confirmed count for same rule+semester + 1), status (Logged/Confirmed/Dismissed/Under Review), confirmed_by/at, auto_confirm_at, fine_charge_id, is_anonymous |
| `Dispute` | violation_id, filed_by, reason, filed_at, reviewed_by, decision, decision_reason |
| `EscalationFlag` | residency_id, type (probation/expulsion_flag), reason, resolved |

## Permission Strings to Add

`violations.view`, `violations.log`, `violations.confirm` — **already seeded** in Adviser/Justice/Kitchen/IGP/SA bundles (Phase 1.3). New rule-scoped enforcement is route-level, not new permissions: Justice head logs all rules, Kitchen head = Section 5 only, IGP = charging-schedule confiscations (₱50), SAs = general.

## Build Order (follow 1.2/1.4 step rhythm)

| Step | Deliverable |
|------|-------------|
| 2.1 | `app/roster/default_hrar.py` (cleaned HRAR catalog — **fix the duplicate "Section 9" title + lettering per spec §5.4**) + 5 new models + migration `phase2 violations` + `seed_hrar.py` + one-shot `/seed-hrar` |
| 2.2 | `/violations/rules` admin (list + add/edit creating `RuleVersion` snapshots; editable fines; who-may-log enforced) |
| 2.3 | `/violations/log` form (multi-occupant, rule dropdown filtered by permission, photo upload via Pillow ≤1280px, creates `ViolationRecord` status=Logged, computes `offense_count` + `auto_confirm_at`, notifies occupant) |
| 2.4 | Review queue `/violations/review` (adviser Confirm/Dismiss with reason → audit) + daily auto-confirm job (48h minors) + fine → `Charge` hand-off stub (real Charge lands Phase 3) |
| 2.5 | Disputes: occupant `/violations/dispute/<id>` within `dispute_days` setting → Under Review (points paused), President+advisers decide (reviewer ≠ reporter ≠ accused), confidential visibility filter |
| 2.6 | E2E tests: minor auto-confirms at 48h, major blocks, dispute pauses points, escalation flag raises at threshold, offense_count increments per rule+semester, Kitchen head can't log non-Section-5 |

## Key Rules (from spec §5.4 — do not paraphrase away)

- **Points count only when Confirmed** (HRAR = 100 − Σ confirmed deductions; `Under Review` pauses them)
- **48h auto-confirm** applies ONLY if: points ≤ 3 AND no escalation AND fine < ₱50 AND not confidential — everything else needs an adviser
- **Escalation never punishes automatically** — flags only (third curfew violation, 21 cleaning absences, etc.)
- **Confidential types** (stealing, sexual harassment, marked-confidential): visibility = advisers + Justice head + involved parties ONLY
- **Make-up general cleaning** cancels 5pts + ₱50 (decision 8) — wire when cleaning exists
- Loggers: Justice head (all), Kitchen head (Sec 5), IGP (charging confiscations + ₱50), advisers, SAs, and occupants via tickets (convert anonymous tickets → violations, reporter hidden except advisers/Justice head/President)

## Reusable Patterns from Phase 1 (do not reinvent)

- **Catalog pattern**: `default_hrar.py` + shell seeder + one-shot `/seed-hrar` (404 when complete, self-heal on revisit)
- **Blueprint**: add `app/violations/` blueprint registered in factory, OR extend `roster_bp` if small — prefer **new blueprint** `violations_bp` with prefix `/violations`
- **Permission gate**: `@login_required` + `@permission_required("violations.log")` etc.
- **Audit**: every Confirm/Dismiss/Dispute decision writes `AuditLog` with reason (spec: scores/money changes REQUIRE reason)
- **Settings**: read `dispute_days`, `auto_confirm_hours` via `utils/settings.py` `get_int_setting()` — never hardcode
- **Photos**: Pillow compress to max 1280px on upload (spec §7), store under `app/static/uploads/` (gitignored)
- **Tests**: throwaway-DB script style used in Phases 1.3–1.5 (create user → login with CSRF token from GET → assert → cleanup with committed deletes)

## Definition of Done (Phase 2)

- [ ] Rule catalog editable with version history
- [ ] Log violations for 1+ occupants, permission-filtered rule dropdown, photo upload
- [ ] 48h auto-confirm for minors; adviser confirm for majors; fines create Charges
- [ ] Dispute window (3 days) pauses points and works for occupants
- [ ] Escalation flags raise, never auto-punish
- [ ] Confidential visibility enforced in list + detail queries
- [ ] All changes audit-logged; E2E tests green; pushed to `main` (Render auto-deploys + auto-migrates)

---


---

## Common Tasks & Troubleshooting

### Adding a New Model

1. Define model in `app/roster/models.py` (or a new `app/<module>/models.py` + import it in the factory so Migrate sees it)
2. `flask db migrate -m "description"` then `flask db upgrade`
3. Add routes (new blueprint preferred) + templates
4. Gate routes: `@login_required` + `@permission_required("perm")`
5. Log changes via `_audit()` / `AuditLog`

### Adding a New Permission

1. Add string to `KNOWN_PERMISSIONS` in `app/roster/forms.py` (grants datalist)
2. Add to role bundle(s) in `app/roster/default_roles.py`
3. Re-run `seed_roles.py` (shell) or `/seed-roles` (live) — stale bundles self-heal
4. Apply `@permission_required("new.perm")` to the route

### Adding a New Setting

1. Add entry to `SETTINGS` in `app/roster/default_settings.py`
2. Run `seed_settings.py` or visit `/seed-settings`
3. Read via `get_setting()` / `get_int_setting()` in `app/utils/settings.py` — NEVER hardcode

### Troubleshooting Table

| Problem | Cause / Fix |
|---------|-------------|
| `Working outside of application context` | Wrap shell/script code in `with app.app_context():` |
| Empty migration generated | Save models first, delete bad file, re-run `flask db migrate` |
| `Constraint must have a name` (SQLite) | Naming convention already set in factory; don't remove it |
| Circular import | Import `db` from `app` only; keep model imports inside factory |
| `CSRF token is missing` (400 on POST) | Add `{{ form.hidden_tag() }}` (or explicit `csrf_token`) to the form |
| Gmail login blocked | Use Gmail App Password (2FA on) or dev console-print mode |
| Render SQLite wiped | SQLite is ephemeral on Render — use Neon Postgres (`DATABASE_URL`) |
| Permission 403 for super-admin | Super-admin bypass is global by design — if it fails, check `RoleAssignment.is_active` and role name is exactly `Super-admin` |
| Seeded role missing a permission | Re-run seed (bundles self-heal on mismatch) — editing `default_roles.py` alone is not enough |
| `ObjectDeletedError` in tests | Capture scalar IDs (`pid, uid, rid = ...`) BEFORE deleting rows; always `db.session.commit()` after deletes (session teardown rolls back uncommitted work) |
| Import file "missing" at commit | Staged upload expired (15 min) — re-run Preview |
| Reset works but login fails | You reset a DIFFERENT account (forgot works by email typed), or `is_active=False` — check both |

### Testing Discipline (learned the hard way)

1. **CSRF:** tests must GET the form first and send the extracted `csrf_token` (or set `WTF_CSRF_ENABLED=False` only for pure unit tests — never for route tests).
2. **Cleanup:** delete test rows WITH `db.session.commit()` — context teardown otherwise rolls deletes back and the next run crashes on UNIQUE.
3. **Dates:** expect `2026-2027` live, not the system clock — assertions using `datetime.now()` will fail.
4. **Order matters:** seeders must run before roles UI tests (empty `Role` table → empty checkboxes → phantom 403s).

---

## Local Development & Testing (Phase 2)

### Prerequisites

- Python 3.11+ with venv.
- Install dependencies: `pip install -r requirements.txt`
- Copy `.env.example` to `.env` (if present) and set `SECRET_KEY`, `SECURITY_PASSWORD_SALT`, mail settings.

### First run (fresh database)

1. Create DB: `flask db upgrade` (or `python -m flask db upgrade`)
2. Seed roles: visit `/seed-roles` (or run `python seed_roles.py`)
3. Seed rooms: visit `/seed-rooms` (or `python seed_rooms.py`)
4. Seed settings: visit `/seed-settings` (or `python seed_settings.py`)
5. Seed HRAR catalog: visit `/seed-hrar` (or `python seed_hrar.py`)
6. Bootstrap first account: visit `/bootstrap` and create the super-admin (one-time; 404 afterwards).

### Superadmin test account (always-on for local testing)

- **Username:** `superadmin`
- **Password:** `testpass`
- **Role:** `Super-admin` (global bypass)
- **Status:** active, no forced password change.
- This account is the local dev super-admin (User id 1). If the DB is recreated, re-run `/bootstrap` or `prep_superadmin.py` to restore it.
- Helper scripts in `zmmh/`:
  - `prep_superadmin.py` — resets User 1 password to `testpass` and activates it.
  - `reset_pw.py` — resets User 2 password to `testpass`.
- Do **not** commit real passwords or use these in production.

### Running the app

- Dev server: `python run.py` (or `flask run`)
- App URL: `http://127.0.0.1:5000/`
- Login: `/login`

### Key URLs (Phase 1 + Phase 2)

- Auth: `/login`, `/logout`, `/change-password`, `/create-account`, `/forgot`, `/reset/<token>`, `/bootstrap`
- Seeders: `/seed-roles`, `/seed-rooms`, `/seed-settings`, `/seed-hrar`
- Roster: `/admin/roles`, `/admin/roles/<id>`, `/roster/rooms`, `/roster/rooms/<id>`, `/roster/import`, `/roster/export`, `/roster/remove/<id>`, `/roster/restore/<id>`
- Admin: `/admin/settings`, `/admin/audit`, `/admin/school-year`, `/admin/school-year/<id>/activate`, `/admin/semester/<id>/activate`
- Violations: `/violations/rules`, `/violations/rules/add`, `/violations/rules/<id>/edit`, `/violations/rules/<id>/history`, `/violations/log`, `/violations/review`, `/violations/mine`, `/violations/dispute/<id>`, `/violations/disputes`, `/violations/disputes/decide/<id>`, `/jobs/auto-confirm`

### Running tests

- Violations E2E: `python -m pytest tests/test_violations_e2e.py -q` (expected: 6 passed)
- Smoke scripts (manual, creates test data — clean up afterwards):
  - `python create_test_rec.py`
  - `python smoke_dispute.py`, `python smoke_dispute2.py`, `python smoke_decide.py`
  - `python inspect_users.py`

### Phase 2 verification checklist

- [x] HRAR catalog seeded (57 rules, sections 1-8)
- [x] Rule add/edit creates `RuleVersion` + bumps version + audit log
- [x] Violation log computes `offense_count` and `auto_confirm_at`
- [x] Photo upload shrinks to <=1280px JPEG
- [x] Anonymous reporter stored as `reporter_id=NULL`
- [x] Auto-confirm job confirms eligible minor violations after 48h
- [x] Escalation flags created at configured thresholds
- [x] Dispute moves record to `Under Review` and pauses points
- [x] Dispute window enforced (`dispute_days` setting)
- [x] Reviewer cannot be reporter or accused
- [x] Confidential rules restricted to advisers/Justice head/President
- [x] Kitchen head restricted to Section 5
- [x] Phase 2 E2E tests green (6/6)

### Git: commit and push (manual)

Local commit already created for Phase 2. To push to GitHub:

```bash
cd "c:/Users/Lenovo T14/Documents/Dormitory/ZmMH Dormitory Management System"
git status
git add -A
git commit -m "Phase 2 complete: HRAR catalog + violations lifecycle"
git push origin main
```

If `git push` fails with "Repository not found" or an auth prompt:

1. Complete the browser login opened by Git Credential Manager.
2. Re-run `git push origin main`.
3. If still failing, check remote: `git remote -v` (expected `https://github.com/FoolishBookButterfly/ZmMH-Dormitory-Management-System.git`).
4. Ensure the GitHub account has push access to the repo.
5. Never commit `.env`, `*.db`, `instance/`, or `app/static/uploads/*` (gitignored).

### Phase 3: Money - Charges, Payments, Receipts (next)

Goal: replace `_charge_stub()` with real `Charge` creation and build finance flows.

Planned work:

1. Models (new migration): `ChargeType`, `Charge`, `Payment`, `PaymentAllocation`, `Receipt`, `Expense`, `Budget`, `FeeWaiver`.
   - `Charge`: residency_id, amount, source_violation_id (nullable), semester_id, is_waived.
   - `Payment`: residency_id, amount, received_by.
   - `PaymentAllocation`: payment_id, charge_id, amount (FIFO oldest-first).
   - `Receipt`: payment_id, receipt_no (e.g. 2026-0001).
2. Auto-create maintenance `Charge` (PHP 700/semester) per active residency when a semester is activated.
3. Violation confirm auto-creates a fine `Charge` (replace `_charge_stub()` in `app/violations/routes.py`).
4. Treasurer routes (permission `finance.edit`):
   - Record payment: select occupant, amount, allocate oldest-first, generate receipt number, audit.
   - Partial payments allowed.
   - Balance = sum(charges) - sum(allocations).
5. Receipt printable page + reports: balance, collection %, unpaid list, monthly income/expense, CSV/PDF export.
6. SA expenses unverified until Treasurer checks (`Expense.is_verified`).
7. Waivers adviser-only with reason (`FeeWaiver.approved_by`, `reason`).
8. Tests: 700+50 charges, pay 500, verify 250 balance, print receipt, export CSV.

Suggested build order:

- 3.1 Add models + migration + seed charge types.
- 3.2 Implement `charge.create_from_violation()` and call from violation confirm.
- 3.3 Implement maintenance charge auto-creation on semester activation.
- 3.4 Record payment route + FIFO allocation + receipt numbering.
- 3.5 Receipt view + reports + CSV export.
- 3.6 Expenses + verification + waivers.
- 3.7 E2E tests.

Do not start Phase 3 until Phase 2 commit is pushed (or at least committed locally).

---

## Important Rules for Contributors

- **Never delete production data** — use Flask-Migrate for schema changes
- **Never commit `.env`** or `*.db` (both gitignored)
- **Never hardcode** editable values — they live in `Setting` (§7)
- **Every route** gets `@login_required` + `@permission_required(...)`
- **Every state change** writes an `AuditLog` row; scores/money changes REQUIRE `reason`
- **Model names are frozen** — spec §9 names (`Person`, `Residency`, `ViolationRecord`, ...) must never be renamed
- **Design plates** in `design/preview.html` are the UI source of truth (Plate 2B dual-view rule especially)

---

*Generated for ZmMH Dormitory Management System — Phase 2 complete. Roadmap: `ROADMAP-Flask-Build-Guide.md` · Spec: `ZmMH Dormitory Management System Requirements (Draft 1).md`*

