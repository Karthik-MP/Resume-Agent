# resume_agent/graph.py
import os
import logging
import re
from typing import Optional, Dict
from pydantic import BaseModel
from langgraph.graph import StateGraph, START, END
from resume_agent.star import rewrite_star

from resume_agent import tools, tex, profile, report, prompts, compile as compile_module

logger = logging.getLogger(__name__)

# Project root directory (parent of resume_agent/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(PROJECT_ROOT, "SWE_Resume_Template")

# Framework to programming language mapping
FRAMEWORK_TO_LANGUAGE = {
    "spring boot": "Java",
    "spring": "Java",
    "jakarta ee": "Java",
    "hibernate": "Java",
    "django": "Python",
    "flask": "Python",
    "fastapi": "Python",
    "express": "JavaScript",
    "express.js": "JavaScript",
    "react": "JavaScript",
    "react.js": "JavaScript",
    "next.js": "JavaScript",
    "vue": "JavaScript",
    "vue.js": "JavaScript",
    "angular": "JavaScript",
    "node.js": "JavaScript",
    "nodejs": "JavaScript",
    ".net": "C#",
    "asp.net": "C#",
    "rails": "Ruby",
    "ruby on rails": "Ruby",
    "laravel": "PHP",
    "symfony": "PHP",
}


def get_required_languages(skills_text: str, jd_text: str) -> set:
    """
    Determine which programming languages should be included based on
    frameworks/technologies mentioned in skills or job description.
    """
    required_langs = set()
    combined_text = (skills_text + " " + jd_text).lower()
    
    for framework, language in FRAMEWORK_TO_LANGUAGE.items():
        if framework in combined_text:
            required_langs.add(language)
    
    return required_langs


def extract_experience_skills(resume_files: Dict[str, str]) -> set:
    """
    Extract technology keywords from the Experience section of resume LaTeX files.
    Returns a set of lowercase skill names found in experience bullets.
    """
    experience_skills = set()
    
    # Common technology keywords to look for (synced with profile.json)
    tech_keywords = [
        # Languages
        'python', 'java', 'javascript', 'typescript', 'sql', 'go', 'rust', 'kotlin', 'swift', 'c#', 'ruby', 'php',
        # Web & Backend
        'react', 'react.js', 'next.js', 'node.js', 'nodejs', 'express', 'express.js',
        'spring boot', 'spring batch', 'spring', 'spring security', 'spring data jpa',
        'fastapi', 'flask', 'django', 'html5', 'css3', 'tailwind css', 'tailwind', 'redux', 'axios', 'uvicorn',
        'tanstack react query', 'jwt', 'rest api', 'rest apis', 'websockets', 'microservices', 'xml',
        '.net', 'asp.net', 'laravel', 'rails', 'angular', 'vue', 'vue.js', 'graphql',
        # Data Science & ML
        'numpy', 'pandas', 'scikit-learn', 'sklearn', 'tensorflow', 'pytorch', 'seaborn', 'matplotlib',
        'opencv', 'time series analysis', 'geospatial analysis', 'data cleaning', 'exploratory data analysis',
        'data ethics', 'jupyter notebook', 'jupyter', 'lstm', 'random forest', 'decision trees',
        'wordcloud', 'spacy', 'nltk',
        # Databases
        'mysql', 'postgresql', 'postgres', 'mongodb', 'oracle', 'oracle db', 'nosql', 'timescaledb',
        'psycopg2', 'neo4j', 'cassandra', 'elasticsearch', 'sql server', 'redis', 'dynamodb',
        # Cloud & DevOps
        'aws', 'azure', 'gcp', 'google cloud platform', 'google cloud', 'docker', 'kubernetes', 'k8s',
        'ci/cd', 'cicd', 'jenkins', 'firebase', 'gitlab', 'github actions', 'terraform', 'ansible',
        # Tools & Technologies
        'git', 'github', 'linux', 'unix', 'postman', 'junit', 'adobe analytics', 'aem', 'aem cloud',
        'power bi', 'tableau', 'faktory', 'sqlx', 'google perspective api', 'perspective api',
        'react simple maps', 'copilotkit', 'langchain', 'llamaindex', 'maven',
        'openai', 'llm', 'llms', 'rag', 'vector database', 'etl', 'kafka', 'rabbitmq',
        'bootstrap', 'material-ui', 'json', 'yaml',
    ]
    
    # Search through all resume files for experience section
    for rel_path, content in resume_files.items():
        # Look for experience section
        if '\\section{Experience}' in content or '\\section{Work Experience}' in content:
            # Extract content between Experience section and next section
            experience_match = re.search(
                r'\\section\{(?:Work )?Experience\}(.*?)(?:\\section|\\end\{document\}|$)',
                content,
                re.DOTALL
            )
            
            if experience_match:
                experience_text = experience_match.group(1).lower()
                
                # Find all technology keywords mentioned
                for keyword in tech_keywords:
                    # Use word boundaries to avoid partial matches
                    if re.search(r'\b' + re.escape(keyword.lower()) + r'\b', experience_text):
                        experience_skills.add(keyword.lower())
    
    logger.info(f"Extracted {len(experience_skills)} skills from Experience section: {sorted(experience_skills)}")
    return experience_skills


class LLMQuotaExceededError(Exception):
    """Custom exception for LLM quota/rate limit errors."""
    pass


