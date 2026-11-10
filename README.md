# Theater Showtimes Backend Assessment

A small system for managing theater showtimes: a FastAPI backend on PostgreSQL that
ingests partner CSV drops and reconciles them against the stored schedule, and a
Next.js frontend that talks to it.

## Quick Start

### 1. Database

Create a PostgreSQL database and put its URL in `.env` (copy from `.env.example`):

```bash
cp .env.example .env
```

```
DATABASE_URL="postgresql://postgres:postgres@localhost:5432/scopelabs"
NEXT_PUBLIC_API_URL="http://localhost:8000"
GEMINI_API_KEY=""      # optional; enables the AI upload assistant
ANTHROPIC_API_KEY=""   # optional; fallback provider, or the only one
```

Tables, indexes and the `pg_trgm` extension are created automatically when the
backend starts, so no migration step is needed. Without a model API key the app
works exactly the same, minus the AI panel in the upload preview.

### 2. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # or: source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed            # loads the sample theaters, users and showtimes
uvicorn app.main:app --reload --port 8000
```

Interactive API docs are served at `http://localhost:8000/docs`.

### 3. Frontend

```bash
npm install
npm run dev
```

Open `http://localhost:3000`, pick a user in the Session box, and the rest of
the page is driven by the API.

### Tests

```bash
cd backend
python -m pytest
```

The tests cover title normalization, CSV parsing and the schedule diff, using
the files in `sample-data/` as fixtures.

## How It Works

### Users and access

There is no login screen. The frontend lets you pick a user and sends that id
on every request as an `X-User-Id` header. The backend resolves the user and
enforces everything from there:

- Every showtime query is restricted to theaters the user belongs to. A user
  with no theaters simply gets an empty list.
- Admins can change a showtime's `status` and `movieStatus`, upload CSVs and
  clear a schedule. Viewers get `403` on those endpoints regardless of what the
  UI shows.

Swapping the header for a real session token would only touch `app/auth.py`.

### Data model

Three tables plus a join table, in `backend/app/models.py`:

- `theaters` and `users`, linked through `user_theaters`.
- `showtimes`, one row per screening, carrying the movie title, auditorium,
  start/end time, language, format, rating, both status fields and a
  `last_updated` timestamp.

Movie status is stored on the showtime rather than in a separate movies table
because the provided data has the same movie at different statuses in different
screenings. It keeps the schema to one hot table, which is also what makes the
list endpoint simple to index.

Each showtime also stores a `normalized_title`: the title lower-cased, with
punctuation and dash variants removed, whitespace collapsed and number words
turned into digits. "Spider‑Man: Homecoming", "  Spider Man - Homecoming  "
and "DUNE PART 2" / "Dune: Part Two" all normalize to the same key. This column
is what matching and searching use; the original spelling is kept for display.

### Search at scale

`GET /showtimes` is paginated and does all searching, filtering and sorting in
SQL. The relevant indexes:

- A GIN trigram index on `normalized_title` so `ILIKE '%term%'` search stays
  fast on hundreds of thousands of rows.
- A composite index on `(theater_id, start_time)` for the default listing.
- A partial unique index on `(theater_id, normalized_title, start_time)` where
  `status = 'active'`. This is the "at most one active showtime per movie and
  start time per theater" rule, enforced by the database rather than by
  application code.

### CSV reconciliation

Upload is two steps so an admin can see the effect before anything is written:

1. `POST /theaters/{id}/schedule/preview` parses the file and returns the adds,
   updates (with per-field diffs) and archives it would make.
2. `POST /theaters/{id}/schedule/apply` takes the same file and applies those
   changes in one transaction.

Re-parsing on apply keeps the server stateless; there is no preview to store or
expire. Both steps run through the same code in `app/ingest.py`:

- Every cell is trimmed and internal whitespace is collapsed. Rows naming a
  different theater are rejected with the line number.
- Within one file, rows with the same movie and start time collapse to the last
  one, so a duplicated line never creates a duplicate showtime.
- A row is matched to an existing showtime by `(normalized title, start time)`.
  If it matches and any field differs (title spelling, auditorium rename,
  format change) the existing row is updated in place. If the match was
  archived earlier, it is reactivated instead of inserted again.
- Rows with no match are inserted as new active showtimes.
- Active showtimes for that theater that do not appear in the file are archived.

`POST /theaters/{id}/schedule/archive-all` backs the Clear Schedule button.

### AI upload assistant

The deterministic pipeline above handles the predictable cases. A model-backed
assistant covers the cases that need judgement, in `backend/app/assistant.py`.
It can run on either provider, chained in `backend/app/ai.py`:

