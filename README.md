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
- Supabase Postgres storage with a zero-config SQLite fallback
- Nine switchable PDF résumé templates fed by the same résumé data

## Screenshots

All screenshots below use fictional demonstration data.

<p align="center">
  <a href="docs/screenshots/00-forma-architecture.png">
    <img src="docs/screenshots/00-forma-architecture.png" alt="Forma architecture: a human-reviewed LangGraph workflow backed by SQLite" width="100%">
  </a>
  <br>
  <sub>Bounded agentic workflow, visible human decisions, and durable local state.</sub>
</p>

<table>
  <tr>
    <td width="50%" valign="top">
      <a href="docs/screenshots/01-agentic-analysis.png">
        <img src="docs/screenshots/01-agentic-analysis.png" alt="Forma cover-letter workflow showing inspectable role analysis">
      </a>
      <br>
      <sub>Inspect requirements, evidence, gaps, strategy, and uncertainties before research begins.</sub>
    </td>
    <td width="50%" valign="top">
      <a href="docs/screenshots/02-research-and-clarify.png">
        <img src="docs/screenshots/02-research-and-clarify.png" alt="Forma cover-letter workflow showing sourced research and clarification">
      </a>
      <br>
      <sub>Approve sourced company context and answer only the questions that improve the draft.</sub>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <a href="docs/screenshots/03-company-researcher.png">
        <img src="docs/screenshots/03-company-researcher.png" alt="Forma company researcher with a structured source-backed report">
      </a>
      <br>
      <sub>Structured company research with retained sources, confidence, risks, and role relevance.</sub>
    </td>
    <td width="50%" valign="top">
      <a href="docs/screenshots/04-application-tracker.png">
        <img src="docs/screenshots/04-application-tracker.png" alt="Forma application tracker linked to resume versions">
      </a>
      <br>
      <sub>Track application status and the exact résumé version submitted for each role.</sub>
    </td>
  </tr>
  <tr>
    <td colspan="2" valign="top">
      <a href="docs/screenshots/05-resume-versions.png">
        <img src="docs/screenshots/05-resume-versions.png" alt="Forma resume-version library with independent tailored versions">
      </a>
      <br>
      <sub>Keep the master résumé protected while creating independent tailored versions and recoverable drafts.</sub>
    </td>
  </tr>
</table>

## Storage and privacy

The browser never receives a database password or AI key. It talks only to the
FastAPI backend. The supplied Supabase schema enables Row Level Security and
revokes table access from the browser-facing `anon` and `authenticated` roles.
Forma's backend connects through the private Postgres connection string.

With Supabase configured, résumé versions, applications, cover letters, research
reports, and uploaded profile photos live in Supabase. Generated files and the
SQLite fallback use the ignored `local-data/` directory:

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

> Forma is currently a single-user workspace and its API has no authentication.
> Keep it bound to your own machine or add an
> authentication layer before exposing it to a network or public host.

## Supabase + Docker quick start

You need a Supabase project, its database password, and the Postgres connection
URI. You do **not** need the publishable key or secret key: Forma connects from
the backend directly to Postgres and does not use Supabase's browser Data API.

Connecting the repository through Supabase's GitHub integration does not perform
these runtime setup steps automatically.

1. Clone the repository and enter it:

   ```bash
   git clone YOUR_REPOSITORY_URL
   cd Forma
   ```

2. Create a Supabase project and keep its database password available. This is
   the password chosen when the project was created, not a publishable or secret
   API key.

3. In **Supabase Dashboard → SQL Editor**, create a new query, paste the complete
   contents of [`supabase/schema.sql`](supabase/schema.sql), and click **Run**.
   The script is idempotent and can be run again after updating Forma. It also
   keeps `anon`, `authenticated`, and `service_role` away from Forma's tables;
   the app does not use Supabase's Data API keys.

4. Create the private backend environment file:

   ```bash
   cp backend/.env.example backend/.env
   ```

5. In the Supabase project, click **Connect**, select **Direct / Connection
   string**, choose **Session pooler**, and copy the URI. The Session pooler uses
   port `5432` and works on IPv4 networks used by many Docker installations.

6. Open `backend/.env` and set `DATABASE_URL` to that URI:

   ```dotenv
   DATABASE_URL=postgresql://postgres.PROJECT_REF:URL_ENCODED_PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres?sslmode=require
   ```

   Replace `[YOUR-PASSWORD]` in Supabase's copied URI if it is still present.
   If the password contains characters such as `@`, `:`, `/`, `#`, or `%`,
   URL-encode it first. Keep `?sslmode=require` at the end. Do not put this URI,
   the database password, or any secret key in a `VITE_` variable; `VITE_`
   variables are shipped to the browser.