class TailorState(BaseModel):
    job_description_path: str
    job_url: Optional[str] = None
    company_name: Optional[str] = None
    resume_root_dir: str
    profile_json_path: str
    output_dir: str
    output_pdf_path: str

    job_description: Optional[str] = None
    jd_title: Optional[str] = None
    jd_keywords: Optional[list[str]] = None

    resume_files: Optional[Dict[str, str]] = None
    main_tex: Optional[str] = None  # ✅ ADD THIS

    profile_data: Optional[dict] = None
    company_summary: Optional[str] = None
    citations: Optional[list[str]] = None
    plan: Optional[dict] = None
    changes: list[str] = []
    verification: list[str] = []
    compile_logs: Optional[str] = None
    report_md: Optional[str] = None
    error_status: Optional[str] = None  # Track error state
    rate_limit_count: int = 0  # Track consecutive rate limit errors


def load_inputs(state: TailorState) -> dict:
    logger.info("Loading inputs")
    # Read job description text
    with open(state.job_description_path, "r", encoding="utf-8") as f:
        jd_text = f.read().strip()
    output = {"job_description": jd_text}

    # Clean output directory if it exists
    import shutil

    if os.path.exists(state.output_dir):
        logger.info(f"Removing existing output directory: {state.output_dir}")
        shutil.rmtree(state.output_dir)

    # Create fresh output directory
    os.makedirs(state.output_dir, exist_ok=True)
    logger.info(f"Created output directory: {state.output_dir}")
    return output


def analyze_jd(state: TailorState) -> dict:
    logger.info("Analyzing job description")
    # Use LLM to extract title and keywords (placeholder logic)
    lines = state.job_description.splitlines()
    title = lines[0] if lines else ""
    # len(words) > 4 to filter out short/common words such as "the", "and", etc.
    # instead of this create file with these words and load from there
    keywords = list(
        {word.strip(".,()") for word in state.job_description.split() if len(word) > 4}
    )
    output = {"jd_title": title, "jd_keywords": keywords}
    return output


def infer_company_and_research(state: TailorState) -> dict:
    logger.info("Inferring company information and researching")
    citations = []
    company = state.company_name
    if not company and state.job_url:
        company = state.job_url.split("//")[-1].split("/")[0]
    summary = ""
    if state.job_url:
        citations.append(state.job_url)
    query = f"{company} mission" if company else "company mission statement"
    search_res = tools.web_search(query, max_results=3)
    if isinstance(search_res, dict) and "text" in search_res:
        summary = search_res["text"]
        if "sources" in search_res:
            citations.extend(search_res["sources"])
    else:
        summary = str(search_res)
    # logger.info(f"Company research summary: {summary[:200]}...")
    # logger.info(f"Citations: {citations}")
    return {"company_summary": summary, "citations": citations}


def load_resume_files(state: TailorState) -> dict:
    logger.info("Loading LaTeX resume files")
    main_tex = None
    candidates = ["main.tex", "resume.tex", "cv.tex"]
    for cand in candidates:
        path = os.path.join(state.resume_root_dir, cand)
        if os.path.exists(path):
            main_tex = path
            break
    if not main_tex:
        for root, dirs, files in os.walk(state.resume_root_dir):
            for file in files:
                if file.endswith(".tex"):
                    with open(
                        os.path.join(root, file), "r", encoding="utf-8", errors="ignore"
                    ) as f:
                        content = f.read()
                        if "\\documentclass" in content:
                            main_tex = os.path.join(root, file)
                            break
            if main_tex:
                break
    if not main_tex:
        raise FileNotFoundError("Main .tex file not found in resume directory")
    paths = [main_tex] + tex.resolve_includes(main_tex)
    files_content = {}
    for path in set(paths):
        rel = os.path.relpath(path, state.resume_root_dir)
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            files_content[rel] = f.read()
    state.resume_files = files_content
    # store the main tex relative path on the state for later compile step
    state.main_tex = os.path.relpath(main_tex, state.resume_root_dir)
    state.plan = {}  # ensure plan exists
    return {"resume_files": files_content, "main_tex": state.main_tex}


def replace_skill_category(content: str, category: str, skills: list[str]) -> str:
    """
    Replaces skills inside:
    \\textbf{Category}{: existing skills}
    without touching LaTeX structure or font.
    """
    if not skills:
        return content
    # Match pattern: \textbf{Category}{: skills here}
    pattern = rf"(\\textbf\{{{category}\}}\{{:\s*)([^}}]+?)\s*\}}"
    replacement = rf"\g<1>{', '.join(skills)} }}"
    return re.sub(pattern, replacement, content)


def relevant_skills(profile_skills, project_tech, jd_keywords):
    return sorted(
        {
            s
            for s in profile_skills
            if s in project_tech or any(k.lower() in s.lower() for k in jd_keywords)
        }
    )


def load_profile_json(state: TailorState) -> dict:
    logger.info("Loading user profile JSON")
    profile_data = profile.load_profile(state.profile_json_path)
    return {"profile_data": profile_data}


