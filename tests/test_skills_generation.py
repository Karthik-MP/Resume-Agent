"""
Test skills generation with LLM
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from resume_agent import tex, prompts, tools


def test_load_template():
    """Test loading the skills template"""
    resume_root = os.path.join(os.path.dirname(__file__), "..", "SWE_Resume_Template")

    try:
        template = tex.load_template("skills_format.tex", resume_root)
        print("✓ Template loaded successfully")
        print(f"\nTemplate preview:\n{template[:200]}...")
        assert "<comma-separated list>" in template
        print("✓ Template contains expected placeholders")
        return True
    except FileNotFoundError as e:
        print(f"✗ Template not found: {e}")
        return False


def test_skills_prompt_format():
    """Test that the skills prompt is properly formatted"""
    jd_keywords = "Python, React, AWS, Docker"
    skills_data = """Languages: Python, JavaScript, Java
Technologies: React.js, Node.js, Express.js
Tools: Docker, AWS, Git"""
    format_template = "\\section{Technical Skills}\n..."

    user_prompt = prompts.GENERATE_SKILLS_USER.format(
        jd_keywords=jd_keywords,
        skills_data=skills_data,
        format_template=format_template,
    )

    print("✓ Prompt formatting works")
    print(f"\nPrompt preview:\n{user_prompt[:200]}...")

    assert jd_keywords in user_prompt
    assert skills_data in user_prompt
    assert format_template in user_prompt
    print("✓ All components included in prompt")
    return True


def test_llm_call():
    """Test LLM call (requires API key)"""
    if not os.environ.get("OPENAI_API_KEY"):
        print("⚠ Skipping LLM test - OPENAI_API_KEY not set")
        print("  Set it with: export OPENAI_API_KEY='your-key'")
        return None

    try:
        # Simple test prompt
        system_prompt = "You are a helpful assistant. Respond with only 'OK'."
        user_prompt = "Say OK"

        response = tools.call_llm(system_prompt, user_prompt)
        print("✓ LLM call successful")
        print(f"  Response: {response[:100]}")
        return True
    except Exception as e:
        print(f"✗ LLM call failed: {e}")
        return False


def test_full_skills_generation():
    """Test complete skills generation flow (requires API key)"""
    if not os.environ.get("OPENAI_API_KEY"):
        print("⚠ Skipping full test - OPENAI_API_KEY not set")
        return None

    resume_root = os.path.join(os.path.dirname(__file__), "..", "SWE_Resume_Template")

    try:
        # Load template
        template = tex.load_template("skills_format.tex", resume_root)

        # Prepare test data
        jd_keywords = "Python, React, AWS, Docker, Kubernetes"
        skills_data = """Languages: Python, JavaScript, TypeScript, Java
Technologies: React.js, Node.js, Express.js, FastAPI
Tools: Docker, Kubernetes, AWS, Git, Jenkins"""

        # Format prompt
        user_prompt = prompts.GENERATE_SKILLS_USER.format(
            jd_keywords=jd_keywords, skills_data=skills_data, format_template=template
        )

        # Call LLM
        generated_latex = tools.call_llm(prompts.GENERATE_SKILLS_SYSTEM, user_prompt)

        print("✓ Skills generation successful")
        print(f"\nGenerated LaTeX:\n{generated_latex}")

        # Verify output
        assert "\\section{Technical Skills}" in generated_latex
        assert "Python" in generated_latex or "JavaScript" in generated_latex
        print("✓ Output contains expected LaTeX structure and skills")

        return True
    except Exception as e:
        print(f"✗ Skills generation failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Skills Generation System")
    print("=" * 60)

    results = []

    print("\n[1/4] Testing template loading...")
    results.append(test_load_template())

    print("\n[2/4] Testing prompt formatting...")
    results.append(test_skills_prompt_format())

    print("\n[3/4] Testing LLM connection...")
    results.append(test_llm_call())

    print("\n[4/4] Testing full skills generation...")
    results.append(test_full_skills_generation())

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for r in results if r is True)
    skipped = sum(1 for r in results if r is None)
    failed = sum(1 for r in results if r is False)

    print(f"Passed:  {passed}")
    print(f"Skipped: {skipped}")
    print(f"Failed:  {failed}")

    if failed > 0:
        print("\n⚠ Some tests failed. Check output above for details.")
        sys.exit(1)
    elif skipped > 0:
        print("\n⚠ Some tests skipped. Set OPENAI_API_KEY to run all tests.")
    else:
        print("\n✓ All tests passed!")