7. Add the API key for any AI provider you want to use. AI features are
   optional; résumé editing, templates, PDF export, and application tracking
   work without one.

8. Start the application:

   ```bash
   docker compose up --build
   ```

9. In another terminal, confirm the backend is using Supabase:

   ```bash
   curl http://localhost:8001/health
   ```

   A successful response includes `"database":"supabase"`. If it says
   `sqlite`, `DATABASE_URL` was not loaded; recreate the backend container after
   checking `backend/.env`:

   ```bash
   docker compose up --build --force-recreate backend
   ```

10. Open:

   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8001
   - API documentation: http://localhost:8001/docs
   - Health check: http://localhost:8001/health

The frontend uses a same-origin `/api` proxy inside Docker. It does not hardcode
the host's backend port, which avoids the common `localhost:8000`/`8001`
mismatch. To choose different host ports:

```bash
BACKEND_PORT=8010 FRONTEND_PORT=5180 docker compose up --build
```

### SQLite fallback

Leave `DATABASE_URL` unset to run without Supabase. Forma will store relational
data and profile photos in `local-data/resume.db`. This mode is also used by the
automated test suite.

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

Local Vite development proxies `/api`, `/static`, and `/health` to
`http://localhost:8000`. Override only when the backend is on another port:

```bash
VITE_API_PROXY_TARGET=http://localhost:8001 npm run dev
```

Without an override, local development and Docker both use the repository's
ignored `local-data/` directory. Set `CV_PERSONALIZER_DATA_DIR` if you want a
different location.

## Optional AI configuration

Copy `backend/.env.example` to `backend/.env` and configure:

```dotenv
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-3.8-flash
GEMINI_COVER_LETTER_MODEL=gemini-3.8-flash
GEMINI_COMPANY_RESEARCH_MODEL=gemini-3.8-flash
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_RESUME_MODEL=gpt-5.6-sol
OPENAI_COVER_LETTER_MODEL=gpt-5.6-sol
OPENAI_COMPANY_RESEARCH_MODEL=gpt-5.6-sol
```

Choose Gemini or ChatGPT from the **AI provider** selector in the sidebar. The
selection is saved in the browser and applies to résumé suggestions, tailoring,
cover letters, and company research. LangGraph orchestrates structured outputs
and provider-native web search for both providers.

Gemini 3.7 uses medium thinking and native structured output. Company research
uses Google Search grounding for Gemini and web search in the OpenAI Responses
API for ChatGPT. The UI shows whether the selected provider has a configured key.

## Résumé templates

Open a résumé and choose **Template** in the editor toolbar. Forma includes:

- Modern
- Classic
- Minimal
- Executive
- Creative
- Technical
- LaTeX — academic, single-column typesetting
- ATS Simple — plain parsing-first document flow
- Timeline — dates lead a chronological rail

The selected template is stored on the résumé version. Switching templates
changes only presentation; all nine render the same structured résumé data.
PDF rendering uses bundled system fonts and does not depend on Google Fonts or
another external asset server.

## Backing up data

Supabase projects can be backed up using Supabase's database backup and export
tools. For the SQLite fallback, SQLite's backup command creates a consistent
snapshot while preserving the active database:

```bash
mkdir -p local-data/backups
sqlite3 local-data/resume.db \
  ".backup 'local-data/backups/resume-backup.db'"
```

Keep `local-data/` out of Git. Do not run `git clean -fdX` in this repository:
that command deletes ignored files, including local application data.

## Troubleshooting

If Docker reports that a port is allocated, choose another host port rather
than changing application code:

```bash
BACKEND_PORT=8010 docker compose up --build
```

If the browser says the backend is unavailable:

```bash
docker compose ps
docker compose logs backend
curl http://localhost:8001/health
```

- A schema error means `supabase/schema.sql` has not been run, or needs to be
  run again after an update.
- A connection timeout commonly means the IPv6 direct URI was used on an
  IPv4-only network. Use Supabase's Session pooler URI on port `5432`.
- An authentication failure usually means `[YOUR-PASSWORD]` was not replaced,
  the database password is wrong, or special characters were not URL-encoded.
- `sb_publishable_...` and `sb_secret_...` values are API keys, not database
  passwords, and do not belong in `DATABASE_URL`.
- An AI-key error affects only that provider. Check `backend/.env`, then restart
  the backend.
- PDF previews do not need internet access. If one fails, inspect the backend
  log for invalid résumé data rather than a font download failure.

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
├── docs/
│   └── screenshots/         # Public fictional demo screenshots
├── supabase/
│   └── schema.sql            # Paste into the Supabase SQL Editor
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
