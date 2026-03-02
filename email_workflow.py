"""
Agent orchestration and approved-email sending workflow.

Author: Ben Walker (BenRWalker@icloud.com)
"""

import asyncio
from typing import List

from agents import Runner, trace
from agent_setup import sales_agent1, sales_agent2, sales_agent3, emailer_agent
from logger_config import setup_logger
from mail_merge import _apply_mail_merge, _ensure_html_body, _parse_agent_email_output, _validate_email_content
from scoring import EmailCandidate, _score_email

logger = setup_logger(__name__)


async def _generate_candidate_for_agent(agent, agent_label: str, message: str) -> EmailCandidate | None:
    try:
        with trace(f"Generate email - {agent_label}"):
            result = await Runner.run(agent, message)
    except Exception as run_error:
        logger.error(f"Agent {agent_label} failed: {run_error}", exc_info=True)
        return None

    raw_output = str(result.final_output)
    subject, body = _parse_agent_email_output(raw_output)
    try:
        subject, body = _validate_email_content(subject, body)
    except ValueError as validation_error:
        logger.warning(
            "Discarding invalid draft from %s: %s",
            agent_label,
            validation_error,
            exc_info=False
        )
        return None

    score = _score_email(subject, body)
    logger.info(f"{agent_label} score: {score}")
    return EmailCandidate(
        agent_name=agent_label,
        subject=subject,
        body=body,
        raw_output=raw_output,
        score=score
    )


async def _generate_best_email(message: str) -> tuple[EmailCandidate, List[EmailCandidate], List[str]]:
    agent_configs = [
        ("Professional Sales Agent", sales_agent1),
        ("Humorous Sales Agent", sales_agent2),
        ("Concise Sales Agent", sales_agent3)
    ]

    tasks = [asyncio.create_task(_generate_candidate_for_agent(agent, label, message)) for label, agent in agent_configs]
    results = await asyncio.gather(*tasks)

    candidates = [candidate for candidate in results if candidate is not None]
    failed_agents = [label for (label, _), candidate in zip(agent_configs, results) if candidate is None]

    if not candidates:
        raise RuntimeError("All sales agents failed to produce drafts")

    best_candidate = max(candidates, key=lambda candidate: candidate.score)
    return best_candidate, candidates, failed_agents


def _compose_generation_summary(best_candidate: EmailCandidate, candidates: List[EmailCandidate], failed_agents: List[str]) -> str:
    lines = [
        f"Selected best draft: {best_candidate.agent_name} (score {best_candidate.score:.1f})",
        "",
        f"Subject: {best_candidate.subject}",
        "",
        best_candidate.body.strip()
    ]

    sorted_candidates = sorted(candidates, key=lambda candidate: candidate.score, reverse=True)
    lines.extend(["", "Candidate scores:"])
    for candidate in sorted_candidates:
        lines.append(f"- {candidate.agent_name}: {candidate.score:.1f}")

    if failed_agents:
        lines.extend(["", "Drafts unavailable from:"])
        for agent_name in failed_agents:
            lines.append(f"- {agent_name}")

    return "\n".join(lines)


def _format_email_for_sending(candidate: EmailCandidate) -> str:
    """Create a clean subject/body text block for sending."""
    subject_line = candidate.subject.strip()
    body_text = candidate.body.strip()
    formatted = f"Subject: {subject_line}\n\n{body_text}"
    return formatted.strip()


async def run_sales_agent(message: str) -> str:
    logger.info(f"Received user request: {message[:100]}...")

    try:
        best_candidate, candidates, failed_agents = await _generate_best_email(message)
        summary = _compose_generation_summary(best_candidate, candidates, failed_agents)
        logger.info(
            "Selected best candidate",
            extra={
                "agent": best_candidate.agent_name,
                "score": best_candidate.score
            }
        )
        return summary

    except Exception as error:
        logger.error(f"OOPS! Error during agent execution: {error}", exc_info=True)
        return f"An error occurred: {str(error)}\n\nPlease check the logs for more details."


async def _create_generation_package(message: str) -> tuple[str, str]:
    best_candidate, candidates, failed_agents = await _generate_best_email(message)
    summary = _compose_generation_summary(best_candidate, candidates, failed_agents)
    formatted_draft = _format_email_for_sending(best_candidate)
    return summary, formatted_draft


async def send_approved_email(email_draft: str, recipients: List[dict[str, str]], sender_name: str) -> str:
    logger.info("Processing approved email for sending...")

    try:
        from email_service import send_html_email

        manager_prompt = (
            "You are the email manager. The user has approved this draft."
            " Format it cleanly with a strong subject line and prepare it for sending."
            " Return the complete email with subject and body.\n\n"
            f"Approved draft:\n{email_draft.strip()}"
        )

        try:
            with trace("Email manager finalize draft"):
                manager_result = await Runner.run(emailer_agent, manager_prompt)
            finalized_output = str(manager_result.final_output)
        except Exception as manager_error:
            logger.warning(
                "Email manager failed to format draft, falling back to raw approval: %s",
                manager_error,
                exc_info=True
            )
            finalized_output = email_draft

        subject_template, body_template = _parse_agent_email_output(finalized_output)
        subject_template, body_template = _validate_email_content(subject_template, body_template)

        recipients_to_use = recipients or []
        send_results: List[dict[str, str]] = []

        for recipient in recipients_to_use:
            recipient_name = (recipient.get('name') or '').strip()
            recipient_email = (recipient.get('email') or '').strip()

            personalized_subject = _apply_mail_merge(subject_template, recipient_name, sender_name)
            personalized_body = _apply_mail_merge(body_template, recipient_name, sender_name)
            html_body = _ensure_html_body(personalized_body)

            logger.info(
                "Sending email",
                extra={"subject": personalized_subject, "recipient_email": recipient_email or '[default]'}
            )
            result = await send_html_email(personalized_subject, html_body, recipient_email=recipient_email or None)
            send_results.append({
                "recipient": recipient_email or recipient_name or "default",
                "status": result.get('status', 'error'),
                "message": result.get('message', ''),
                "status_code": str(result.get('status_code', '')),
            })

        success_count = sum(1 for result in send_results if result["status"] == "success")
        failure_details = [result for result in send_results if result["status"] != "success"]

        if failure_details:
            first_failure = failure_details[0]
            failure_msg = (
                f"Sent {success_count} email(s), but {len(failure_details)} failed. "
                f"First failure ({first_failure['recipient']}): {first_failure.get('message', 'Unknown error')}"
            )
            logger.error(failure_msg)
            return failure_msg

        success_msg = f"Email sent to {success_count} recipient(s)."
        logger.info(success_msg)
        return success_msg

    except Exception as error:
        error_msg = f"Error sending email: {str(error)}"
        logger.error(error_msg, exc_info=True)
        return f"{error_msg}"