def plan_edits(state: TailorState) -> dict:
    logger.info("Planning resume edits")

    jd_keywords = [k.lower() for k in (state.jd_keywords or [])]
    profile_data = state.profile_data

    # ---- 1. Select top 2 relevant projects using LLM scoring (batched) ----
    all_projects = profile_data.get("projects", [])
    relevant_projects = []

    # Batch all projects into a single LLM request
    if all_projects:
        try:
            # Prepare all projects data for single LLM call
            projects_data_str = ""
            for i, proj in enumerate(all_projects, 1):
                tech_stack_str = ", ".join(proj.get("tech_stack", []))
                tags_str = ", ".join(proj.get("tags", []))
                description_str = " ".join(proj.get("description", []))

                projects_data_str += f"{i}. Project: {proj.get('name', 'Untitled')}\n"
                projects_data_str += f"   Tech Stack: {tech_stack_str}\n"
                projects_data_str += f"   Tags: {tags_str}\n"
                projects_data_str += f"   Description: {description_str}\n\n"

            # Single LLM call to score all projects
            user_prompt = prompts.SCORE_PROJECTS_RELEVANCE_USER.format(
                job_description=state.job_description or "",
                projects_data=projects_data_str,
            )

            response = tools.call_llm(
                system_prompt=prompts.SCORE_PROJECTS_RELEVANCE_SYSTEM,
                user_prompt=user_prompt,
            )

            # Parse JSON array response
            import json
            import re

            # Clean response - remove markdown code blocks if present
            response_clean = response.strip()
            logger.debug(f"Project scoring response: {response_clean}")
            
            # Try to extract JSON from markdown code blocks (```json ... ``` or ``` ... ```)
            code_block_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response_clean, re.DOTALL)
            if code_block_match:
                response_clean = code_block_match.group(1).strip()
                logger.info("Extracted JSON from markdown code block in project scoring")
            elif response_clean.startswith("```"):
                # Fallback to old logic if regex doesn't match
                lines = response_clean.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                response_clean = "\n".join(lines).strip()

            # Try to parse JSON with error handling
            try:
                results = json.loads(response_clean)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error in project scoring: {e}")
                logger.error(f"Problematic response: {response_clean}")
                
                # Try to fix truncated JSON
                if response_clean.count("[") > response_clean.count("]"):
                    response_clean += "]" * (response_clean.count("[") - response_clean.count("]"))
                if response_clean.count("{") > response_clean.count("}"):
                    response_clean += "}" * (response_clean.count("{") - response_clean.count("}"))
                if response_clean.count('"') % 2 != 0:
                    response_clean += '"'
                
                try:
                    results = json.loads(response_clean)
                    logger.info("Successfully parsed JSON after fixes")
                except json.JSONDecodeError:
                    logger.error("Cannot parse JSON even after fixes. Using fallback.")
                    raise ValueError(f"Invalid JSON from LLM: {e}")

            # Handle if results is not a list
            if not isinstance(results, list):
                logger.warning(
                    f"Expected list from LLM, got {type(results).__name__}. Response: {response_clean[:200]}"
                )
                raise ValueError("LLM did not return a JSON array")

            # Match scores back to projects
            for result in results:
                if not isinstance(result, dict):
                    logger.warning(
                        f"Expected dict for project result, got {type(result).__name__}: {result}"
                    )
                    continue

                project_name = result.get("project_name", "")
                score = result.get("score", 0)
                reasoning = result.get("reasoning", "")

                # Find matching project
                for proj in all_projects:
                    if proj.get("name") == project_name:
                        logger.info(
                            f"Project '{project_name}' scored {score}/100: {reasoning}"
                        )
                        if score > 0:
                            relevant_projects.append((score, proj))
                        break

        except Exception as e:
            error_msg = str(e)
            
            # Check if this is a rate limit error - stop immediately
            if "RATE_LIMIT_EXCEEDED" in error_msg or "429" in error_msg:
                logger.error(f"Rate limit exceeded during project scoring. Stopping process.")
                state.error_status = f"ERROR: Rate limit exceeded. {error_msg}"
                raise Exception(f"RATE_LIMIT_EXCEEDED: Stopping due to repeated rate limit errors")
            
            logger.warning(
                f"Failed to score projects with LLM: {e}. Response snippet: {response[:200] if 'response' in locals() else 'N/A'}"
            )
            # Fallback: use all projects with default scores
            for proj in all_projects:
                relevant_projects.append((10, proj))

    relevant_projects.sort(reverse=True, key=lambda x: x[0])
    selected_projects = [p for _, p in relevant_projects[:2]]

    # ---- 2. Extract skills from existing resume Experience section ----
    experience_skills = extract_experience_skills(state.resume_files or {})
    logger.info(f"DEBUG: Extracted {len(experience_skills)} skills from Experience: {sorted(experience_skills)}")

    # ---- 3. Collect skills from JD, selected projects, and experience ----
    # Map profile categories to output categories
    category_mapping = {
        "Languages": "Languages",
        "Web & Backend": "Technologies",
        "Data Science & ML": "Technologies",
        "Databases": "Technologies",
        "Cloud & DevOps": "Tools",
        "Tools & Platforms": "Tools",
    }

    skills_by_category = {"Languages": [], "Technologies": [], "Tools": []}
    profile_skills = profile_data.get("skills", {})

    # Collect tech stack from selected projects
    project_tech = set()
    for proj in selected_projects:
        project_tech.update([t.lower() for t in proj.get("tech_stack", [])])

    # Get JD text for matching
    jd_text_lower = state.job_description.lower() if state.job_description else ""

    # Use LLM to intelligently filter skills
    try:
        # Prepare data for LLM
        projects_tech_str = ", ".join(sorted(project_tech))
        experience_skills_str = ", ".join(sorted(experience_skills))
        all_skills_str = ""
        for category, skills in profile_skills.items():
            all_skills_str += f"{category}: {', '.join(skills)}\n"

        user_prompt = prompts.FILTER_SKILLS_USER.format(
            job_description=state.job_description or "",
            selected_projects_tech=projects_tech_str,
            experience_skills=experience_skills_str,
            all_skills=all_skills_str,
        )

        response = tools.call_llm(
            system_prompt=prompts.FILTER_SKILLS_SYSTEM, user_prompt=user_prompt
        )

        # Parse JSON response
        import json

        response_clean = response.strip()

        # Log response for debugging
        if not response_clean:
            logger.warning("Empty response from LLM for skills filtering")
            raise ValueError("Empty LLM response")

        logger.info(f"DEBUG: LLM raw response length: {len(response_clean)} chars")
        logger.debug(f"Skills LLM response: {response_clean}")

        # Clean markdown code blocks if present - handle text before/after code block
        import re
        # Try to extract JSON from markdown code blocks (```json ... ``` or ``` ... ```)
        code_block_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response_clean, re.DOTALL)
        if code_block_match:
            response_clean = code_block_match.group(1).strip()
            logger.info("Extracted JSON from markdown code block")
        elif response_clean.startswith("```"):
            # Fallback to old logic if regex doesn't match
            lines = response_clean.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            response_clean = "\n".join(lines).strip()

        # Try to parse JSON with better error handling
        try:
            selected_skills = json.loads(response_clean)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            logger.error(f"Problematic response: {response_clean}")
            
            # Try to fix common JSON issues
            # 1. Try to complete truncated JSON arrays
            if response_clean.count("[") > response_clean.count("]"):
                logger.warning("Attempting to fix incomplete JSON arrays")
                response_clean += "]" * (response_clean.count("[") - response_clean.count("]"))
            
            # 2. Try to complete truncated JSON objects
            if response_clean.count("{") > response_clean.count("}"):
                logger.warning("Attempting to fix incomplete JSON objects")
                response_clean += "}" * (response_clean.count("{") - response_clean.count("}"))
            
            # 3. Try to close unterminated strings
            if response_clean.count('"') % 2 != 0:
                logger.warning("Attempting to fix unterminated string")
                response_clean += '"'
            
            # Try parsing again after fixes
            try:
                selected_skills = json.loads(response_clean)
                logger.info("Successfully parsed JSON after fixes")
            except json.JSONDecodeError as e2:
                logger.error(f"Still cannot parse JSON after fixes: {e2}")
                raise ValueError(f"Invalid JSON from LLM: {e2}")

        logger.info(f"DEBUG: LLM returned skills for {len(selected_skills)} categories")
        for cat, skills in selected_skills.items():
            logger.info(f"DEBUG: LLM category '{cat}': {len(skills)} skills = {skills}")

        # Map to output categories preserving LLM's priority order
        skills_by_category = {"Languages": [], "Technologies": [], "Tools": []}
        for category, skills in selected_skills.items():
            mapped_category = category_mapping.get(category)
            if mapped_category and skills:
                # Preserve LLM order - extend list instead of updating set
                for skill in skills:
                    if skill not in skills_by_category[mapped_category]:
                        skills_by_category[mapped_category].append(skill)
                logger.info(f"DEBUG: Mapped '{category}' -> '{mapped_category}': added skills preserving LLM order")

        logger.info("Skills filtered using LLM")
        logger.info(f"DEBUG: skills_by_category after LLM: {dict((k, sorted(v)) for k, v in skills_by_category.items())}")
        
        # CRITICAL: Force-add ALL experience skills that LLM may have missed
        # Match experience skills to profile and add them
        logger.info(f"DEBUG: Starting force-add of {len(experience_skills)} experience skills...")
        added_count = 0
        for exp_skill in experience_skills:
            found = False
            exp_skill_lower = exp_skill.lower().strip()
            
            # Try to find this skill in the profile with fuzzy matching
            for category, profile_skill_list in profile_skills.items():
                for profile_skill in profile_skill_list:
                    profile_skill_lower = profile_skill.lower().strip()
                    
                    # Match if: exact match, one contains the other, or very similar
                    is_match = (
                        exp_skill_lower == profile_skill_lower or
                        exp_skill_lower in profile_skill_lower or
                        profile_skill_lower in exp_skill_lower or
                        # Handle cases like "react" vs "react.js"
                        exp_skill_lower.replace('.', '') == profile_skill_lower.replace('.', '') or
                        # Handle "spring boot" vs "spring"
                        (exp_skill_lower.split()[0] == profile_skill_lower.split()[0] and len(exp_skill_lower.split()[0]) > 3)
                    )
                    
                    if is_match:
                        mapped_category = category_mapping.get(category)
                        if mapped_category:
                            if profile_skill not in skills_by_category.get(mapped_category, []):
                                skills_by_category[mapped_category].append(profile_skill)
                                logger.info(f"DEBUG: Force-added '{profile_skill}' to {mapped_category} (matched '{exp_skill}')")
                                added_count += 1
                            else:
                                logger.debug(f"DEBUG: '{profile_skill}' already in {mapped_category}")
                        else:
                            logger.warning(f"DEBUG: No mapping for category '{category}' containing '{profile_skill}'")
                        found = True
                        break
                if found:
                    break
            if not found:
                logger.warning(f"DEBUG: Experience skill '{exp_skill}' not found in profile skills")
        
        logger.info(f"DEBUG: Force-added {added_count} missing experience skills")
        logger.info(f"DEBUG: skills_by_category after force-add: {dict((k, sorted(v)) for k, v in skills_by_category.items())}")

        # CRITICAL: Force-add profile skills that are explicitly mentioned in the JD text.
        # Use word-boundary matching so "spring" in the JD does NOT accidentally pull in
        # "Spring Batch", "Spring Security", "Spring Data JPA" unless those exact phrases appear.
        logger.info("DEBUG: Starting force-add of JD-matched profile skills...")
        jd_matched_count = 0
        for category, profile_skill_list in profile_skills.items():
            mapped_category = category_mapping.get(category)
            if not mapped_category:
                continue
            for profile_skill in profile_skill_list:
                skill_lower = profile_skill.lower().strip()
                # Normalize variants for matching: "Node.js" → ["node.js", "node js"], "CI/CD" → ["ci/cd", "ci cd"]
                # Keep multi-word skills as full phrases so we require the full phrase in the JD.
                skill_variants = {
                    skill_lower,
                    skill_lower.replace(".", ""),   # "node.js" → "nodejs"
                    skill_lower.replace("/", " "),   # "ci/cd" → "ci cd"
                    skill_lower.replace(".js", ""),  # "react.js" → "react"
                }
                skill_variants = {v.strip() for v in skill_variants if len(v.strip()) > 2}
                # Use word-boundary regex so "java" doesn't match "javascript",
                # and "spring" doesn't match "spring boot" unless "spring" appears alone.
                matched = False
                for variant in skill_variants:
                    escaped = re.escape(variant)
                    if re.search(rf'\b{escaped}\b', jd_text_lower):
                        matched = True
                        break
                if matched:
                    if profile_skill not in skills_by_category.get(mapped_category, []):
                        skills_by_category[mapped_category].append(profile_skill)
                        logger.info(f"DEBUG: JD-matched force-added '{profile_skill}' to {mapped_category}")
                        jd_matched_count += 1
        logger.info(f"DEBUG: JD-matched force-added {jd_matched_count} profile skills mentioned in JD")
        logger.info(f"DEBUG: skills_by_category after JD-match force-add: {dict((k, sorted(v)) for k, v in skills_by_category.items())}")

        # Ensure required languages are included based on frameworks
        all_skills_text = " ".join(str(s) for skills in skills_by_category.values() for s in skills)
        required_languages = get_required_languages(all_skills_text, jd_text_lower)
        
        for lang in required_languages:
            if lang not in skills_by_category.get("Languages", []):
                # Check if language exists in profile
                for category, skills in profile_skills.items():
                    if lang in skills:
                        skills_by_category["Languages"].append(lang)
                        logger.info(f"DEBUG: Added {lang} to Languages (required by frameworks in JD/skills)")
                        break

    except Exception as e:
        error_msg = str(e)
        
        # Check if this is a rate limit error - stop immediately
        if "RATE_LIMIT_EXCEEDED" in error_msg or "429" in error_msg:
            logger.error(f"Rate limit exceeded during skills filtering. Stopping process.")
            state.error_status = f"ERROR: Rate limit exceeded. {error_msg}"
            raise Exception(f"RATE_LIMIT_EXCEEDED: Stopping due to repeated rate limit errors")
        
        # For critical LLM failures, stop the process instead of using fallback
        logger.error(
            f"Failed to filter skills with LLM: {e}. Response: {response[:300] if 'response' in locals() else 'N/A'}."
        )
        logger.error("CRITICAL: Cannot generate appropriate resume without LLM. Stopping process.")
        state.error_status = f"ERROR: LLM failure - {error_msg}"
        raise Exception(f"LLM_FAILURE: Cannot filter skills appropriately. {error_msg}")

    # Limit to 10 per category, preserving LLM's priority order (LLM puts JD matches first)
    skills_by_category = {k: v[:10] for k, v in skills_by_category.items() if v}
    
    logger.info(f"DEBUG: FINAL skills_by_category (limited to 10 each, LLM-prioritized): {skills_by_category}")
    for cat, skills in skills_by_category.items():
        logger.info(f"DEBUG: FINAL {cat}: {len(skills)} skills = {skills}")

    # ---- 3. Add all certifications from profile ----
    certifications = profile_data.get("certifications", [])
    if certifications:
        skills_by_category["Certifications"] = certifications

    plan = {"add_projects": selected_projects, "skills_by_category": skills_by_category}

    # ---- 3. Verification hooks ----
    for proj in selected_projects:
        state.verification.append(f"Verify project relevance: {proj['name']}")

    for cat, skills in skills_by_category.items():
        for s in skills:
            state.verification.append(f"Verify skill: {s}")

    return {"plan": plan}


