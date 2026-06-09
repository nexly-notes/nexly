import subprocess


def run_pr_view() -> tuple[bool, str]:
    result = subprocess.run(
        [
            "gh",
            "pr",
            "view",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False, "PR not found"
    return True, "PR found"
