# Resume Tailoring Agent

LangGraph-orchestrated agent that takes a job description + LaTeX resume template + `profile.json` and produces a tailored, ATS-friendly 1-page PDF. Exposes both a CLI and a production FastAPI server backed by Firebase.

## What It Does

Given a job description, the agent:
1. Researches the company via web search
2. Scores all projects in `profile.json` against the JD using an LLM
3. Selects the top 2 most relevant projects
4. Filters and prioritizes skills from `profile.json` that match the JD, selected projects, and existing resume experience
5. Generates LaTeX for the Skills and Projects sections using LLM + user-editable templates
6. Compiles the final PDF with `latexmk`/`pdflatex`

Key guarantees:
- **No fabrication** — all skills, projects, and certifications come exclusively from `profile.json`
- **Zero layout drift** — only Skills and Projects sections are replaced; all other sections (Experience, Education, etc.) are untouched
- **Hard constraints** — exactly 2 projects, ≤10 skills per category, certifications always included

---

## Architecture

Two entrypoints share the same LangGraph pipeline:

- `tailor.py` — CLI for local use
- `api.py` — FastAPI server for production; requires Firebase auth, fetches resume zip from Firebase Storage, stores results in Firestore

```
tailor.py (CLI)  ──┐
                   ├──► LangGraph Pipeline (resume_agent/graph.py)
api.py (FastAPI) ──┘
```

---

## LangGraph Pipeline

Linear 9-node DAG (`resume_agent/graph.py`):

```
load_inputs
    │  Read JD text, wipe & recreate output dir
    ▼
analyze_jd
    │  Extract title + keyword list from JD text
    ▼
infer_company_and_research
    │  Web-search company mission; collect citations
    ▼
load_resume_files
    │  Find main.tex, resolve \input/\include recursively, read all .tex files
    ▼
load_profile_json
    │  Load profile.json (skills, projects, certifications)
    ▼
plan_edits
    │  LLM call 1: Score all projects against JD (batched, single call)
    │  → Select top 2 projects
    │  LLM call 2: Filter skills by JD + project tech + experience section
    │  → Post-process: force-add skills found in resume Experience section
    │  → Post-process: force-add profile skills word-boundary matched in JD
    │  → Force-add required languages implied by frameworks (e.g. Spring Boot → Java)
    │  → Cap each category at 10, always include certifications
    ▼
apply_edits
    │  LLM call 3: Generate Skills LaTeX from template (skills_format.tex)
    │  → Regex-replace %-*PROGRAMMING SKILLS-*% section using lambda (avoids backslash bugs)
    │  LLM call 4: Generate Projects LaTeX from template (projects_format.tex)
    │  → Regex-replace %-*PROJECTS-*% section using lambda
    │  Write all updated .tex files to output dir
    ▼
compile_pdf
    │  latexmk (preferred) or pdflatex fallback
    │  Output filename: {username}-{Company}-{Position}-{MM-YYYY}.pdf
    ▼
generate_report
       Write report.md: selected projects, skills, citations, verification list
```

State flows through `TailorState` (Pydantic model). If any node sets `state.error_status`, all downstream nodes skip.

---

## API Request Flow (`POST /api/v1/generate`)

```
Client
  │  POST /api/v1/generate
  │  Headers: Authorization: Bearer <Firebase ID token>
  │  Body: { companyName, jobTitle, jobDescription, resumeZipUrl, jobUrl?, jobId? }
  ▼
verify_firebase_token
  │  Verifies Firebase ID token → extracts uid
  ▼
Determine job ID
  │  New job: generate UUID
  │  Regeneration (jobId provided): verify job exists in Firestore under uid, fetch old PDF URL
  ▼
Download & extract resume zip
  │  Cache keyed by MD5(url + CACHE_VERSION) in .resume_cache/
  │  Cache hit: copy from cache
  │  Cache miss: download → save to cache → extract → copy
  ▼
Write JD to temp file
  │  Load profile.json from server working directory
  ▼
Run LangGraph pipeline
  │  (see pipeline above)
  │  Raises LLMQuotaExceededError → HTTP 402
  │  Raises RATE_LIMIT_EXCEEDED/LLM_FAILURE → HTTP 503
  ▼
Verify PDF exists at output path
  ▼
Delete old PDF from Firebase Storage (regeneration only)
  ▼
Upload new PDF to Firebase Storage
  │  Path: users/{uid}/generated_resumes/{username}-{company}-{title}-{timestamp}.pdf
  │  Made public; returns public URL
  ▼
Save to Firestore
  │  jobs/{job_id} — job details + company research
  │  job_applied/{uid}/applications/{job_id} — user application record + PDF URL
  ▼
Copy output files to ./Resume/job_{job_id[:8]}/ (for server-side inspection)
  ▼
Cleanup temp dir
  ▼
Return { status, message, job_id, resume_pdf_url }
```

