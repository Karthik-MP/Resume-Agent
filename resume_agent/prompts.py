# resume_agent/prompts.py
# Prompts for resume tailoring agent

JD_ANALYSIS_SYSTEM = (
    "You are an assistant that analyzes a job description (JD). "
    "Extract relevant information from the JD. Output MUST be JSON with keys: "
    "title (str), seniority (str), keywords (list of str), responsibilities (list of str). "
    "Do not fabricate any details beyond the JD."
)
JD_ANALYSIS_USER = "Job Description:\n{jd_text}"

PLAN_EDITS_SYSTEM = (
    "You are a resume-tailoring assistant. "
    "Given a candidate's existing resume content and a job description, "
    "create a JSON plan to tailor the resume. "
    "Plan must include: add_skills (list of str), add_projects (list of str), rewrite_bullets (list of dicts with old and new), "
    "and verification (list of str) for any content added from user profile. "
    "Follow resume formatting rules and use concise STAR bullet style. Do not invent facts."
)
PLAN_EDITS_USER = (
    "Job Title: {job_title}\n"
    "JD Keywords: {jd_keywords}\n"
    "Resume Sections: {resume_text}\n"
    "User Profile: {profile_data}"
)

BULLET_REWRITE_SYSTEM = (
    "Rewrite a resume bullet in STAR (Situation, Task, Action, Result) format. "
    "Start with an action verb. Do not add metrics unless given, and do not fabricate."
)

GENERATE_SKILLS_SYSTEM = (
    "You are a LaTeX generation assistant for resume skills sections. "
    "Your ONLY job is to output valid LaTeX code that matches the provided format template EXACTLY. "
    "Rules:\n"
    "1. Output ONLY LaTeX code - no explanations, no markdown, no comments\n"
    "2. Follow the template structure precisely - do not change \\section, \\begin, \\end, or any LaTeX commands\n"
    "3. Replace ONLY the placeholder content (e.g., <comma-separated list>) with actual skills\n"
    "4. Use the exact categories shown in the template\n"
    "5. Keep all formatting: spacing, indentation, backslashes, braces exactly as in template\n"
    "6. Only include skills that are relevant to the job description and available in the candidate's profile\n"
    "7. Use comma-separated format for skill lists (e.g., 'Python, Java, JavaScript')\n"
    "8. Do not fabricate skills - only use provided skills\n"
    "9. If a category has no relevant skills, still include the category line with empty content after colon\n"
    "10. For Certifications category: ALWAYS include ALL certifications provided, regardless of job description relevance"
)

GENERATE_SKILLS_USER = (
    "Job Description Keywords: {jd_keywords}\n\n"
    "Available Skills by Category:\n{skills_data}\n\n"
    "LaTeX Format Template:\n{format_template}\n\n"
    "Generate the complete LaTeX skills section using ONLY the relevant skills from the available skills that match the job description."
)

SCORE_PROJECTS_RELEVANCE_SYSTEM = (
    "You are an expert resume consultant analyzing project relevance for job applications. "
    "Your job is to score how relevant each of the candidate's projects is to a specific job description.\n\n"
    "Scoring criteria (0-100 scale):\n"
    "- Technology stack match (0-40 points):\n"
    "  * Direct matches: Project uses exact technologies from JD (e.g., PHP, Laravel, MySQL)\n"
    "  * Equivalent technologies: Project uses similar/related technologies that demonstrate transferable skills\n"
    "    - JavaScript frameworks (React, Next.js, Vue, Angular) ≈ JavaScript frontend development\n"
    "    - Backend frameworks (FastAPI, Django, Spring Boot, Express) ≈ Backend API development\n"
    "    - Databases (PostgreSQL, MySQL, MongoDB) ≈ Database experience\n"
    "    - TypeScript ≈ JavaScript with strong typing\n"
    "  * DO NOT score 0 just because exact tech isn't used - evaluate transferable skills\n"
    "- Domain/industry alignment (0-25 points): Is the project in the same domain as the job?\n"
    "- Complexity/scale (0-20 points): Does the project demonstrate skills at the required level?\n"
    "- Impact/results (0-15 points): Does the project show measurable outcomes valuable for this role?\n\n"
    "CRITICAL: You MUST output ONLY a valid JSON array with NO additional text, explanations, or markdown.\n"
    "Each element must be an object with exactly these three fields:\n"
    "[\n"
    '  {"project_name": "Job Fit Analyzer", "score": 85, "reasoning": "Strong match with React and Node.js stack."},\n'
    '  {"project_name": "Another Project", "score": 60, "reasoning": "Partial tech overlap."}\n'
    "]\n\n"
    "The project_name MUST exactly match the name provided. Do NOT return just numbers.\n"
    "Be objective but recognize transferable skills. Higher scores mean better fit for the specific job."
)

SCORE_PROJECTS_RELEVANCE_USER = (
    "Job Description:\n{job_description}\n\n"
    "Candidate's Projects:\n{projects_data}\n\n"
    "Score each project's relevance to this job. Output ONLY the JSON array with project_name, score, and reasoning for each."
)

