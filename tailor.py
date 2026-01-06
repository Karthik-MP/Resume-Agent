# tailor.py
#!/usr/bin/env python3
import argparse
import os
import sys
import logging
from resume_agent.graph import build_graph, TailorState


def main():
    parser = argparse.ArgumentParser(
        description="Tailor a LaTeX resume to a job description."
    )
    parser.add_argument(
        "--jd", dest="jd", required=True, help="Path to job description text file"
    )
    parser.add_argument(
        "--job_url",
        dest="job_url",
        required=False,
        help="Job URL for company research",
        default=None,
    )
    parser.add_argument(
        "--resume_dir",
        dest="resume_dir",
        required=True,
        help="Path to root of LaTeX resume project directory",
    )
    parser.add_argument(
        "--profile",
        dest="profile",
        required=True,
        help="Path to user profile JSON file",
    )
    parser.add_argument(
        "--company",
        dest="company",
        required=False,
        help="Company name (optional)",
        default=None,
    )
    parser.add_argument(
        "--out_dir",
        dest="out_dir",
        required=True,
        help="Output directory for tailored resume files",
    )
    parser.add_argument(
        "--out_pdf",
        dest="out_pdf",
        required=True,
        help="Output path for compiled PDF resume",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info("Starting resume tailoring agent")

    # Initialize state
    state = TailorState(
        job_description_path=args.jd,
        job_url=args.job_url,
        company_name=args.company,
        resume_root_dir=args.resume_dir,
        profile_json_path=args.profile,
        output_dir=args.out_dir,
        output_pdf_path=args.out_pdf,
    )
    # Build and run LangGraph
    graph = build_graph()
    final_state = graph.invoke(state)
    # Write report and output PDF path
    if final_state.get("report_md"):
        report_path = os.path.join(state.output_dir, "report.md")
        with open(report_path, "w") as f:
            f.write(final_state["report_md"])
        logger.info(f"Report written to {report_path}")
    if final_state.get("compile_logs"):
        logger.info("LaTeX compilation logs captured")
    if os.path.exists(final_state.get("output_pdf_path", state.output_pdf_path)):
        logger.info(
            f"Compiled resume PDF at {final_state.get('output_pdf_path', state.output_pdf_path)}"
        )
    else:
        logger.error("PDF generation failed. See compile logs.")
    logger.info("Done.")


if __name__ == "__main__":
    main()
