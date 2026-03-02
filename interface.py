"""
Gradio UI interface for the Sales Agent.

Author: Ben Walker (BenRWalker@icloud.com)
"""

import csv
from typing import List

import gradio as gr

from email_workflow import (
    _create_generation_package,
    run_sales_agent,
    send_approved_email,
)
from logger_config import setup_logger

logger = setup_logger(__name__)


async def _update_status_during_processing(message: str):
    logger.info(f"Received user request: {message[:100]}...")
    message = (message or "").strip()
    if not message:
        warning = "Please enter a request"
        return "", warning, "", warning, False, ""

    try:
        summary, draft = await _create_generation_package(message)
        final_status = "Draft ready. Please review and approve or reject."
        send_status = "Awaiting approval. Approve to send automatically or reject to regenerate."
        return summary, final_status, message, send_status, False, draft

    except Exception as error:
        error_msg = f"Error running agent: {str(error)}"
        logger.error(error_msg, exc_info=True)
        failure_notice = f"❌ {error_msg}"
        return failure_notice, failure_notice, message, failure_notice, False, ""





def _safe_clear_callback():
    logger.info("Clear button clicked")
    return "", "", "", "", "", False, "", "No recipients uploaded.", [], ""


def _handle_recipient_upload(uploaded_file) -> tuple[str, List[dict[str, str]]]:
    if uploaded_file is None:
        return "Please upload a CSV with 'name' and 'email' columns.", []

    try:
        recipients: List[dict[str, str]] = []
        with open(uploaded_file.name, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            if not reader.fieldnames:
                return "Uploaded CSV is missing a header row.", []

            for idx, row in enumerate(reader, start=1):
                normalized = {(key or "").strip().lower(): (value or "").strip() for key, value in row.items()}
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
            return "No valid recipients found (need name + email).", []

        status = f"Loaded {len(recipients)} recipient{'s' if len(recipients) != 1 else ''}."
        return status, recipients

    except Exception as parse_error:
        logger.error("Failed to process recipient CSV: %s", parse_error, exc_info=True)
        return f"Failed to read CSV: {parse_error}", []



async def _approve_and_send_callback(
    email_draft: str,
    already_approved: bool,
    recipients: List[dict[str, str]],
    sender_name: str,
) -> tuple[str, bool]:
    if already_approved:
        logger.info("Approve clicked but draft already approved")
        return "ℹThis draft has already been approved and sent.", True

    if not email_draft or email_draft.strip() == "":
        logger.warning("Approve clicked with no draft available")
        return "Generate a draft before approving.", False

    if not recipients:
        logger.warning("Approve clicked without uploaded recipients")
        return "Upload a recipient CSV with names and email addresses before approving.", False

    sender_name = (sender_name or "").strip()
    if not sender_name:
        logger.warning("Approve clicked without sender name")
        return "Please provide a sender or team name before approving.", False

    try:
        result = await send_approved_email(email_draft, recipients, sender_name)
        return result, True
    except Exception as error:
        error_msg = f"Error sending approved email: {str(error)}"
        logger.error(error_msg, exc_info=True)
        return error_msg, False


async def _reject_and_regenerate(prompt: str):
    prompt = (prompt or "").strip()
    if not prompt:
        warning = "No previous request found. Please enter a prompt first."
        return warning, warning, "", warning, False, ""

    try:
        summary, draft = await _create_generation_package(prompt)
        status = "Generated a new draft after rejection."
        send_status = "Awaiting approval for the new draft."
        return summary, status, prompt, send_status, False, draft
    except Exception as error:
        error_msg = f"Error generating replacement draft: {str(error)}"
        logger.error(error_msg, exc_info=True)
        failure_notice = f"{error_msg}"
        return failure_notice, failure_notice, prompt, failure_notice, False, ""


def launch_interface():
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
                    label="Sales Request",
                )

                sender_textbox = gr.Textbox(
                    label="Sender / Team Name",
                    placeholder="e.g., Alice from Growth Team",
                )

                recipient_upload = gr.File(
                    label="Upload Recipients CSV",
                    file_types=[".csv"],
                    file_count="single",
                )

                recipient_status_box = gr.Textbox(
                    label="Recipient Upload Status",
                    value="No recipients uploaded.",
                    interactive=False,
                    lines=2,
                )

                status_box = gr.Textbox(
                    label="⚙️ Processing Status",
                    placeholder="Ready to process your request...",
                    interactive=False,
                    lines=2,
                )

                with gr.Row():
                    submit_btn = gr.Button("Generate Email", variant="primary")
                    clear_btn = gr.Button("Clear", variant="secondary")

            with gr.Column():
                summary_textbox = gr.Textbox(
                    label="Generation Summary",
                    lines=12,
                    interactive=False,
                )

        gr.Markdown("---")
        gr.Markdown("### Approval Workflow")

        with gr.Row():
            with gr.Column(scale=3):
                send_status = gr.Textbox(
                    label="Approval & Send Status",
                    placeholder="Generate an email, then approve or reject the draft",
                    interactive=False,
                    lines=3,
                )
            with gr.Column(scale=1):
                approve_btn = gr.Button("Approve & Send", variant="secondary")
                reject_btn = gr.Button("Reject & Regenerate", variant="secondary")

        gr.Examples(
            examples=[
                "Send a cold sales email to introduce our new product to potential clients.",
                "Create a witty cold email about our SOC2 compliance tool",
                "Write a concise sales email for busy executives",
            ],
            inputs=input_textbox,
            outputs=[summary_textbox, status_box, prompt_state, send_status, approved_state, draft_state],
            fn=_update_status_during_processing,
            cache_examples=False,
        )

        submit_btn.click(
            fn=_update_status_during_processing,
            inputs=input_textbox,
            outputs=[summary_textbox, status_box, prompt_state, send_status, approved_state, draft_state],
        )

        approve_btn.click(
            fn=_approve_and_send_callback,
            inputs=[draft_state, approved_state, recipient_state, sender_textbox],
            outputs=[send_status, approved_state],
        )

        reject_btn.click(
            fn=_reject_and_regenerate,
            inputs=prompt_state,
            outputs=[summary_textbox, status_box, prompt_state, send_status, approved_state, draft_state],
        )

        recipient_upload.upload(
            fn=_handle_recipient_upload,
            inputs=recipient_upload,
            outputs=[recipient_status_box, recipient_state],
        )

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
                sender_textbox,
            ],
        )

        input_textbox.submit(
            fn=_update_status_during_processing,
            inputs=input_textbox,
            outputs=[summary_textbox, status_box, prompt_state, send_status, approved_state, draft_state],
        )

    logger.info("Gradio interface ready")
    return interface


if __name__ == "__main__":
    logger.info("Starting Sales Agent application")
    interface = launch_interface()
    interface.launch()
