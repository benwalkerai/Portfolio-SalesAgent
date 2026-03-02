"""
Email scoring primitives.

Author: Ben Walker (BenRWalker@icloud.com)
"""

from dataclasses import dataclass

CTA_KEYWORDS = {"call", "demo", "meeting", "chat", "reply", "schedule", "respond"}


@dataclass
class EmailCandidate:
    agent_name: str
    subject: str
    body: str
    raw_output: str
    score: float


def _score_email(subject: str, body: str) -> float:
    score = 0.0
    subject_length = len(subject.strip())
    body_words = body.split()
    word_count = len(body_words)

    if subject_length:
        score += 25
        if 25 <= subject_length <= 80:
            score += 5

    if 80 <= word_count <= 220:
        score += 35
    else:
        deviation = abs(150 - word_count)
        score += max(10, 35 - deviation * 0.2)

    paragraph_count = max(1, body.count("\n\n") + 1)
    if paragraph_count >= 3:
        score += 10
    elif paragraph_count == 2:
        score += 6

    personalization_hits = sum(body.lower().count(term) for term in ("you", "your"))
    score += min(personalization_hits * 2, 10)

    if any(keyword in body.lower() for keyword in CTA_KEYWORDS):
        score += 10

    return round(score, 2)
