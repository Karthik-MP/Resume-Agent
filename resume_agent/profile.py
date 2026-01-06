# resume_agent/profile.py
import json


def load_profile(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def select_skills(jd_keywords, profile_data):
    skills = []
    categories = profile_data.get("skills", {})
    for cat, sk_list in categories.items():
        for skill in sk_list:
            if any(
                kw.lower() in skill.lower() or skill.lower() in kw for kw in jd_keywords
            ):
                skills.append(skill)
    return list(set(skills))


def select_projects(jd_keywords, profile_data):
    relevant = []
    projects = profile_data.get("projects", [])
    for proj in projects:
        name = proj.get("name", "")
        description = " ".join(proj.get("description", []))
        tags = proj.get("tags", [])
        content = f"{name} {description} {' '.join(tags)}".lower()
        if any(kw.lower() in content for kw in jd_keywords):
            relevant.append(proj)
    return relevant
