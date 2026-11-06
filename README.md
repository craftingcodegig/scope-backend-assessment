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
```

Tables, indexes and the `pg_trgm` extension are created automatically when the
backend starts, so no migration step is needed.

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
backend/app/
  main.py        FastAPI app, CORS, startup schema creation
  db.py          engine and session
  models.py      SQLAlchemy models and indexes
  auth.py        X-User-Id resolution and admin check
  normalize.py   title normalization
  ingest.py      CSV parsing and schedule diff
  seed.py        loads seed_data.json
  routers/       users, showtimes, schedule endpoints
backend/tests/   pytest suite
src/lib/api.ts   typed client used by the page
sample-data/     example partner drops used by the tests
```
