THRESHOLDS = {
    "confidence_score": 80,
    "quality_score": 80,
}


def extract_scores(content: str) -> dict[str, int]:
    scores = {
        "confidence_score": 0,
        "quality_score": 0,
    }
    for line in content.split("\n"):
        if line.startswith("Confidence Score:"):
            scores["confidence_score"] = int(line.split(":")[1].strip())
        if line.startswith("Quality Score:"):
            scores["quality_score"] = int(line.split(":")[1].strip())
    return scores


def scores_valid(scores: dict[str, int]) -> tuple[bool, str]:
    if scores["confidence_score"] < 0 or scores["confidence_score"] > 100:
        return False, "Confidence score must be between 0 and 100"
    if scores["quality_score"] < 0 or scores["quality_score"] > 100:
        return False, "Quality score must be between 0 and 100"
    return True, "Valid Scores"


def scores_passing(scores: dict[str, int]) -> tuple[bool, str]:
    if scores["confidence_score"] < THRESHOLDS["confidence_score"]:
        return False, "Confidence score is below threshold"
    if scores["quality_score"] < THRESHOLDS["quality_score"]:
        return False, "Quality score is below threshold"
    return True, "Scores are passing"


def confidence_score_passing(confidence_score: int) -> tuple[bool, str]:
    if confidence_score < THRESHOLDS["confidence_score"]:
        return False, "Confidence score is below threshold"
    return True, "Confidence score is passing"


def extract_verdict(content: str) -> str:
    lines = content.splitlines()
    for line in lines:
        if line.startswith("Verdict:"):
            return line.split(":")[1].strip()
    return ""
