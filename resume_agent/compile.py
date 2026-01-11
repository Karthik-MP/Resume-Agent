# resume_agent/compile.py
import os
import subprocess


def compile_latex(workdir, main_tex, output_pdf):
    """Compile LaTeX document using latexmk or pdflatex."""
    logs = ""
    cmd = ["latexmk", "-pdf", "-interaction=nonstopmode", main_tex]
    try:
        proc = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True)
        logs += proc.stdout + proc.stderr
    except FileNotFoundError:
        # latexmk not found, fallback to pdflatex
        cmd = ["pdflatex", "-interaction=nonstopmode", main_tex]
        proc = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True)
        logs += proc.stdout + proc.stderr
        if proc.returncode == 0:
            # run twice for references
            proc2 = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True)
            logs += proc2.stdout + proc2.stderr
    # Move the generated PDF to the correct location with proper filename
    pdf_name = os.path.splitext(main_tex)[0] + ".pdf"
    pdf_path = os.path.join(workdir, pdf_name)
    if os.path.exists(pdf_path):
        try:
            # Ensure target directory exists
            os.makedirs(os.path.dirname(output_pdf), exist_ok=True)
            # Move and rename the PDF to the target location
            import shutil

            shutil.move(pdf_path, output_pdf)
            logs += f"\nPDF moved to: {output_pdf}\n"
        except Exception as e:
            logs += f"\nError moving PDF: {e}\n"
    else:
        logs += f"\nWarning: Generated PDF not found at {pdf_path}\n"
    return logs
