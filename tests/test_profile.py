# tests/test_profile.py
from resume_agent.profile import select_projects


def test_project_deduplication(tmp_path):
    # Prepare profile JSON with two projects, one with matching tag
    profile_data = {
        "projects": [
            {"name": "ProjA", "description": ["Test"], "tags": ["ml"]},
            {"name": "ProjB", "description": ["Other"], "tags": ["web"]},
        ]
    }
    keywords = ["machine", "learning", "web"]
    selected = select_projects(keywords, profile_data)
    # Should select ProjA and ProjB (ProjA by keyword 'learning', ProjB by 'web')
    names = [p["name"] for p in selected]
    assert "ProjA" in names and "ProjB" in names
