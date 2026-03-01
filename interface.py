"""
Gradio UI interface for the Sales Agent

Author: Ben Walker (BenRWalker@icloud.com)
"""

import gradio as gr
import asyncio
import csv
import json
import re
from dataclasses import dataclass
from html import escape
from typing import Tuple, List
from agents import Runner, trace
from sales_manager import careful_sales_manager
from agent_setup import (
    BASE_MODEL1, BASE_MODEL2, BASE_MODEL3,
    sales_agent1, sales_agent2, sales_agent3,
    subject_writer, html_converter, emailer_agent, guardrail_agent
)
from logger_config import setup_logger
import time

# Set up logger for this module
logger = setup_logger(__name__)

# Shared progress state used for UI feedback.
progress_state = {
    "status": "Ready",
    "progress": 0
}

CTA_KEYWORDS = {"call", "demo", "meeting", "chat", "reply", "schedule", "respond"}


@dataclass
class EmailCandidate:
    agent_name: str
    subject: str
    body: str
    raw_output: str
    score: float


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences from text if present."""
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
    """Convert plain text email content to simple paragraph-based HTML."""
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
    """Ensure the provided body text is HTML. Convert if necessary."""
    stripped = body_text.lstrip()
    if stripped.startswith("<") and stripped.endswith(">"):
        return body_text
    return _plain_text_to_html(body_text)


def _apply_mail_merge(text: str, recipient_name: str, sender_name: str) -> str:
    """Replace placeholder tokens with recipient/sender info."""
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
    """Extract subject and body from agent output supporting JSON and text formats."""
    default_subject = "Sales Email"
    cleaned = agent_output.strip()
    subject: str | None = None
    body: str | None = None
    candidate = _strip_code_fences(cleaned)

    # Try JSON parsing first
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
        logger.debug("Agent output not JSON - falling back to heuristics")
    except Exception as json_error:
        logger.warning(f"Error parsing agent JSON output: {json_error}")

    if not subject:
        subject_match = re.search(r"^subject(?:\s+line)?\s*[:\-]\s*(.+)$", cleaned, re.IGNORECASE | re.MULTILINE)
        if subject_match:
            subject = str(subject_match.group(1)).strip()
            # Body is text after subject declaration
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
    """Basic validation ensuring subject/body exist and contain meaningful text."""
    if not subject or not subject.strip():
        return False
    if not body or not body.strip():
        return False
    return True


def _validate_email_content(subject: str | None, body: str | None) -> Tuple[str, str]:
    """Ensure parsed content is usable; raise ValueError if not."""
    if not _is_valid_email_content(subject, body):
        raise ValueError("Email draft missing subject or body text")
    return subject.strip(), body.strip()


def _score_email(subject: str, body: str) -> float:
    """Compute a heuristic quality score for an email draft."""
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


async def _generate_candidate_for_agent(agent, agent_label: str, message: str) -> EmailCandidate | None:
    """Run a specific agent and return a scored email candidate."""
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
    """Generate drafts with all sales agents and pick the best one."""
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
    """Format the selected email plus scoring diagnostics."""
    lines = [
        f"🤖 Selected best draft: {best_candidate.agent_name} (score {best_candidate.score:.1f})",
        "",
        f"Subject: {best_candidate.subject}",
        "",
        best_candidate.body.strip()
    ]

    sorted_candidates = sorted(candidates, key=lambda candidate: candidate.score, reverse=True)
    lines.extend(["", "📊 Candidate scores:"])
    for candidate in sorted_candidates:
        lines.append(f"- {candidate.agent_name}: {candidate.score:.1f}")

    if failed_agents:
        lines.extend(["", "⚠️ Drafts unavailable from:"])
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
    """
    Run the sales manager agent with the given message.
    
    Args:
        message: User input message
        
    Returns:
        Agent response as string
    """
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
            
    except Exception as e:
        logger.error(f"OOPS! Error during agent execution: {e}", exc_info=True)
        return f"An error occurred: {str(e)}\n\nPlease check the logs for more details."


async def _create_generation_package(message: str) -> tuple[str, str]:
    """Run agents and return (summary_display, formatted_draft)."""
    best_candidate, candidates, failed_agents = await _generate_best_email(message)
    summary = _compose_generation_summary(best_candidate, candidates, failed_agents)
    formatted_draft = _format_email_for_sending(best_candidate)
    return summary, formatted_draft


async def _update_status_during_processing(message: str):
    """Generate draft, update status, and store state for approval workflow."""
    logger.info(f"Received user request: {message[:100]}...")
    message = (message or "").strip()
    if not message:
        warning = "⚠️ Please enter a request"
        return "", warning, "", warning, False, ""

    try:
        summary, draft = await _create_generation_package(message)
        final_status = "✅ Draft ready. Please review and approve or reject."
        send_status = "⏳ Awaiting approval. Approve to send automatically or reject to regenerate."
        return summary, final_status, message, send_status, False, draft

    except Exception as e:
        error_msg = f"Error running agent: {str(e)}"
        logger.error(error_msg, exc_info=True)
        failure_notice = f"❌ {error_msg}"
        return failure_notice, failure_notice, message, failure_notice, False, ""


async def _safe_agent_callback_with_progress(message: str):
    """Run the agent workflow while surfacing real-time progress updates."""
    logger.info(f"Received user request: {message[:100]}...")
    
    if not message or message.strip() == "":
        return "", "⚠️ Please enter a request"
    
    try:
        progress_state["status"] = "⏳ Starting..."
        progress_state["progress"] = 10

        async def _run_agent_task():
            return await run_sales_agent(message)

        task = asyncio.create_task(_run_agent_task())

        steps = [
            (20, "🛡️ Running input guardrails..."),
            (35, "📝 Sales agent writing email..."),
            (60, "✍️ Creating subject line..."),
            (75, "🎨 Converting to HTML..."),
            (90, "🛡️ Running output guardrails..."),
        ]

        for progress, status in steps:
            if task.done():
                break
            progress_state["status"] = status
            progress_state["progress"] = progress
            await asyncio.sleep(15)

        try:
            result = await asyncio.wait_for(task, timeout=180)
        except asyncio.TimeoutError:
            task.cancel()
            logger.error("Agent execution timed out after 3 minutes")
            return "⏱️ Request timed out after 3 minutes", "❌ Timeout"

        return result, "✅ Complete! Email generated successfully."

    except Exception as e:
        error_msg = f"Error running agent: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return f"❌ {error_msg}", f"❌ Failed: {str(e)[:50]}..."



def _safe_clear_callback():
    """Clear input, output, status boxes, and approval state."""
    logger.info("Clear button clicked")
    return "", "", "", "", "", False, "", "No recipients uploaded.", [], ""


def _handle_recipient_upload(uploaded_file) -> tuple[str, List[dict[str, str]]]:
    """Parse uploaded CSV into recipient list."""
    if uploaded_file is None:
        return "⚠️ Please upload a CSV with 'name' and 'email' columns.", []

    try:
        recipients: List[dict[str, str]] = []
        with open(uploaded_file.name, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            if not reader.fieldnames:
                return "⚠️ Uploaded CSV is missing a header row.", []

            for idx, row in enumerate(reader, start=1):
                normalized = { (key or "").strip().lower(): (value or "").strip() for key, value in row.items() }
                name = (
                    normalized.get("name")
                    or normalized.get("recipient")
                    or normalized.get("recipient name")
                    or normalized.get("full name")
                )
                email = normalized.get("email") or normalized.get("email address")

                if not email:
                    logger.warning("Skipping row %s with missing email", idx)
                    continue

                recipients.append({"name": name or "", "email": email})

        if not recipients:
            return "⚠️ No valid recipients found (need name + email).", []

        status = f"📥 Loaded {len(recipients)} recipient{'s' if len(recipients) != 1 else ''}."
        return status, recipients

    except Exception as parse_error:
        logger.error("Failed to process recipient CSV: %s", parse_error, exc_info=True)
        return f"❌ Failed to read CSV: {parse_error}", []


def clear_cache_and_ui():
    """
    Clear LLM cache and reset UI components.
    
    Returns:
        Tuple of empty strings for input and output textboxes
    """
    logger.info("Clearing model and agent caches...")
    cleared_count = 0
    
    # Clear model caches if they have cache methods
    models = [BASE_MODEL1, BASE_MODEL2, BASE_MODEL3]
    for model in models:
        try:
            # Clear cache if the model has a cache attribute
            if hasattr(model, 'cache'):
                model.cache = {}
                cleared_count += 1
            
            # Some models might have a clear_cache method
            if hasattr(model, 'clear_cache'):
                model.clear_cache()
                cleared_count += 1
        except Exception as e:
            logger.warning(f"Oh No! Error clearing cache for model {model}: {e}", exc_info=True)
    
    # Clear agent caches
    agents = [
        sales_agent1, sales_agent2, sales_agent3,
        subject_writer, html_converter, emailer_agent, guardrail_agent
    ]
    for agent in agents:
        try:
            if hasattr(agent, 'cache'):
                agent.cache = {}
                cleared_count += 1
            if hasattr(agent, 'clear_cache'):
                agent.clear_cache() #type: ignore[attr=defined]
                cleared_count += 1
        except Exception as e:
            logger.warning(f"Error clearing cache for agent {agent.name}: {e}")
    
    logger.info(f"Successfully cleared {cleared_count} caches")
    
    # Return empty strings to clear the UI components
    return "", ""


async def send_approved_email(email_draft: str, recipients: List[dict[str, str]], sender_name: str) -> str:
    """
    Send an email that the user has approved.
    Parses the draft and sends it via SendGrid.
    
    Args:
        email_draft: The complete email text including subject
        recipients: List of recipient records containing name/email
        sender_name: Name/team that should appear in the email content
        
    Returns:
        Success/failure message string
    """
    logger.info("Processing approved email for sending...")
    
    try:
        # Import here to avoid circular dependency
        from email_service import send_html_email
        
        # First, run the Email Manager agent to polish/format the draft
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

        success_count = sum(1 for res in send_results if res["status"] == "success")
        failure_details = [res for res in send_results if res["status"] != "success"]

        if failure_details:
            first_failure = failure_details[0]
            failure_msg = (
                f"⚠️ Sent {success_count} email(s), but {len(failure_details)} failed. "
                f"First failure ({first_failure['recipient']}): {first_failure.get('message', 'Unknown error')}"
            )
            logger.error(failure_msg)
            return failure_msg

        success_msg = f"✅ Email sent to {success_count} recipient(s)."
        logger.info(success_msg)
        return success_msg
            
    except Exception as e:
        error_msg = f"Error sending email: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return f"❌ {error_msg}"


async def _approve_and_send_callback(
    email_draft: str,
    already_approved: bool,
    recipients: List[dict[str, str]],
    sender_name: str
) -> tuple[str, bool]:
    """Approve the current draft and trigger sending."""
    if already_approved:
        logger.info("Approve clicked but draft already approved")
        return "ℹ️ This draft has already been approved and sent.", True

    if not email_draft or email_draft.strip() == "":
        logger.warning("Approve clicked with no draft available")
        return "⚠️ Generate a draft before approving.", False

    if not recipients:
        logger.warning("Approve clicked without uploaded recipients")
        return "⚠️ Upload a recipient CSV with names and email addresses before approving.", False

    sender_name = (sender_name or "").strip()
    if not sender_name:
        logger.warning("Approve clicked without sender name")
        return "⚠️ Please provide a sender or team name before approving.", False

    try:
        result = await send_approved_email(email_draft, recipients, sender_name)
        return result, True
    except Exception as e:
        error_msg = f"❌ Error sending approved email: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return error_msg, False


async def _reject_and_regenerate(prompt: str):
    """Regenerate a draft for the last prompt after rejection."""
    prompt = (prompt or "").strip()
    if not prompt:
        warning = "⚠️ No previous request found. Please enter a prompt first."
        return warning, warning, "", warning, False, ""

    try:
        summary, draft = await _create_generation_package(prompt)
        status = "✅ Generated a new draft after rejection."
        send_status = "⏳ Awaiting approval for the new draft."
        return summary, status, prompt, send_status, False, draft
    except Exception as e:
        error_msg = f"Error generating replacement draft: {str(e)}"
        logger.error(error_msg, exc_info=True)
        failure_notice = f"❌ {error_msg}"
        return failure_notice, failure_notice, prompt, failure_notice, False, ""


def launch_interface():
    """
    Launch the gradio interface with Blocks API for more control
    """
    
    logger.info("Launching Gradio interface")

    with gr.Blocks(title="Sales Agent") as interface:
        gr.Markdown("# Sales Agent")
        gr.Markdown("An AI-powered sales agent that crafts and sends cold sales emails.")
        
        draft_state = gr.State("")
        prompt_state = gr.State("")
        approved_state = gr.State(False)
        recipient_state = gr.State([])

        with gr.Row():
            with gr.Column():
                input_textbox = gr.Textbox(
                    lines=3,
                    placeholder="Enter your sales request here...",
                    label="Sales Request"
                )

                sender_textbox = gr.Textbox(
                    label="Sender / Team Name",
                    placeholder="e.g., Alice from Growth Team"
                )

                recipient_upload = gr.File(
                    label="Upload Recipients CSV",
                    file_types=[".csv"],
                    file_count="single"
                )

                recipient_status_box = gr.Textbox(
                    label="Recipient Upload Status",
                    value="No recipients uploaded.",
                    interactive=False,
                    lines=2
                )
                
                status_box = gr.Textbox(
                    label="⚙️ Processing Status",
                    placeholder="Ready to process your request...",
                    interactive=False,
                    lines=2
                )
                
                with gr.Row():
                    submit_btn = gr.Button("Generate Email", variant="primary")
                    clear_btn = gr.Button("Clear", variant="secondary")
            
            with gr.Column():
                summary_textbox = gr.Textbox(
                    label="Generation Summary",
                    lines=12,
                    interactive=False
                )
        
        # Email sending section
        gr.Markdown("---")
        gr.Markdown("### 📧 Approval Workflow")
        
        with gr.Row():
            with gr.Column(scale=3):
                send_status = gr.Textbox(
                    label="Approval & Send Status",
                    placeholder="Generate an email, then approve or reject the draft",
                    interactive=False,
                    lines=3
                )
            with gr.Column(scale=1):
                approve_btn = gr.Button("✅ Approve & Send", variant="secondary")
                reject_btn = gr.Button("❌ Reject & Regenerate", variant="secondary")
        
        # Examples section
        gr.Examples(
            examples=[
                "Send a cold sales email to introduce our new product to potential clients.",
                "Create a witty cold email about our SOC2 compliance tool",
                "Write a concise sales email for busy executives"
            ],
            inputs=input_textbox,
            outputs=[summary_textbox, status_box, prompt_state, send_status, approved_state, draft_state],
            fn=_update_status_during_processing,
            cache_examples=False
        )
        
        # Connect submit button - with status updates
        submit_btn.click(
            fn=_update_status_during_processing,
            inputs=input_textbox,
            outputs=[summary_textbox, status_box, prompt_state, send_status, approved_state, draft_state]
        )
        
        approve_btn.click(
            fn=_approve_and_send_callback,
            inputs=[draft_state, approved_state, recipient_state, sender_textbox],
            outputs=[send_status, approved_state]
        )

        reject_btn.click(
            fn=_reject_and_regenerate,
            inputs=prompt_state,
            outputs=[summary_textbox, status_box, prompt_state, send_status, approved_state, draft_state]
        )
        
        recipient_upload.upload(
            fn=_handle_recipient_upload,
            inputs=recipient_upload,
            outputs=[recipient_status_box, recipient_state]
        )

        # Connect clear button
        clear_btn.click(
            fn=_safe_clear_callback,
            inputs=None,
            outputs=[
                input_textbox,
                summary_textbox,
                status_box,
                prompt_state,
                send_status,
                approved_state,
                draft_state,
                recipient_status_box,
                recipient_state,
                sender_textbox
            ]
        )
        
        # Also allow Enter key to submit
        input_textbox.submit(
            fn=_update_status_during_processing,
            inputs=input_textbox,
            outputs=[summary_textbox, status_box, prompt_state, send_status, approved_state, draft_state]
        )
    
    logger.info("Gradio interface ready")
    return interface


if __name__ == "__main__":
    logger.info("Starting Sales Agent application")
    interface = launch_interface()
    interface.launch()
