# CV Personalizer

A local-first workspace for managing résumé versions, tailoring applications,
building cover letters, researching companies, and tracking job applications.

## Features

- Section-by-section résumé editor with PDF preview and export
- Version history and per-application résumé tracking
- Job application pipeline with statuses, notes, links, and dates
- AI-assisted résumé tailoring
- Multi-step cover-letter analysis, company research, clarification, drafting,
  editing, and PDF export
- Standalone, source-backed company research reports
- Persistent local SQLite storage

## Privacy model

The application is designed for local use. Résumés, applications, cover
letters, uploaded images, signatures, and API keys are private and are excluded
from Git and Docker build contexts.

Runtime data lives in the ignored `local-data/` directory:

```text
local-data/
├── resume.db
├── backups/
└── static/
    ├── profile.jpg
    └── documents/
        └── signature.png
```

A fresh clone starts with a neutral example résumé. It does not contain the
maintainer's résumé or contact information.

> The API has no authentication. Keep it bound to your own machine or add an
> authentication layer before exposing it to a network or public host.

## Docker quick start

1. Create a private environment file:

   ```bash
   cp backend/.env.example backend/.env
   ```

2. Add whichever API keys you want to use. AI features are optional.

3. Start the application:

   ```bash
   docker compose up --build
   ```

4. Open:

   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API documentation: http://localhost:8000/docs

Docker bind-mounts `local-data/` into `/app/data`, so rebuilding or recreating
the containers does not remove your application data.

## Local development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
nvm use
npm install
npm run dev
```

The frontend expects Node.js 22 or newer.

Without an override, local development and Docker both use the repository's
ignored `local-data/` directory. Set `CV_PERSONALIZER_DATA_DIR` if you want a
different location.

## Optional AI configuration

Copy `backend/.env.example` to `backend/.env` and configure:

```dotenv
GEMINI_API_KEY=your_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_COMPANY_RESEARCH_MODEL=gpt-5.6-sol
```

LangChain's Gemini integration powers résumé suggestions and tailoring.
LangGraph orchestrates the OpenAI cover-letter and company-research workflows,
using LangChain's Responses API integration, structured output, and web search.

## Backing up local data

SQLite's backup command creates a consistent snapshot while preserving the
active database:

```bash
mkdir -p local-data/backups
sqlite3 local-data/resume.db \
  ".backup 'local-data/backups/resume-backup.db'"
```

Keep `local-data/` out of Git. Do not run `git clean -fdX` in this repository:
that command deletes ignored files, including local application data.

## Tests

```bash
python -m unittest discover -s backend/tests -v

cd frontend
npm test
npm run lint
npm run build
```

## Project structure

```text
.
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── sql/
│   │   ├── schema.sql
│   │   └── migrations/
│   ├── sample_data/
│   │   └── default_resume.json
│   ├── routers/
│   └── templates/
├── frontend/
│   ├── src/
│   └── tests/
├── local-data/              # Private and ignored
└── docker-compose.yml
```

The repository contains genuine Python, JavaScript, CSS, HTML, and SQL source.
GitHub calculates its language percentages automatically.

## Before publishing a fork

- Confirm `backend/.env`, `local-data/`, private documents, and generated PDFs
  are ignored.
- Run `python scripts/privacy_check.py` before staging and
  `python scripts/privacy_check.py --staged` after staging.
- Review `git diff --cached --name-only` before the first commit.
- Run a secret scan against the staged files.
- Never publish a locally built Docker image that predates the `.dockerignore`
  files.