def apply_edits(state: TailorState) -> dict:
    logger.info("Applying edits to LaTeX files")

    # Check if there was an error in previous steps
    if state.error_status:
        logger.error(f"Skipping apply_edits due to previous error: {state.error_status}")
        return {}

    # --- Copy original files to output dir first ---
    for rel_path, content in state.resume_files.items():
        dst_path = os.path.join(state.output_dir, rel_path)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        with open(dst_path, "w", encoding="utf-8") as f:
            f.write(content)

    # ---------- SKILLS (LLM-GENERATED FROM TEMPLATE) ----------
    for rel, content in state.resume_files.items():
        if "\\section{Technical Skills}" not in content:
            continue

        try:
            # Load the skills format template from project template directory
            logger.info(f"DEBUG: Loading skills template from: {os.path.join(TEMPLATE_DIR, 'templates')}")
            logger.info(f"DEBUG: Template exists: {os.path.exists(os.path.join(TEMPLATE_DIR, 'templates', 'skills_format.tex'))}")
            
            skills_template = tex.load_template(
                "skills_format.tex", TEMPLATE_DIR
            )

            # Get selected skills from plan
            skills_by_category = (state.plan or {}).get("skills_by_category", {})

            # Format skills data for LLM prompt
            skills_data_str = ""
            for category, skills in skills_by_category.items():
                skills_data_str += f"{category}: {', '.join(skills)}\n"

            logger.info(f"DEBUG: Sending {len(skills_by_category)} categories to skills generation LLM")
            logger.info(f"DEBUG: Skills data being sent:\n{skills_data_str}")

            # Call LLM to generate skills LaTeX
            user_prompt = prompts.GENERATE_SKILLS_USER.format(
                skills_data=skills_data_str,
                format_template=skills_template,
            )

            generated_skills_latex = tools.call_llm(
                system_prompt=prompts.GENERATE_SKILLS_SYSTEM, user_prompt=user_prompt
            )

            logger.info(f"DEBUG: Generated skills LaTeX length: {len(generated_skills_latex)} chars")
            logger.info(f"DEBUG: Generated skills LaTeX preview:\n{generated_skills_latex[:500]}")

            # Clean the output - strip markdown code fences if LLM added them
            generated_skills_latex = generated_skills_latex.strip()
            code_block_match = re.search(r'```(?:latex|tex)?\s*\n?(.*?)\n?```', generated_skills_latex, re.DOTALL)
            if code_block_match:
                generated_skills_latex = code_block_match.group(1).strip()
                logger.info("DEBUG: Stripped markdown code fences from skills LaTeX")
            elif generated_skills_latex.startswith("```"):
                lines = generated_skills_latex.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]  # remove opening fence
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]  # remove closing fence
                generated_skills_latex = "\n".join(lines).strip()

            logger.info(f"DEBUG: Cleaned skills LaTeX length: {len(generated_skills_latex)} chars")
            
            # Check if pattern exists in content before replacement
            pattern = r"%-*PROGRAMMING SKILLS-*%\s*\\section\{Technical Skills\}.*?\\end\{itemize\}"
            match = re.search(pattern, content, flags=re.DOTALL)
            if match:
                logger.info(f"DEBUG: Found existing skills section to replace (length: {len(match.group(0))} chars)")
                logger.info(f"DEBUG: Existing skills preview: {match.group(0)[:200]}")
            else:
                logger.warning(f"DEBUG: Skills section pattern NOT FOUND in {rel}")
                logger.warning(f"DEBUG: File content preview: {content[:500]}")

            # Replace the entire skills section
            # Use lambda to avoid backslash interpretation issues
            content = re.sub(
                pattern,
                lambda m: generated_skills_latex.strip(),
                content,
                flags=re.DOTALL,
            )
            
            logger.info(f"DEBUG: After replacement, checking if skills are in content...")
            if "Java, JavaScript, Python, SQL, TypeScript" in content:
                logger.info(f"DEBUG: ✓ Skills successfully replaced in content")
            else:
                logger.error(f"DEBUG: ✗ Skills NOT found in content after replacement!")
                logger.error(f"DEBUG: Content around Technical Skills: {content[content.find('Technical Skills')-100:content.find('Technical Skills')+500] if 'Technical Skills' in content else 'NOT FOUND'}")

            state.changes.append(
                "Generated skills section using LLM with custom template"
            )

        except Exception as e:
            error_msg = str(e)
            
            # Check if this is a rate limit error - stop immediately
            if "RATE_LIMIT_EXCEEDED" in error_msg or "429" in error_msg:
                logger.error(f"Rate limit exceeded during skills generation. Stopping process.")
                state.error_status = f"ERROR: Rate limit exceeded. {error_msg}"
                raise Exception(f"RATE_LIMIT_EXCEEDED: Stopping due to repeated rate limit errors")
            
            # Check if this is a quota exceeded error (not rate limit)
            if "QUOTA_EXCEEDED" in error_msg or "insufficient_quota" in error_msg.lower() or "quota exceeded" in error_msg.lower():
                logger.error(f"LLM quota exceeded: {e}")
                state.error_status = f"ERROR: LLM API quota exhausted. {error_msg}"
                raise LLMQuotaExceededError(f"LLM quota exceeded: {error_msg}")
            
            # For any other LLM failure, stop the process
            logger.error(f"Failed to generate skills with LLM: {e}")
            logger.error("CRITICAL: Cannot generate appropriate resume without LLM. Stopping process.")
            state.error_status = f"ERROR: Skills generation failed - {error_msg}"
            raise Exception(f"LLM_FAILURE: Cannot generate skills section. {error_msg}")

        state.resume_files[rel] = content
        logger.info(f"DEBUG: Updated state.resume_files[{rel}] with new skills content")

    # ---------- PROJECTS (LLM-GENERATED FROM TEMPLATE) ----------
    for rel, content in state.resume_files.items():
        if "\\section{Projects}" not in content:
            continue

        try:
            # Load the projects format template from project template directory
            projects_template = tex.load_template(
                "projects_format.tex", TEMPLATE_DIR
            )

            # Get selected projects from plan (max 2)
            selected_projects = state.plan.get("add_projects", [])[:2]

            if not selected_projects:
                logger.warning("No projects selected for resume")
                continue

            # Format projects data for LLM prompt
            projects_data_str = ""
            for i, proj in enumerate(selected_projects, 1):
                projects_data_str += f"Project {i}: {proj['name']}\n"
                projects_data_str += (
                    f"Tech Stack: {', '.join(proj.get('tech_stack', []))}\n"
                )
                # Add project link
                links = proj.get("links", [])
                if links:
                    projects_data_str += f"Link: {links[0]}\n"
                projects_data_str += "Description:\n"
                for desc in proj.get("description", []):
                    projects_data_str += f"  - {desc}\n"
                if proj.get("metrics"):
                    projects_data_str += "Metrics/Results:\n"
                    for metric in proj.get("metrics", []):
                        projects_data_str += f"  - {metric}\n"
                projects_data_str += "\n"

            # Get JD data
            jd_keywords_str = ", ".join(state.jd_keywords or [])
            job_title = state.jd_title or "the position"

            # Call LLM to generate projects LaTeX
            user_prompt = prompts.GENERATE_PROJECTS_USER.format(
                job_description=state.job_description[:1000]
                if state.job_description
                else "",  # Limit JD length
                job_title=job_title,
                jd_keywords=jd_keywords_str,
                projects_data=projects_data_str,
                format_template=projects_template,
            )

            generated_projects_latex = tools.call_llm(
                system_prompt=prompts.GENERATE_PROJECTS_SYSTEM, user_prompt=user_prompt
            )

            # Clean the output - strip markdown code fences if LLM added them
            generated_projects_latex = generated_projects_latex.strip()
            code_block_match = re.search(r'```(?:latex|tex)?\s*\n?(.*?)\n?```', generated_projects_latex, re.DOTALL)
            if code_block_match:
                generated_projects_latex = code_block_match.group(1).strip()
                logger.info("DEBUG: Stripped markdown code fences from projects LaTeX")
            elif generated_projects_latex.startswith("```"):
                lines = generated_projects_latex.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]  # remove opening fence
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]  # remove closing fence
                generated_projects_latex = "\n".join(lines).strip()

            # Replace the entire projects section
            # Use lambda to avoid backslash interpretation issues
            content = re.sub(
                r"%-*PROJECTS-*%\s*\\section\{Projects\}.*?(?=\\section|\Z)",
                lambda m: generated_projects_latex.strip(),
                content,
                flags=re.DOTALL,
            )

            for proj in selected_projects:
                state.changes.append(
                    f"Generated project '{proj['name']}' using LLM with custom template"
                )

        except Exception as e:
            error_msg = str(e)
            
            # Check if this is a rate limit error - stop immediately
            if "RATE_LIMIT_EXCEEDED" in error_msg or "429" in error_msg:
                logger.error(f"Rate limit exceeded during project generation. Stopping process.")
                state.error_status = f"ERROR: Rate limit exceeded. {error_msg}"
                raise Exception(f"RATE_LIMIT_EXCEEDED: Stopping due to repeated rate limit errors")
            
            # Check if this is a quota exceeded error (not rate limit)
            if "QUOTA_EXCEEDED" in error_msg or "insufficient_quota" in error_msg.lower() or "quota exceeded" in error_msg.lower():
                logger.error(f"LLM quota exceeded: {e}")
                state.error_status = f"ERROR: LLM API quota exhausted. {error_msg}"
                raise LLMQuotaExceededError(f"LLM quota exceeded: {error_msg}")
            
            # For any other LLM failure, stop the process
            logger.error(f"Failed to generate projects with LLM: {e}")
            logger.error("CRITICAL: Cannot generate appropriate resume without LLM. Stopping process.")
            state.error_status = f"ERROR: Projects generation failed - {error_msg}"
            raise Exception(f"LLM_FAILURE: Cannot generate projects section. {error_msg}")

        state.resume_files[rel] = content

    # ---------- WRITE UPDATED FILES ----------
    logger.info(f"DEBUG: Writing {len(state.resume_files)} updated files to {state.output_dir}")
    for rel, content in state.resume_files.items():
        out_path = os.path.join(state.output_dir, rel)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        # Verify skills are in the written file
        if "Technical Skills" in rel or "skills" in rel.lower():
            logger.info(f"DEBUG: Wrote skills file: {out_path}")
            if "Java, JavaScript, Python, SQL, TypeScript" in content:
                logger.info(f"DEBUG: ✓ Skills verified in written file {rel}")
            else:
                logger.error(f"DEBUG: ✗ Skills NOT in written file {rel}!")
        else:
            # Check if this is the main file that includes skills
            with open(out_path, 'r', encoding='utf-8') as verify_f:
                written_content = verify_f.read()
                if "Technical Skills" in written_content:
                    logger.info(f"DEBUG: File {rel} contains Technical Skills section")
                    if "Java, JavaScript, Python, SQL, TypeScript" in written_content:
                        logger.info(f"DEBUG: ✓ Skills verified in written file {rel}")
                    else:
                        logger.error(f"DEBUG: ✗ Skills NOT verified in written file {rel}!")
                        logger.error(f"DEBUG: Skills section preview: {written_content[written_content.find('Technical Skills')-100:written_content.find('Technical Skills')+500] if 'Technical Skills' in written_content else 'NOT FOUND'}")

    return {}


