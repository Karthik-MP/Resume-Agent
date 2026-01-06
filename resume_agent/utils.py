# resume_agent/utils.py
def run_process(cmd, cwd=None):
    import subprocess

    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr
