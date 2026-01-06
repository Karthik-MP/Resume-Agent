# Resume Tailoring System Design

A LangGraph-orchestrated resume tailoring system that takes:
- A job description
- A multi-file LaTeX resume
- A trusted profile.json (skills + projects)

And produces a 1-page, ATS-safe, visually identical PDF resume, tailored to a single job.

## Core Design Principles
- **Zero layout drift**: Fonts, margins, spacing are never changed.
- **Truthfulness**: No fabrication; only uses resume + profile.json.
- **Direct LaTeX generation**: LLM outputs final LaTeX blocks, not prose or JSON.
- **Hard constraints**:
  - Exactly 2 projects
  - STAR bullets (2-3 points per project)
  - Quantified results only if metrics exist
  - Skills filtered to JD + selected projects
  - Overleaf-compatible: Multi-file LaTeX preserved.

## High-Level Flow
- Load inputs (JD, resume files, profile)
- Analyze JD (keywords, role signals)
- Select top 2 relevant projects
- Derive relevant skills by category
- Ask LLM to generate LaTeX-only sections
- Replace entire LaTeX sections (not lines)
- Compile PDF
- Generate report

## File-by-File Responsibility Map

### Root
- **tailor.py**
  - CLI entrypoint
  - Parses arguments
  - Initializes LangGraph
  - Runs the pipeline
  - Writes report.md
  - Outputs final PDF path

### resume_agent/
- **graph.py** - System brain / orchestration
  - Defines TailorState
  - LangGraph nodes:
    - load_inputs
    - analyze_jd
    - load_resume_files
    - load_profile_json
    - plan_edits
    - apply_edits
    - compile_pdf
    - generate_report
  - Enforces hard constraints:
    - max 2 projects
    - safe skill categories
    - no structural LaTeX mutation

- **plan_edits** (inside graph.py) - Decision-making layer
  - Scores projects vs JD
  - Selects top 2 projects
  - Derives skills_by_category strictly from:
    - selected projects' tech stack
    - JD keywords
  - Produces a minimal, deterministic plan
  - No LaTeX editing here

- **apply_edits** (inside graph.py) - LaTeX-safe mutation layer
  - Never edits margins, fonts, macros
  - Replaces entire sections only
  - src/skills.tex
  - src/projects.tex
  - Inserts LLM-generated LaTeX verbatim
  - Guarantees:
    - identical font
    - identical spacing
    - 1-page output

- **prompts.py** - LLM contract definitions
  - Strict system prompts:
    - "Output ONLY LaTeX"
    - "Do not change structure"
    - "Follow exact format"
  - Provides format exemplars for:
    - Skills section (GENERATE_SKILLS_SYSTEM, GENERATE_SKILLS_USER)
    - Projects section
  - Enforces STAR + quantification rules
  - Skills generation uses user-customizable template from templates/skills_format.tex

- **profile.py** - Trusted data loader
  - Loads profile.json
  - No rewriting, no inference
  - Source of truth for:
    - skills
    - projects
    - metrics

- **tex.py** - LaTeX utilities
  - Resolves \input / \include
  - Reads multi-file resumes
  - Writes mirrored output directory
  - (Optional) diff generation
  - load_template() - Loads user-customizable LaTeX format templates

- **compile.py** - PDF compilation
  - Uses latexmk or pdflatex
  - Gracefully skips if LaTeX missing
  - Captures compile logs
  - Moves final PDF to target path

- **report.py** - Transparency & audit
  - Keyword coverage summary
  - Projects selected
  - Skills kept/removed
  - Sources used
  - "Verification needed" list

- **utils.py** - Shared helpers
  - Logging
  - subprocess wrappers
  - small pure utilities

- **tools.py** - External integrations
  - Web search (Tavily, DuckDuckGo)
  - get_llm() - LLM model initialization
  - call_llm() - Unified interface for LLM calls
  - Supports OpenAI models via environment configuration

### Templates Directory (SWE_Resume_Template/templates/)
- **skills_format.tex** - User-editable LaTeX template for skills section
  - Defines exact structure and categories
  - Uses placeholders like `<comma-separated list>`
  - LLM fills placeholders with relevant skills
  - Allows format changes without code modifications
  - See SKILLS_TEMPLATE_GUIDE.md for customization instructions