def compile_pdf(state: TailorState) -> dict:
    logger.info("Compiling LaTeX to PDF")

    # Check if there was an error in previous steps
    if state.error_status:
        logger.error(f"Skipping PDF compilation due to previous error: {state.error_status}")
        return {"compile_logs": state.error_status}

    if not state.main_tex:
        return {"compile_logs": "ERROR: main_tex not set. Cannot compile PDF."}

    # Generate dynamic filename: Username-CompanyName-Position-MM-YYYY.pdf
    from datetime import datetime
    import re

    # Extract username from profile
    username = state.profile_data.get("username", "Resume")

    # Extract company name (clean for filename)
    company = state.company_name or "Company"
    company_clean = re.sub(r"[^\w\-]", "", company.replace(" ", "-"))

    # Extract position from JD title (clean for filename)
    position = state.jd_title or "Position"
    # Take first few words if title is too long
    position_words = position.split()[:3]
    position_clean = re.sub(r"[^\w\-]", "", "-".join(position_words))

    # Get current date in MM-YYYY format
    date_str = datetime.now().strftime("%m-%Y")

    # Construct filename
    filename = f"{username}-{company_clean}-{position_clean}-{date_str}.pdf"

    # Update output_pdf_path with new filename
    output_dir = os.path.dirname(state.output_pdf_path)
    new_pdf_path = os.path.join(output_dir, filename)

    logger.info(f"Generating PDF: {filename}")

    logs = compile_module.compile_latex(state.output_dir, state.main_tex, new_pdf_path)

    # Update state with new path
    state.output_pdf_path = new_pdf_path
    
    # Log exact file locations
    logger.info("="*80)
    logger.info("📄 RESUME FILES GENERATED AT:")
    logger.info(f"  Output Directory: {state.output_dir}")
    logger.info(f"  PDF Location: {new_pdf_path}")
    logger.info(f"  Skills File: {os.path.join(state.output_dir, 'src/skills.tex')}")
    logger.info("="*80)

    return {"compile_logs": logs, "output_pdf_path": new_pdf_path}