Other endpoints:
- `GET /` — API info
- `GET /health` — health check

---

## Repository Layout

```
.
├── tailor.py                    # CLI entrypoint
├── api.py                       # FastAPI server
├── profile.json                 # Single source of truth: skills, projects, certifications
├── pyproject.toml               # Dependencies (managed with uv)
├── resume_agent/
│   ├── graph.py                 # LangGraph pipeline nodes + TailorState
│   ├── prompts.py               # LLM system + user prompts
│   ├── tools.py                 # LLM wrapper (multi-provider), web search
│   ├── tex.py                   # LaTeX \input resolver, template loader, read/write
│   ├── profile.py               # profile.json loader
│   ├── compile.py               # latexmk / pdflatex compilation
│   ├── report.py                # report.md generation
│   ├── star.py                  # STAR bullet rewriting
│   └── utils.py                 # Shared utilities
├── SWE_Resume_Template/
│   ├── templates/
│   │   ├── skills_format.tex    # Skills section template (user-editable)
│   │   └── projects_format.tex  # Projects section template (user-editable)
│   └── src/                     # Section .tex files used by the template
└── tests/                       # pytest unit tests
```

---

## Setup

**Prerequisites:**
- Python 3.11+
- LaTeX toolchain (`latexmk` or `pdflatex`)
- Firebase service account JSON (for `api.py` only)

**Install:**
```bash
uv sync
cp .env.example .env   # fill in API keys
```

**Run CLI:**
```bash
python tailor.py \
  --jd ./jd.txt \
  --resume_dir ./SWE_Resume_Template/ \
  --profile ./profile.json \
  --out_dir ./output/ \
  --company "CompanyName"
```

**Run API server:**
```bash
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
# or
python api.py
```

**Docker:**
```bash
docker compose up --build
```

---

## Configuration

`LLM_PROVIDER` in `.env` selects the active provider. Supported: `openai`, `gemini`, `moonshot`, `custom` (any OpenAI-compatible endpoint).

| Variable | Purpose |
|---|---|
| `LLM_PROVIDER` | `openai` / `gemini` / `moonshot` / `custom` |
| `OPENAI_API_KEY` | OpenAI or compatible key |
| `OPENAI_BASE_URL` | Custom base URL (optional) |
| `OPENAI_MODEL` | Model name |
| `GEMINI_API_KEY` | Gemini key |
| `LLM_TEMPERATURE` | Set low (0.0–0.2) for determinism |
| `FIREBASE_CREDENTIALS_PATH` | Path to Firebase service account JSON (`api.py` only) |

See `LLM_CONFIGURATION.md` for full provider-specific details.

---

## LLM Error Handling

`call_llm()` in `tools.py`:
- Retries once on HTTP 429
- Raises `RATE_LIMIT_EXCEEDED` — pipeline stops, HTTP 503
- Raises `QUOTA_EXCEEDED` / `LLMQuotaExceededError` — pipeline stops, HTTP 402
- Raises `LLM_FAILURE` — pipeline stops, HTTP 503

The pipeline never silently falls back to incomplete output when the LLM fails — it stops and surfaces the error.

---

## profile.json

Single source of truth. Structure:

```json
{
  "username": "FirstName_LastName",
  "skills": {
    "Languages": ["Python", "Java", ...],
    "Web & Backend": ["React", "FastAPI", ...],
    "Data Science & ML": [...],
    "Databases": [...],
    "Cloud & DevOps": [...],
    "Tools & Platforms": [...]
  },
  "projects": [
    {
      "name": "Project Name",
      "tech_stack": ["Python", "PostgreSQL"],
      "tags": ["backend", "ml"],
      "description": ["bullet 1", "bullet 2"],
      "metrics": ["reduced latency by 40%"],
      "links": ["https://github.com/..."]
    }
  ],
  "certifications": ["AWS Certified Developer"]
}
```

---

## Templates

Edit `SWE_Resume_Template/templates/skills_format.tex` and `projects_format.tex` to adjust output layout. The LLM fills in the content; keep placeholder structure intact. See `SKILLS_TEMPLATE_GUIDE.md`.

Section markers in your LaTeX files tell the pipeline where to do replacements:
- `%-*PROGRAMMING SKILLS-*%` before `\section{Technical Skills}`
- `%-*PROJECTS-*%` before `\section{Projects}`

---

## Tests

```bash
pytest                     # all tests
pytest tests/test_tex.py   # single file
```

Tests cover: LaTeX `\input`/`\include` resolver, project deduplication and matching logic.

---

## License

MIT
