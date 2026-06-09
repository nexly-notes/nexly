"""reviewer.py — Template-agnostic headless reviewer.

Drives a headless Claude or Codex agent through a self-correcting review
loop: each round parses the agent's JSONL output, asks a caller-supplied
conformance check whether the response is acceptable, and — if not —
feeds the check's feedback back as a correction prompt until the response
conforms or attempts are exhausted.

Both the conformance check and the correction-prompt builder are
parameters, so the same loop drives plan review, code review, or any
other format-gated review without knowing the format. The common
markdown-template case is handled by the ``template_tree_check``
factory included here.
"""

import json
from pathlib import Path
from typing import Callable
from typing_extensions import Literal


from lib.template_diff import trees_identical, build_md_tree  # type: ignore


# ---------------------------------------------------------------------------
# Constants + type aliases
# ---------------------------------------------------------------------------


ConformanceCheck = Callable[[str], tuple[bool, str]]
# Correction builders take the conformance feedback and return the next prompt.
CorrectionBuilder = Callable[[str], str]
_DIFF_SEPARATOR = "\n\n------------------------------------\n\n"


# ---------------------------------------------------------------------------
# Conformance-check factory for the common markdown-template case
# ---------------------------------------------------------------------------


def template_conformance_check(actual_content: str, template: str) -> tuple[bool, str]:
    """
    Build a ConformanceCheck that matches responses against *template*'s md tree.

    The returned callable reads *template* each invocation so callers can
    edit the template mid-session and pick up the new structure without
    rebuilding the check.

    Args:
        template (Path): Path to the markdown template file.

    Returns:
        ConformanceCheck: ``(response) -> (is_ok, stitched_diff_str)``.

    Raises:
        FileNotFoundError: When the check is *called* and *template* is missing.

    Example:
        >>> check = template_tree_check(Path("plan.md"))  # doctest: +SKIP
        >>> check("# Wrong")  # doctest: +SKIP
        (False, '...')
        Return: (False, '...')
    """

    template_tree = build_md_tree(template)
    response_tree = build_md_tree(actual_content)
    ok, diff = trees_identical(template_tree, response_tree)

    return ok, _DIFF_SEPARATOR.join(diff)


def scores_present(actual_content: str) -> tuple[bool, dict[str, str]]:
    """
    Check if the actual content contains scores.
    """

    lines = actual_content.splitlines()

    confidence_score = ""
    quality_score = ""

    for line in lines:
        if line.startswith("Confidence Score:"):
            confidence_score = line.split(":")[1].strip()
        if line.startswith("Quality Score:"):
            quality_score = line.split(":")[1].strip()

    if not confidence_score or not quality_score:
        return False, {}

    return True, {
        "confidence_score": confidence_score,
        "quality_score": quality_score,
    }


def verdict_present(actual_content: str) -> tuple[bool, str]:
    """
    Check if the actual content contains a verdict.
    """
    lines = actual_content.splitlines()
    verdict = ""
    for line in lines:
        if line.startswith("Verdict:"):
            verdict = line.split(":")[1].strip()

    if verdict not in ["Pass", "Fail"]:
        return False, ""

    return True, verdict


def template_conformance_check_fn(template: str) -> ConformanceCheck:

    def _check(response: str) -> tuple[bool, str]:
        # Tree-level compare so trivial whitespace/wording drift doesn't retrigger a round.
        ok, diff = trees_identical(
            build_md_tree(template),
            build_md_tree(response),
        )
        return ok, _DIFF_SEPARATOR.join(diff)

    return _check
