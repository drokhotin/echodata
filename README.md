# EchoData

Flask application for clinical records and echocardiography workflows, including configurable forms, DICOM SR extraction, attachments, and ward status.

## Security-first setup

EchoData processes sensitive health data. Do not deploy it using source-code defaults or with production patient data until your organization has completed a security, privacy, and regulatory review.

```bash
cp .env.example .env
# Edit .env: all required values must be set before startup.
python3 -m venv .venv
source .venv/bin/activate
python -m pip install Flask python-dotenv peewee PyMySQL requests jinja-try-catch \
  Babel python-dateutil bleach html2text Markdown Flask-SSLify Flask-Mail \
  openai pandas openpyxl pydicom pynetdicom
flask --app echodata:app run
```

The project has no migration framework or dependency lockfile. Provision the database and create its schema through a reviewed migration/bootstrap process before running it. Do not use the placeholder values in `.env.example`.

## Required configuration

`SECRET_KEY`, `ADMINS`, `DATABASE_URL`, `UPLOAD_FOLDER`, and all four `DICOM_*` variables are required at startup. The application fails closed when they are absent. `SESSION_COOKIE_SECURE=True` is the production default; set it to `False` only for local HTTP development.

AI access is disabled by default. It requires both `OPENAI_API_KEY` and `AI_ALLOW_PHI=True`; enable it only after your organization has approved the provider and data-processing arrangement.

## Security hardening in this branch

- Removes embedded integration credentials, clinical-network addresses, database credentials, and the fallback session secret.
- Uses Werkzeug PBKDF2-SHA256 password hashes; legacy SHA-256 hashes are upgraded after a successful interactive login.
- Requires authenticated administrator access for DICOM routes.
- Requires authenticated JSON POST requests for EchoView integration routes.
- Restricts record and attachment access to the record author or an administrator.
- Changes attachment deletion to CSRF-protected POST.
- Adds secure session defaults and a 16 MiB request-size limit.

Further work is still required before production use: database migrations, comprehensive CSRF coverage, role/ward-based authorization designed for the organization, audit logging, rate limiting, automated tests, backups, and formal compliance controls.
