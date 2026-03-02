"""
Agent definitions and model configurations.
Author: Ben Walker (BenRWalker@icloud.com)
"""

from agents import Agent, OpenAIChatCompletionsModel
from config import ollama_client
from prompts import (
    INSTRUCTIONS_PROFESSIONAL,
    INSTRUCTIONS_HUMOROUS,
    INSTRUCTIONS_CONCISE,
    SUBJECT_INSTRUCTIONS,
    HTML_INSTRUCTIONS,
    EMAIL_MANAGER_INSTRUCTIONS,
    SALES_MANAGER_INSTRUCTIONS,
    NAME_CHECK_INSTRUCTIONS,
    INPUT_GUARDRAIL_INSTRUCTIONS,
    OUTPUT_GUARDRAIL_INSTRUCTIONS
)

from models import NameCheckOutput, InputGuardrailOutput, OutputGuardrailOutput
from email_service import send_html_email_tool
from logger_config import setup_logger

logger = setup_logger('agent_setup')

try:
    BASE_MODEL1 = OpenAIChatCompletionsModel(model="mistral:7b", openai_client=ollama_client)
except Exception as e:
    logger.error(f"✗ Failed to initialize BASE_MODEL1: {e}", exc_info=True)
    raise

try:
    BASE_MODEL2 = OpenAIChatCompletionsModel(model="qwen2.5:3b", openai_client=ollama_client)
except Exception as e:
    logger.error(f"✗ Failed to initialize BASE_MODEL2: {e}", exc_info=True)
    raise

try:
    BASE_MODEL3 = OpenAIChatCompletionsModel(model="llama3.2:3b", openai_client=ollama_client)
except Exception as e:
    logger.error(f"✗ Failed to initialize BASE_MODEL3: {e}", exc_info=True)
    raise

sales_agent1 = Agent(
    name="Professional Sales Agent",
    instructions=INSTRUCTIONS_PROFESSIONAL,
    model=BASE_MODEL1
)

sales_agent2 = Agent(
    name="Humorous Sales Agent",
    instructions=INSTRUCTIONS_HUMOROUS,
    model=BASE_MODEL2
)

sales_agent3 = Agent(
    name="Concise Sales Agent",
    instructions=INSTRUCTIONS_CONCISE,
    model=BASE_MODEL3
)

tool1 = sales_agent1.as_tool(
    tool_name="professional_sales_writer",
    tool_description="Write a professional, formal cold sales email. Best for B2B, enterprise, serious products."
)

tool2 = sales_agent2.as_tool(
    tool_name="humorous_sales_writer",
    tool_description="Write a witty, engaging cold sales email with personality. Best for B2C, creative products, when humor is appropriate."
)

tool3 = sales_agent3.as_tool(
    tool_name="concise_sales_writer",
    tool_description="Write a brief, direct cold sales email. Best for busy executives, when brevity is important."
)


subject_writer = Agent(
    name="Email Subject Writer",
    instructions=SUBJECT_INSTRUCTIONS,
    model=BASE_MODEL3
)

subject_tool = subject_writer.as_tool(
    tool_name="subject_writer",
    tool_description="Generate a compelling subject line for an email"
)

html_converter = Agent(
    name="HTML Email Converter",
    instructions=HTML_INSTRUCTIONS,
    model=BASE_MODEL2
)

html_tool = html_converter.as_tool(
    tool_name="html_converter",
    tool_description="Convert plain text email to HTML format"
)

email_tools = [subject_tool, html_tool, send_html_email_tool]
emailer_agent = Agent(
    name="Email Manager",
    instructions=EMAIL_MANAGER_INSTRUCTIONS,
    tools=email_tools, #type :ignore[arg-type]
    model=BASE_MODEL1,
    handoff_description="Format and send the email (generates subject, converts to HTML, sends)"
)

guardrail_agent = Agent(
    name="Name Check Agent",
    instructions=NAME_CHECK_INSTRUCTIONS,
    model=BASE_MODEL3,
    output_type=NameCheckOutput
)

input_guardrail_agent = Agent(
    name="Input Guardrail Agent",
    instructions=INPUT_GUARDRAIL_INSTRUCTIONS,
    model=BASE_MODEL3,
    output_type=InputGuardrailOutput
)

output_guardrail_agent = Agent(
    name="Output Guardrail Agent",
    instructions=OUTPUT_GUARDRAIL_INSTRUCTIONS,
    model=BASE_MODEL3,
    output_type=OutputGuardrailOutput
)

sales_tools = [tool1, tool2, tool3]