def generate_report(state: TailorState) -> dict:
    logger.info("Generating report")
    
    # If there was an error, include it in the report
    if state.error_status:
        error_report = f"# Resume Generation Failed\n\n{state.error_status}\n\n"
        
        # Provide specific guidance based on error type
        if "rate limit" in state.error_status.lower() or "429" in state.error_status:
            error_report += "**Rate Limit Error:** Too many API requests in a short period.\n\n"
            error_report += "**Solutions:**\n"
            error_report += "- Wait a few minutes before trying again\n"
            error_report += "- Check if your API account has sufficient credits/quota\n"
            error_report += "- Verify your account status with your API provider\n"
            error_report += "- The error message above may indicate 'insufficient balance' - please recharge your account\n\n"
        else:
            error_report += "Please check your LLM API configuration and quota limits.\n\n"
            error_report += "**Common solutions:**\n"
            error_report += "- Check your LLM API provider account has sufficient credits\n"
            error_report += "- Verify your quota limits and plan details with your API provider\n"
            error_report += "- Check your API key is valid and properly configured\n\n"
        return {"report_md": error_report}
    
    report_text = report.generate_report(state)
    return {"report_md": report_text}


def build_graph():
    graph = StateGraph(TailorState)
    graph.add_node(load_inputs, name="load_inputs")
    graph.add_node(analyze_jd, name="analyze_jd")
    graph.add_node(infer_company_and_research, name="infer_company_and_research")
    graph.add_node(load_resume_files, name="load_resume_files")
    graph.add_node(load_profile_json, name="load_profile_json")
    graph.add_node(plan_edits, name="plan_edits")
    graph.add_node(apply_edits, name="apply_edits")
    graph.add_node(compile_pdf, name="compile_pdf")
    graph.add_node(generate_report, name="generate_report")

    graph.add_edge(START, "load_inputs")
    graph.add_edge("load_inputs", "analyze_jd")
    graph.add_edge("analyze_jd", "infer_company_and_research")
    graph.add_edge("infer_company_and_research", "load_resume_files")
    graph.add_edge("load_resume_files", "load_profile_json")
    graph.add_edge("load_profile_json", "plan_edits")
    graph.add_edge("plan_edits", "apply_edits")
    graph.add_edge("apply_edits", "compile_pdf")
    graph.add_edge("compile_pdf", "generate_report")
    graph.add_edge("generate_report", END)
    return graph.compile()
