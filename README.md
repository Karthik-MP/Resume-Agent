# Resume Tailoring Agent — Overview

This repository implements a LangGraph-orchestrated resume tailoring agent that:

- Takes a job description (JD), a multi-file LaTeX resume project, and a trusted `profile.json` (skills + projects).
- Produces a tailored, ATS-friendly 1-page PDF while preserving layout and LaTeX structure.
- Uses a ChatGPT-class LLM (configurable) to generate LaTeX-only sections (skills and projects) from user-editable templates.

Goals:

- Zero layout drift: fonts, margins, and spacing are preserved.
- Truthfulness: only facts from the resume and `profile.json` are used; no fabrication.
- Deterministic editing: replace entire sections (not line-level edits) and compile the resulting PDF.

## Quick Features

- Multi-file LaTeX resolver and mirrored output directory
- LLM-driven skills & projects generation using user templates
- Hard constraints enforced: exactly 2 projects, 2–3 STAR bullets per project
- Certifications always included from `profile.json`
- Safe replacements (lambda-based regex replacement) to avoid LaTeX escaping issues
- Compile using `latexmk` or fallback `pdflatex` runs, with logs captured

## Repository Layout

Root

- `tailor.py` — CLI entrypoint (runs the LangGraph pipeline)
- `profile.json` — trusted source for skills, projects, certifications
- `pyproject.toml` — project metadata & dev dependencies
- `README.md` — original README (kept for history)
- `README_UPDATED.md` — this updated README
- `SKILLS_TEMPLATE_GUIDE.md` — guidance for templates

resume_agent/

- `graph.py` — pipeline orchestration (LangGraph nodes)
- `prompts.py` — strict LLM system and user prompts
- `tools.py` — LLM wrapper, web search helpers
- `tex.py` — multi-file LaTeX resolver and read/write helpers
- `profile.py` — `profile.json` loader and matcher
- `compile.py` — LaTeX compilation utilities
- `report.py` — transparency & audit report generation
- `utils.py` — shared utilities and logging

SWE_Resume_Template/

- `templates/skills_format.tex` — skills template (user-editable)
- `templates/projects_format.tex` — projects template (user-editable)
- `src/` — sample section files used by the template

tests/

- Unit tests for `tex` include resolver and project dedupe logic

## Getting Started

Prerequisites

- Python 3.11+ (project uses modern typing and features)
- A LaTeX toolchain (`latexmk` or `pdflatex`) for PDF compilation
- Optionally: an OpenAI-compatible API key if you want LLM generation

Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Configuration

- Copy `.env.example` to `.env` and set required keys.
- Important environment variables:
  - `OPENAI_API_KEY` — required for LLM generation (if you use OpenAI-compatible providers)
  - `OPENAI_BASE_URL` — optional custom base URL (default: https://api.openai.com/v1)
  - `OPENAI_MODEL` — model name (default recommended: `gpt-4` or `gpt-4o-mini`)
  - `LLM_TEMPERATURE` — set low (0.0–0.2) for deterministic output

Example `.env` values:

```bash
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4
LLM_TEMPERATURE=0.1
```

## Usage

Run the tailoring pipeline via the CLI. Minimal example:

```bash
python tailor.py \
  --jd ./jd.txt \
  --resume_dir ./SWE_Resume_Template/ \
  --profile ./profile.json \
  --out_dir ./output/ \
  --out_pdf ./output/final.pdf
```

Optional flags: `--job_url`, `--company` (used for company research), `--no-llm` (force fallback behavior).

Output artifacts

- `output/` (default) — mirrored LaTeX files written here
- `output/final.pdf` — compiled PDF (if compilation succeeded)
- `output/report.md` — audit report with keyword coverage, selected projects, and verification-needed list

## How It Works (High Level)

1. load_inputs — reads JD, resume files, and profile JSON; cleans output dir
2. analyze_jd — extracts keywords, responsibilities, and seniority signals
3. load_resume_files — resolves `\input`/`\include`, reads editable section files
4. load_profile_json — loads trusted `profile.json` (skills, projects, certifications)
5. plan_edits — selects top-2 relevant projects and derives skills by category (strict mapping)
6. apply_edits — asks LLM to generate LaTeX for skills/projects based on templates; falls back to safe regex replacements when LLM fails
7. compile_pdf — attempts `latexmk` or `pdflatex` and captures logs
8. generate_report — writes `report.md` summarizing changes, sources, and verification items

## Templates and Customization

- Edit `SWE_Resume_Template/templates/skills_format.tex` and `projects_format.tex` to adjust output layout — keep placeholders like `<comma-separated list>` or `<Project Name>`.
- See `SKILLS_TEMPLATE_GUIDE.md` for examples and mapping rules between `profile.json` categories and template categories.

## LLM Prompting & Safety

- The system uses strict system prompts (see `resume_agent/prompts.py`) instructing the LLM to output ONLY LaTeX and follow the template exactly.
- Hard constraints enforced in code:
  - Exactly two projects in projects section
  - 2–3 STAR bullets per project
  - Certifications from `profile.json` are always included
  - Do not invent facts not present in `profile.json` or the original resume

If the LLM output contains backslash or escape issues, the pipeline will retry with a lower temperature and, if necessary, use the safe fallback replacement.

## Company Research (optional)

- If `--job_url` or `--company` is supplied, `tools.py` performs lightweight web fetching and summarization to extract company mission and product signals to inform keyword selection.
- All web sources and citations are recorded in `output/report.md`.

## Troubleshooting

- LaTeX compilation errors: check `output/compile.log` for details. If compilation fails, the updated LaTeX files remain in `output/` for manual inspection.
- LLM not called: verify `OPENAI_API_KEY` and network connectivity.
- Bad LaTeX from LLM: lower `LLM_TEMPERATURE` and retry; templates should use simple placeholders.

## Tests

- Unit tests are under `tests/` for the `tex` include resolver and project dedupe/matching logic. Run with `pytest`.

## Development Notes & Assumptions

- The system treats `profile.json` as the single trusted source for additional skills and projects. No external fabrication.
- Templates must preserve placeholders the LLM will replace. See `SKILLS_TEMPLATE_GUIDE.md`.
- LLM usage is optional; the pipeline supports a safe regex-based fallback.

## Next Steps

- Improve LLM post-processing sanitizers for LaTeX escapes.
- Add optional ATS scoring step and iterative prompt refinement.

## License

MIT

---

If you'd like, I can run a quick markdown lint or re-run the tailoring pipeline to incorporate the new `Data Collection System` project you recently added to `profile.json`.