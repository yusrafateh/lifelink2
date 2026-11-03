# LifeLink - Cloud-Based Emergency Blood Donor Matching System
Cloud Computing CEP Project - MUET SZAB Campus, Khairpur Mir's

LifeLink connects patients/hospitals that urgently need blood with nearby, medically
eligible donors. A request is accepted instantly by the REST API and matched to donors
**in the background by multiple worker threads**; donors accept/decline, and the
requester sees donor contact details only after a donor accepts.

## 1. Run on your own computer (Windows / Linux / Mac)
```bash
python --version                 # needs Python 3.9+
python -m venv venv
venv\Scripts\activate            # Windows      (Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt
python app.py
```
Open **http://127.0.0.1:5000**

Demo accounts (password for all: `Password123`):

| Role | Email |
|------|-------|
| Admin | admin@lifelink.pk |
| Donor (O+, Karachi) | ali@demo.pk |
| Donor (O-, Karachi) | sara@demo.pk |
| Requester / Hospital | ayesha@demo.pk |

### 2-minute demo script for the teacher
1. Login as **ayesha@demo.pk** -> Request Blood: O+, 1 unit, Karachi, urgency *critical*.
2. Watch status go `pending -> matching -> open` automatically (background threads). "donors notified: 2".
3. Logout, login as **ali@demo.pk** -> see the request -> **Accept**.
4. Login again as ayesha -> status is `fulfilled` and Ali's phone number is now visible.
5. Login as **admin@lifelink.pk** -> dashboard shows users, requests, notifications, active worker threads.

## 2. Run the automated tests
```bash
python -m unittest discover -s tests -t . -v      # 23 tests
```

## 3. Project structure (MVC)
```
app.py                       entry point (+ demo seed data)
seed.py                      demo users
lifelink/
  __init__.py                application factory, security headers, /health
  config.py                  settings from environment variables
  db.py                      SQLite connection + schema
  models/                    M - user_model, request_model, notification_model (all SQL)
  controllers/               C - auth_controller, request_controller, admin_controller (REST API)
  services/                  business logic: matching.py (rules), auth.py (tokens/RBAC/rate-limit),
                             worker.py (multithreaded background matching)
  templates/ + static/       V - single-page web UI (HTML/CSS/JS)
tests/test_api.py            23 automated tests
Dockerfile, Procfile, render.yaml   cloud deployment artefacts
```

## 4. REST API summary
| Method & path | Who | Purpose |
|---|---|---|
| POST /api/auth/register | public | create donor/requester account |
| POST /api/auth/login | public | returns signed token (rate-limited) |
| GET/PUT /api/me | any user | view/update profile |
| POST /api/requests | requester | create request (returns 202, matching is async) |
| GET /api/requests/mine | requester | my requests + accepted donors |
| POST /api/requests/{id}/cancel | requester (owner) | cancel |
| GET /api/notifications | donor | requests I was matched to |
| POST /api/notifications/{id}/respond | donor | `{"response":"accept"}` or `decline` |
| GET /api/admin/stats, /users, /requests | admin | monitoring |
| POST /api/admin/users/{id}/toggle | admin | enable/disable account |
| GET /health | public | health check for the cloud platform |

## 5. Deploy to the cloud
See **DEPLOYMENT.md** (Render.com free tier, Docker, or AWS EC2).
Always set a strong `SECRET_KEY` environment variable in the cloud.
