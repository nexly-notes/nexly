import subprocess
from pathlib import Path  # type: ignore

GIT_TIMEOUT_SECONDS = 60


def run_git(
    args: list[str], cwd: Path, timeout: int = GIT_TIMEOUT_SECONDS
) -> subprocess.CompletedProcess:
    """
    Run ``git <args>`` inside *cwd* and return the result without raising.

    A timeout is mandatory in practice: the auto-commit hook and the
    PostToolUse path both call this synchronously and would otherwise hang
    the live session on a stuck git operation (e.g. a credential prompt
    with no TTY). On timeout we return a synthesized non-zero result so
    callers that check ``returncode`` fall through their error branch
    instead of seeing a raised exception.

    Args:
        args (list[str]): Argv tail (everything after ``git``).
        cwd (Path): Working directory for the git invocation.
        timeout (int): Max seconds before the subprocess is killed.

    Returns:
        subprocess.CompletedProcess: Fully populated result; callers inspect
        ``returncode``, ``stdout``, and ``stderr`` themselves.

    Example:
        >>> run_git(["status", "--porcelain"], Path.cwd())  # doctest: +SKIP
        Return: CompletedProcess(args=['git', 'status', '--porcelain'], returncode=0, ...)
    """
    try:
        # Capture text so callers can parse stdout/stderr without decoding bytes.
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        # Synthesize a non-zero result so callers treat timeout like any other git failure.
        return subprocess.CompletedProcess(
            args=e.cmd,
            returncode=124,
            stdout="",
            stderr=f"git timed out after {timeout}s",
        )