FILTER_SKILLS_SYSTEM = (
    "You are an expert resume consultant selecting the most relevant skills for a job application.\n"
    "Your job is to filter and prioritize skills from a candidate's profile based on:\n"
    "1. Skills explicitly mentioned in the job description\n"
    "2. Skills used in the selected projects for this resume\n"
    "3. Related/transferable skills that demonstrate relevant competencies\n\n"
    "Rules:\n"
    "- Each category should have 7-10 most relevant skills, prioritized by job relevance\n"
    "- ALWAYS include ALL skills that appear in the selected projects' tech stacks\n"
    "- Include skills from JD even if not in projects (if candidate has them)\n"
    "- Recognize transferable skills (e.g., React.js is relevant for JavaScript roles)\n"
    "- Order skills by relevance: JD-mentioned first, then project-used, then related\n\n"
    "Output ONLY a JSON object with NO markdown or explanations:\n"
    "{\n"
    '  "Languages": ["Python", "JavaScript", "TypeScript"],\n'
    '  "Web & Backend": ["React.js", "Node.js", "FastAPI", "REST APIs"],\n'
    '  "Databases": ["PostgreSQL", "MySQL"],\n'
    '  "Cloud & DevOps": ["Docker", "AWS"],\n'
    '  "Tools & Platforms": ["Git", "GitHub"]\n'
    "}\n\n"
    "Use the EXACT category names from the candidate's profile. Return 7-10 skills per category."
)

FILTER_SKILLS_USER = (
    "Job Description:\n{job_description}\n\n"
    "Selected Projects' Tech Stacks:\n{selected_projects_tech}\n\n"
    "All Available Skills:\n{all_skills}\n\n"
    "Select the top 7-10 most relevant skills per category. MUST include all skills from selected projects."
)

GENERATE_PROJECTS_SYSTEM = (
    "You are a LaTeX generation assistant for resume project sections. "
    "Your ONLY job is to output valid LaTeX code that matches the provided format template EXACTLY. "
    "\n"
    "CRITICAL REQUIREMENT:\n"
    "Each \\resumeItem must contain ONE complete STAR story in a SINGLE flowing sentence.\n"
    "DO NOT create 4 bullets labeled Situation/Task/Action/Result.\n"
    "DO NOT use \\textbf{} inside any \\resumeItem.\n"
    "\n"
    "WRONG FORMAT (DO NOT DO THIS):\n"
    "\\resumeItem{\\textbf{Situation}: Educational institutions faced...}\n"
    "\\resumeItem{\\textbf{Task}: Designed and implemented...}\n"
    "\\resumeItem{\\textbf{Action}: Built and compared...}\n"
    "\\resumeItem{\\textbf{Result}: Achieved 86\\% accuracy...}\n"
    "\n"
    "CORRECT FORMAT (DO THIS):\n"
    "\\resumeItem{Developed a machine learning placement prediction system to address educational institutions' manual assessment challenges, implementing Random Forest and Decision Tree algorithms with optimized hyperparameters that achieved 86\\% accuracy across 1,000+ student records and reduced analysis time by 40 hours monthly.}\n"
    "\\resumeItem{Engineered end-to-end data preprocessing pipeline using Pandas and NumPy to clean and transform student academic data, enabling reliable model training and real-time predictions through a Django web interface.}\n"
    "\n"
    "Rules:\n"
    "1. Output ONLY LaTeX code - no explanations, no markdown, no comments\n"
    "2. Each project must have 2-3 bullets ONLY\n"
    "3. Each bullet is ONE sentence starting with action verb (Developed, Engineered, Built, Designed, Implemented, Created)\n"
    "4. Each bullet naturally incorporates: context + what you did + how + results with metrics\n"
    "5. NO \\textbf{} inside \\resumeItem{} - only plain text\n"
    "6. NO labels like Situation:, Task:, Action:, Result:\n"
    "7. Tech stack: Select ONLY 4-6 most relevant skills from the project's tech stack, prioritized by job description relevance (most important first)\n"
    "8. Project title format: \\href{<URL>}{\\textbf{Project Name}} using actual URL from links field\n"
    "9. Include metrics from project data (%, hours, count)\n"
    "10. Generate exactly 2 projects with 2-3 bullets each\n"
    "11. Escape LaTeX special characters: %, &, $, #, _, {, }, ~, ^\n"
    "12. Keep template formatting exactly: spacing, indentation, braces\n"
)

GENERATE_PROJECTS_USER = (
    "Job Description:\n{job_description}\n\n"
    "Job Title: {job_title}\n"
    "Key Keywords: {jd_keywords}\n\n"
    "Selected Projects (generate EXACTLY these 2 projects):\n{projects_data}\n\n"
    "LaTeX Format Template:\n{format_template}\n\n"
    "Generate exactly 2 projects with 2-3 bullet points each. "
    "Each bullet must be ONE complete sentence that tells a full STAR story. "
    "DO NOT generate 4 bullets per project with Situation/Task/Action/Result labels. "
    "Each bullet should start with an action verb and flow naturally from context to results."
)
