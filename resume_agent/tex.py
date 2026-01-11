# resume_agent/tex.py
import os
import re


def resolve_includes(file_path):
    """Recursively find all files included by a LaTeX file via \\input or \\include."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except FileNotFoundError:
        return []
    includes = re.findall(r"\\(?:input|include)\{([^}]+)\}", content)
    paths = []
    for inc in includes:
        texfile = inc
        if not texfile.endswith(".tex"):
            texfile += ".tex"
        dir_path = os.path.dirname(file_path)
        inc_path = os.path.join(dir_path, texfile)
        if os.path.exists(inc_path):
            paths.append(inc_path)
            paths.extend(resolve_includes(inc_path))
    return list(set(paths))


def generate_diff(original_text, new_text):
    """Generate a unified diff between original and new text."""
    import difflib

    orig_lines = original_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    diff = difflib.unified_diff(orig_lines, new_lines, lineterm="")
    return "".join(diff)


def load_template(template_name, resume_root_dir):
    """
    Load a LaTeX template file from the templates directory.

    Args:
        template_name: Name of the template file (e.g., 'skills_format.tex')
        resume_root_dir: Root directory of the resume template

    Returns:
        Template content as a string

    Raises:
        FileNotFoundError: If template file doesn't exist
    """
    template_path = os.path.join(resume_root_dir, "templates", template_name)
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found: {template_path}")

    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()
