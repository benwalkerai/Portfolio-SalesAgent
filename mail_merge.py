"""
Mail-merge and email text parsing utilities.

Author: Ben Walker (BenRWalker@icloud.com)
"""

import json
import re
from html import escape
from typing import Tuple


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped


def _plain_text_to_html(text: str) -> str:
    paragraphs = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        paragraphs.append(f"<p>{escape(block).replace('\n', '<br>')}</p>")
    if not paragraphs:
        return f"<p>{escape(text.strip())}</p>" if text.strip() else ""
    return "".join(paragraphs)


def _ensure_html_body(body_text: str) -> str:
    stripped = body_text.lstrip()
    if stripped.startswith("<") and stripped.endswith(">"):
        return body_text
    return _plain_text_to_html(body_text)


def _apply_mail_merge(text: str, recipient_name: str, sender_name: str) -> str:
    if not text:
        return text

    recipient_value = recipient_name or "there"
    sender_value = sender_name or "Your team"

    replacements = {
        "[recipient name]": recipient_value,
        "[recpient name]": recipient_value,
        "[recipient]": recipient_value,
        "[recipient_first_name]": recipient_value,
        "[your name]": sender_value,
        "[sender name]": sender_value,
        "[from name]": sender_value,
        "[team name]": sender_value,
    }

    lowercase_replacements = {key.lower(): value for key, value in replacements.items()}
    pattern = re.compile("|".join(re.escape(key) for key in lowercase_replacements), re.IGNORECASE)

    def _replace(match: re.Match[str]) -> str:
        return lowercase_replacements.get(match.group(0).lower(), match.group(0))

    return pattern.sub(_replace, text)


def _parse_agent_email_output(agent_output: str) -> Tuple[str, str]:
    default_subject = "Sales Email"
    cleaned = agent_output.strip()
    subject: str | None = None
    body: str | None = None
    candidate = _strip_code_fences(cleaned)

    try:
        data = json.loads(candidate)
        if isinstance(data, dict):
            subject = data.get("subject") or data.get("subject_line") or data.get("title")
            body = (
                data.get("html_body")
                or data.get("body_html")
                or data.get("email_html")
                or data.get("body")
                or data.get("email_body")
            )
            if isinstance(body, list):
                body = "\n\n".join(str(item) for item in body)
            if isinstance(body, dict):
                body = "\n\n".join(str(value) for value in body.values())
    except json.JSONDecodeError:
        pass

    if not subject:
        subject_match = re.search(r"^subject(?:\s+line)?\s*[:\-]\s*(.+)$", cleaned, re.IGNORECASE | re.MULTILINE)
        if subject_match:
            subject = str(subject_match.group(1)).strip()
            after_subject = cleaned[subject_match.end():].strip()
            body = after_subject or body

    if not body:
        double_newline_split = cleaned.split("\n\n", 1)
        if len(double_newline_split) == 2:
            potential_subject_line = double_newline_split[0]
            if potential_subject_line.lower().startswith("subject") and not subject:
                subject = potential_subject_line.split(":", 1)[-1].strip() or subject
                body = double_newline_split[1].strip()
        if not body:
            body = cleaned

    return str(subject or default_subject), str(body)


def _is_valid_email_content(subject: str | None, body: str | None) -> bool:
    if not subject or not subject.strip():
        return False
    if not body or not body.strip():
        return False
    return True


def _validate_email_content(subject: str | None, body: str | None) -> Tuple[str, str]:
    if not _is_valid_email_content(subject, body):
        raise ValueError("Email draft missing subject or body text")
    return subject.strip(), body.strip()
