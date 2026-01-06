# tests/test_tex.py
import os
import tempfile
from resume_agent.tex import resolve_includes


def test_resolve_includes(tmp_path):
    # Create main.tex that includes section.tex
    main = tmp_path / "main.tex"
    section = tmp_path / "section.tex"
    main.write_text(
        "\\documentclass{article}\n\\begin{document}\n\\input{section}\n\\end{document}"
    )
    section.write_text("Section content")
    includes = resolve_includes(str(main))
    # Should find section.tex
    assert any("section.tex" in inc for inc in includes)
