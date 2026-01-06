SYSTEM:
You are a senior Python engineer and AI product architect. You will output production-ready code for a LangGraph-based resume tailoring agent. You must follow requirements exactly, ask no follow-up questions, and implement sensible defaults where unspecified. Do not include explanations longer than necessary; prioritize working code with clear structure and comments. Do not fabricate external dependencies—if you introduce a dependency, include it in requirements and explain briefly why it is needed.

USER:
Build a LangGraph agent in Python that uses a ChatGPT-class LLM to tailor my Overleaf resume to a single job description (JD). The resume project is MULTI-FILE LaTeX (e.g., main.tex plus included section files). The system must also enrich the resume by adding new skills/projects pulled from my predefined user profile JSON file (skills + projects), but only when relevant to the JD and consistent with the profile.

INPUTS:
1) job_description: text (primary source)
2) job_url: optional URL (use if needed for company research)
3) resume_root_dir: path to a folder containing multi-file LaTeX resume project
4) profile_json_path: path to predefined JSON containing user skills and projects
5) company_name: optional (if not provided, infer from JD or job_url when possible)

OUTPUTS:
- final compiled PDF resume file (output_pdf_path)
- also output intermediate artifacts:
  - updated LaTeX files written back into an output folder (not overwriting original)
  - report.md with: ATS keyword alignment summary, list of changes, sources used, and a “verification needed” section
  - optional diff patch files (per LaTeX file) if easy

HARD CONSTRAINTS:
- Truthfulness: Do not invent facts beyond what is in resume + profile_json. You MAY add new projects/skills ONLY if they exist in profile_json.
- Preserve formatting: Keep LaTeX structure stable. Minimal structural changes. Do not break compilation.
- Humanize + STAR bullets: rewrite experience and project bullets using STAR method (Situation, Task, Action, Result) BUT keep it concise and resume-appropriate.
- Quantify results: If a metric is not present in resume/profile_json, do NOT fabricate. Prefer wording like “improved,” “reduced,” “increased,” but only quantify if metrics exist in sources.
- Action verbs: Start each bullet with an action verb, avoid repeating the same action verb within a section (rotate verbs).
- One job at a time.
- Web research: Use web search tool for company mission and what product they are building; summarize it and incorporate relevant keywords into resume ONLY if truthful and aligned.
- Relevance linking: If applying to a company like LinkedIn, prefer adding projects from profile_json that match what they build (e.g., job automation tool) and rephrase them to align to JD.
- Domain restriction: none.
- Future: ATS scoring might be added later; design code to be extensible but do not implement complex scoring now—just include keyword coverage summary.

FEATURES TO IMPLEMENT:
A) Multi-file LaTeX handling
- Parse main.tex and recursively resolve \\input and \\include to collect editable tex files.
- Maintain file boundaries (edit each file, write updated versions to output folder mirroring structure).

B) Profile enrichment
- profile_json has:
  - skills: { "categories": { "Languages": [...], "Frameworks": [...], ... } } OR similar
  - projects: list of objects containing: name, description bullets, tech stack, links, optional metrics, tags
- Agent selects relevant skills/projects based on JD keywords.
- Add selected items into appropriate sections (Skills/Projects) without breaking LaTeX formatting.
- If project section exists, inject 1–3 most relevant projects (or rephrase existing to emphasize).
- Never duplicate a project already in resume.

C) Company research tool
- Implement a web search tool (prefer Tavily if API key exists; fallback to DDGS).
- If job_url exists, also fetch and parse page text lightly (requests + bs4) to extract company and role context.
- Summarize company mission + product focus + tech signals.
- Include citations in report.md with URLs.

D) Resume tailoring logic
- Extract JD keywords, responsibilities, and seniority signals.
- Map keywords to existing resume bullets/skills/projects.
- Rewrite bullets using STAR style, action verbs, and avoid repetition.
- Keep LaTeX stable; do not change custom macros unless necessary.
- Provide a “verification needed” list: every place where you imported something from profile_json or rephrased a claim significantly.

E) PDF compilation
- Compile output LaTeX to PDF locally.
- Prefer latexmk if available; fallback to pdflatex x2 runs.
- Capture compile logs; if compilation fails, return best-effort plus logs in report.md and leave the updated LaTeX files.
- Output path: output_pdf_path.

ARCHITECTURE REQUIREMENTS:
- Use LangGraph for orchestration:
  1) load_inputs
  2) analyze_jd
  3) infer_company_and_research
  4) load_resume_files
  5) load_profile_json
  6) plan_edits (structured plan)
  7) apply_edits (per file edits)
  8) compile_pdf
  9) generate_report
- Each node should be a pure function where possible, writing to state.
- Use Pydantic or TypedDict for state schema.
- Add clear logging.
- Provide CLI entrypoint:
  python tailor.py --jd jd.txt --resume_dir ./overleaf --profile profile.json --out_dir ./out --out_pdf ./out/resume.pdf --job_url "..." --company "..."
- Add requirements.txt.
- Include unit-testable helpers (e.g., tex include resolver, diff generation).
- Do NOT require any proprietary services. If OpenAI is used, read OPENAI_API_KEY. If Tavily is used, read TAVILY_API_KEY but keep it optional.
- Use langchain-openai for LLM wrapper.

PROMPTING REQUIREMENTS (LLM):
- Use structured outputs (JSON) whenever possible: plan, selected projects/skills, per-file edit instructions.
- Implement a strong “no fabrication” system prompt.
- Provide an action-verb rotation strategy in the prompt.
- Provide a LaTeX safety strategy: keep commands, environments, braces, and custom macros intact.

DELIVERABLE:
Return a complete repo layout as plain text, including:
- tailor.py (main)
- resume_agent/ (package)
  - graph.py
  - tools.py (web search + page fetch)
  - tex.py (multi-file resolver + read/write + diff)
  - profile.py (json loader + matcher)
  - prompts.py (system prompts)
  - compile.py (latex compile)
  - report.py (report generation)
  - utils.py
- requirements.txt
- README.md with setup and run instructions
- (Optional) tests/ with a couple unit tests for tex include resolver and project dedupe logic

IMPORTANT OUTPUT RULES:
- Output only the code/files content. No extra commentary.
- Use fenced code blocks per file, labeled with file path.
- Code must be runnable.
- Make reasonable assumptions and document them in README.md.
- Do not omit error handling.