- **Gemini** (`gemini-2.5-flash` via `google-genai`) is tried first when
  `GEMINI_API_KEY` is set.
- **Anthropic** (`claude-opus-5-5` via the `anthropic` SDK, with structured
  output and the server-side refusal fallback enabled) answers when Gemini is
  not configured, rejects its key, or a call fails. A rejected key disables that
  provider for the rest of the process so later calls skip straight to the
  fallback.

The preview shows which provider answered. The assistant does three things:

1. **Header mapping.** When a file does not use our column names, the header
   and a few sample rows are sent to the model, which maps them to our schema.
   The preview shows the mapping ("Film → movie_title") so the admin can check
   it, and the frontend sends it back on apply so both steps read the file the
   same way.
2. **Match suggestions.** When the diff would add a row and archive a showtime
   at the same start time, the model is asked whether the two titles are the
   same film. Suggestions above 70% confidence appear in the preview with a
   checkbox. Accepting one turns the add-plus-archive pair into a single update
   of the existing showtime, which also teaches the normalizer that spelling
   for future drops.
3. **Review summary.** The model gets the diff and the projected schedule and
   returns a two-sentence summary plus warnings such as overlapping screenings
   in one auditorium or an implausible runtime.

Design rules for the assistant:

- Every call asks for JSON matching a pydantic schema; anything else is
  discarded. Mappings are checked against the real headers, suggestions
  against the real diff, so the model can only propose, never write.
- Nothing is applied without the admin confirming in the preview.
- API keys live only in the server environment (`GEMINI_API_KEY`,
  `ANTHROPIC_API_KEY`). If neither is set, or every provider fails, the upload
  flow continues without the panel.
- The tests exercise the assistant with a fake client, so the suite runs
  offline and without a key.

## Deploying to Vercel

The whole project deploys as one Vercel project: Next.js for the frontend and
the FastAPI app as a Python function (`api/index.py`) served under `/api`.

1. Create a Postgres database. Neon via the Vercel Marketplace works on the
   free tier and supports `pg_trgm`.
2. Import the repository into Vercel and set these environment variables:
   - `DATABASE_URL`: the Postgres connection string (use the pooled one if offered).
   - `GEMINI_API_KEY` and/or `ANTHROPIC_API_KEY`: at least one, for the assistant.
   - `NEXT_PUBLIC_API_URL`: `/api`
3. Create the schema and load the sample data once, from your machine, with
   `DATABASE_URL` pointed at the hosted database:

   ```bash
   cd backend && python -m app.seed
   ```

4. Deploy. Vercel installs `requirements.txt` from the repository root (which
   pulls in `backend/requirements.txt`), builds Next.js, and rewrites
   `/api/*` to the Python function.

On Vercel the backend skips startup schema creation and uses one database
connection per request instead of a pool, since functions are short-lived.

## API Overview

| Method | Path | Who | Purpose |
| --- | --- | --- | --- |
| GET | `/users` | anyone | Users for the session selector |
| GET | `/me` | any user | Current user with role and theater ids |
| GET | `/me/theaters` | any user | Theaters the user belongs to |
| GET | `/showtimes` | any user | Paginated list with `q`, filters, `sort`, `order`, `page`, `page_size` |
| GET | `/showtimes/filter-options` | any user | Distinct values for the filter dropdowns |
| PATCH | `/showtimes/{id}` | admin | Update `status` and/or `movieStatus` |
| POST | `/theaters/{id}/schedule/preview` | admin | Diff a CSV against the current schedule |
| POST | `/theaters/{id}/schedule/apply` | admin | Apply a CSV |
| POST | `/theaters/{id}/schedule/archive-all` | admin | Archive every active showtime |

All responses use camelCase to match the frontend types in
`src/types/assessment.ts`.

## Project Layout

```
api/index.py     Vercel function entry mounting the backend under /api
backend/app/
  main.py        FastAPI app, CORS, startup schema creation
  db.py          engine and session
  models.py      SQLAlchemy models and indexes
  auth.py        X-User-Id resolution and admin check
  normalize.py   title normalization
  ingest.py      CSV parsing and schedule diff
  ai.py          Gemini and Anthropic providers, fallback chain, disabled mode
  assistant.py   header mapping, match suggestions, review summary
  seed.py        loads seed_data.json
  routers/       users, showtimes, schedule endpoints
backend/tests/   pytest suite
src/lib/api.ts   typed client used by the page
sample-data/     example partner drops used by the tests
```
