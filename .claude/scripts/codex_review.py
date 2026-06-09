"""Code review script.

Runs the code review phase of the workflow.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Literal
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent))


PROMPTS_DIR = Path.cwd() / "claude-3PO" / "prompts" / "claude"

CONFIG_MAP: dict[str, dict[str, Any]] = {
    "code_review": {
        "prompt": PROMPTS_DIR / "code_review.md",
        "schema": Path.cwd() / "claude-3PO" / "schemas" / "code_review.json",
    },
    "security": {
        "prompt": PROMPTS_DIR / "security_review.md",
        "schema": Path.cwd() / "claude-3PO" / "schemas" / "security_review.json",
    },
    "requirements": {
        "prompt": PROMPTS_DIR / "requirements_review.md",
        "schema": Path.cwd() / "claude-3PO" / "schemas" / "requirements_review.json",
    },
}

PR_CONTENT = os.environ.get("PR_CONTENT", "")

PR_NUMBER = os.environ.get("PR_NUMBER", "")

TEST_MODE = os.environ.get("TEST_MODE", "false").lower() == "true"


@dataclass(frozen=True, slots=True)
class CodexConfig:

    session_id: str | None = None
    output_schema: Path | None = None
    json_output: bool = False
    model: str | None = None
    skip_git_repo_check: bool = True


def build_codex_argv(prompt: str, options: CodexConfig) -> list[str]:
    argv = ["codex", "exec"]
    # `codex exec resume <id>` — the resume subcommand must come right after `exec`,
    # before any flags or the prompt.
    if options.session_id:
        argv.extend(["resume", options.session_id])
    if options.skip_git_repo_check:
        argv.append("--skip-git-repo-check")
    if options.model:
        argv.extend(["--model", options.model])
    if options.json_output:
        argv.append("--json")
    if options.output_schema:
        argv.extend(["--output-schema", str(options.output_schema)])
    argv.append(prompt)
    return argv


def run_headless_codex(commands: list[list[str]]) -> list[str]:
    """Run commands in parallel, return their stdouts; raise on any non-zero exit.

    Raises RuntimeError with argv, returncode and stderr of the first failing
    command so CI logs surface the real error instead of a generic "failed".
    """
    procs = [
        subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for cmd in commands
    ]
    results = [(p.wait(), *p.communicate()) for p in procs]
    for cmd, (rc, stdout, stderr) in zip(commands, results):
        if rc != 0:
            # codex sometimes writes the failure on stdout (json mode) and
            # sometimes on stderr — surface both so CI never silently truncates.
            raise RuntimeError(
                f"codex exited {rc} for {cmd!r}\n"
                f"stdout:\n{stdout}\nstderr:\n{stderr}"
            )
    return [stdout for (_rc, stdout, _stderr) in results]


class CodexReview:

    def __init__(self, pr: str, test_mode: bool = False):
        self.pr = pr
        self.test_mode = test_mode

    @property
    def test_mode_prompt(self) -> str:
        prompt = f"""
        We are in test mode. Create a mock review. Please inform if 'THIS IS A TEST. NO PR BODY' is present as a PR BODY and if PR NUMBER is 1.
        Please follow the structured_output schema when creating a mock review.
        """
        return prompt

    def build_argv(self) -> list[list[str]]:
        argv: list[list[str]] = []
        for cfg in CONFIG_MAP.values():
            prompt = (
                cfg.get("prompt", "").read_text().format(pr=self.pr)
                if not self.test_mode
                else self.test_mode_prompt
            )
            schema_path = cfg.get("schema", "")
            codex_config = CodexConfig(model="gpt-5.4", output_schema=schema_path)
            argv.append(build_codex_argv(prompt, codex_config))

        return argv

    def run(self) -> list[str]:
        results = run_headless_codex(self.build_argv())
        if not results:
            raise Exception("Headless Cli failed")

        return results


def get_confidence_score(response: str) -> int:
    structured_output = json.loads(response)
    confidence_score = structured_output.get("confidence_score", 0)
    return confidence_score


def get_report(response: str) -> str:
    structured_output = json.loads(response)
    return structured_output.get("report", "")


def run_pr_review(
    decision: Literal["approve", "request-changes"], body: str, test_mode: bool = False
) -> None:
    flag = "--approve" if decision == "approve" else "--request-changes"
    command = ["gh", "pr", "review", PR_NUMBER, flag, "-b", body]

    if test_mode:
        print(f"Simulating {decision} review")
        return

    subprocess.run(command, check=True, text=True)


def main() -> None:
    code_review = CodexReview(pr=PR_CONTENT, test_mode=TEST_MODE)
    output = code_review.run()

    for result in output:
        confidence_score = get_confidence_score(result)
        report = get_report(result)
        decision: Literal["approve", "request-changes"] = (
            "request-changes" if confidence_score < 80 else "approve"
        )
        run_pr_review(decision=decision, body=report, test_mode=TEST_MODE)


if __name__ == "__main__":
    main()
