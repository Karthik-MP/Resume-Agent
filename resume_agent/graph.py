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

            # Clean response - remove markdown code blocks if present
            response_clean = response.strip()
            if response_clean.startswith("```"):
                lines = response_clean.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                response_clean = "\n".join(lines).strip()

            results = json.loads(response_clean)

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
            logger.warning(
                f"Failed to score projects with LLM: {e}. Response snippet: {response[:200] if 'response' in locals() else 'N/A'}"
            )
            # Fallback: use all projects with default scores
            for proj in all_projects:
                relevant_projects.append((10, proj))

    relevant_projects.sort(reverse=True, key=lambda x: x[0])
    selected_projects = [p for _, p in relevant_projects[:2]]

    # ---- 2. Collect skills ONLY that are relevant to JD ----
    # Map profile categories to output categories
    category_mapping = {
        "Languages": "Languages",
        "Web & Backend": "Technologies",
        "Data Science & ML": "Technologies",
        "Databases": "Technologies",
        "Cloud & DevOps": "Tools",
        "Tools & Platforms": "Tools",
    }

    skills_by_category = {"Languages": set(), "Technologies": set(), "Tools": set()}
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
        all_skills_str = ""
        for category, skills in profile_skills.items():
            all_skills_str += f"{category}: {', '.join(skills)}\n"

        user_prompt = prompts.FILTER_SKILLS_USER.format(
            job_description=state.job_description or "",
            selected_projects_tech=projects_tech_str,
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

        logger.debug(f"Skills LLM response (first 200 chars): {response_clean[:200]}")

        if response_clean.startswith("```"):
            lines = response_clean.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            response_clean = "\n".join(lines).strip()

        selected_skills = json.loads(response_clean)

        # Map to output categories and limit to 7-10 per category
        for category, skills in selected_skills.items():
            mapped_category = category_mapping.get(category)
            if mapped_category and skills:
                # Limit to top 10 skills per category
                skills_by_category[mapped_category].update(skills[:10])

        logger.info("Skills filtered using LLM")

    except Exception as e:
        logger.warning(
            f"Failed to filter skills with LLM: {e}. Response: {response[:300] if 'response' in locals() else 'N/A'}. Using fallback method."
        )
        # Fallback: Include skills from projects + JD matches
        for category, skills in profile_skills.items():
            mapped_category = category_mapping.get(category)
            if not mapped_category:
                continue

            for skill in skills:
                skill_lower = skill.lower()

                # Include if: in project tech, in JD keywords, or exact match in JD
                is_in_projects = skill_lower in project_tech
                is_in_jd = any(
                    keyword in skill_lower or skill_lower in keyword
                    for keyword in jd_keywords
                    if len(keyword) > 2
                )
                is_exact_match = skill_lower in jd_text_lower

                if is_in_projects or is_in_jd or is_exact_match:
                    skills_by_category[mapped_category].add(skill)

    # Convert sets to sorted lists and limit to 10 per category
    skills_by_category = {k: sorted(v)[:10] for k, v in skills_by_category.items() if v}

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
            # Load the skills format template
            skills_template = tex.load_template(
                "skills_format.tex", state.resume_root_dir
            )

            # Get selected skills from plan
            skills_by_category = (state.plan or {}).get("skills_by_category", {})

            # Format skills data for LLM prompt
            skills_data_str = ""
            for category, skills in skills_by_category.items():
                skills_data_str += f"{category}: {', '.join(skills)}\n"

            # Get JD keywords
            jd_keywords_str = ", ".join(state.jd_keywords or [])

            # Call LLM to generate skills LaTeX
            user_prompt = prompts.GENERATE_SKILLS_USER.format(
                jd_keywords=jd_keywords_str,
                skills_data=skills_data_str,
                format_template=skills_template,
            )

            generated_skills_latex = tools.call_llm(
                system_prompt=prompts.GENERATE_SKILLS_SYSTEM, user_prompt=user_prompt
            )

            # Clean the output (remove any markdown code blocks if present)
            generated_skills_latex = generated_skills_latex.strip()
            if generated_skills_latex.startswith("```"):
                lines = generated_skills_latex.split("\n")
                # Remove first and last lines if they're code fence markers
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                generated_skills_latex = "\n".join(lines)

            # Replace the entire skills section
            # Use lambda to avoid backslash interpretation issues
            content = re.sub(
                r"%-*PROGRAMMING SKILLS-*%\s*\\section\{Technical Skills\}.*?\\end\{itemize\}",
                lambda m: generated_skills_latex.strip(),
                content,
                flags=re.DOTALL,
            )

            state.changes.append(
                "Generated skills section using LLM with custom template"
            )

        except Exception as e:
            logger.warning(f"Failed to generate skills with LLM: {e}")
            # Fallback to old method if LLM generation fails
            skills_by_category = (state.plan or {}).get("skills_by_category", {})
            content = replace_skill_category(
                content, "Languages", skills_by_category.get("Languages", [])
            )
            content = replace_skill_category(
                content, "Technologies", skills_by_category.get("Technologies", [])
            )
            content = replace_skill_category(
                content, "Tools \\& Platforms", skills_by_category.get("Tools", [])
            )
            state.changes.append(
                "Used fallback method for skills (LLM generation failed)"
            )

        state.resume_files[rel] = content

    # ---------- PROJECTS (LLM-GENERATED FROM TEMPLATE) ----------
    for rel, content in state.resume_files.items():
        if "\\section{Projects}" not in content:
            continue

        try:
            # Load the projects format template
            projects_template = tex.load_template(
                "projects_format.tex", state.resume_root_dir
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

            # Clean the output (remove any markdown code blocks if present)
            generated_projects_latex = generated_projects_latex.strip()
            if generated_projects_latex.startswith("```"):
                lines = generated_projects_latex.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                generated_projects_latex = "\n".join(lines)

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
            logger.warning(f"Failed to generate projects with LLM: {e}")
            # Fallback to old method if LLM generation fails
            selected_projects = state.plan.get("add_projects", [])[:2]
            project_blocks = []

            for proj in selected_projects:
                name = proj["name"]
                tech = ", ".join(proj.get("tech_stack", []))
                used_verbs = set()
                bullets = rewrite_star(proj, used_verbs)
                bullet_tex = "\n".join(f"    \\resumeItem{{{b}}}" for b in bullets)

                block = f"""
            \\resumeProjectHeading
            {{\\textbf{{{name}}} $|$ \\emph{{{tech}}}}}{{}}
            \\resumeItemListStart
            {bullet_tex}
            \\resumeItemListEnd
            """
                project_blocks.append(block.strip())
                state.changes.append(f"Selected project '{name}' (fallback method)")

            new_projects_section = "\\section{Projects}\n\n" + "\n\n".join(
                project_blocks
            )
            content = re.sub(
                r"\\section\{Projects\}.*?(?=\\section|\Z)",
                lambda m: new_projects_section,
                content,
                flags=re.S,
            )

        state.resume_files[rel] = content

    # ---------- WRITE UPDATED FILES ----------
    for rel, content in state.resume_files.items():
        out_path = os.path.join(state.output_dir, rel)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)

    return {}


def compile_pdf(state: TailorState) -> dict:
    logger.info("Compiling LaTeX to PDF")

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

    return {"compile_logs": logs, "output_pdf_path": new_pdf_path}


def generate_report(state: TailorState) -> dict:
    logger.info("Generating report")
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
