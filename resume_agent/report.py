# resume_agent/report.py
import os


def generate_report(state):
    lines = []
    lines.append("# ATS Keyword Alignment\n")
    # Determine matched keywords
    keywords = state.jd_keywords or []
    resume_text = ""
    if state.resume_files:
        for content in state.resume_files.values():
            resume_text += content + " "
    matched = [kw for kw in keywords if kw.lower() in resume_text.lower()]
    lines.append(
        f"Matched {len(matched)} of {len(keywords)} JD keywords: {', '.join(matched)}\n\n"
    )
    lines.append("## Changes\n")
    for change in state.changes:
        lines.append(f"- {change}\n")
    lines.append("\n## Sources\n")
    for src in state.citations or []:
        lines.append(f"- {src}\n")
    lines.append("\n## Verification Needed\n")
    for note in state.verification:
        lines.append(f"- {note}\n")
    return "".join(lines)
