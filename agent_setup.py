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

# Set up logger for this module
logger = setup_logger('agent_setup')
logger.info("=" * 60)
logger.info("Initializing Sales Agent System")
logger.info("=" * 60)

# Create model instances
logger.info("Creating LLM Model instances")
try:
    BASE_MODEL1 = OpenAIChatCompletionsModel(model="mistral:7b", openai_client=ollama_client)
    logger.info("✓ BASE_MODEL1 (mistral:7b) initialized")
except Exception as e:
    logger.error(f"✗ Failed to initialize BASE_MODEL1: {e}", exc_info=True)
    raise

try:
    BASE_MODEL2 = OpenAIChatCompletionsModel(model="qwen2.5:3b", openai_client=ollama_client)
    logger.info("✓ BASE_MODEL2 (qwen2.5:3b) initialized")
except Exception as e:
    logger.error(f"✗ Failed to initialize BASE_MODEL2: {e}", exc_info=True)
    raise

try:
    BASE_MODEL3 = OpenAIChatCompletionsModel(model="llama3.2:3b", openai_client=ollama_client)
    logger.info("✓ BASE_MODEL3 (BASE_MODEL2) initialized")
except Exception as e:
    logger.error(f"✗ Failed to initialize BASE_MODEL3: {e}", exc_info=True)
    raise

# Create Sales Agents with updated descriptions
logger.info("Creating specialized sales agents...")

sales_agent1 = Agent(
    name="Professional Sales Agent",
    instructions=INSTRUCTIONS_PROFESSIONAL,
    model=BASE_MODEL1
)
logger.info("✓ Professional Sales Agent created (using mistral:7b)")

sales_agent2 = Agent(
    name="Humorous Sales Agent",
    instructions=INSTRUCTIONS_HUMOROUS,
    model=BASE_MODEL2
)
logger.info("✓ Humorous Sales Agent created (using llama3.2:1b)")

sales_agent3 = Agent(
    name="Concise Sales Agent",
    instructions=INSTRUCTIONS_CONCISE,
    model=BASE_MODEL3
)
logger.info("✓ Concise Sales Agent created (using qwen2.5:3b)")


# Create Sales Agent Tools with better descriptions
logger.info("Creating agent tools...")

tool1 = sales_agent1.as_tool(
    tool_name="professional_sales_writer",
    tool_description="Write a professional, formal cold sales email. Best for B2B, enterprise, serious products."
)
logger.debug("Tool created: professional_sales_writer")

tool2 = sales_agent2.as_tool(
    tool_name="humorous_sales_writer",
    tool_description="Write a witty, engaging cold sales email with personality. Best for B2C, creative products, when humor is appropriate."
)
logger.debug("Tool created: humorous_sales_writer")

tool3 = sales_agent3.as_tool(
    tool_name="concise_sales_writer",
    tool_description="Write a brief, direct cold sales email. Best for busy executives, when brevity is important."
)
logger.debug("Tool created: concise_sales_writer")

# Create Email Helper Agents
logger.info("Creating email helper agents...")

subject_writer = Agent(
    name="Email Subject Writer",
    instructions=SUBJECT_INSTRUCTIONS,
    model=BASE_MODEL3
)
logger.info("✓ Email Subject Writer agent created")

subject_tool = subject_writer.as_tool(
    tool_name="subject_writer",
    tool_description="Generate a compelling subject line for an email"
)

html_converter = Agent(
    name="HTML Email Converter",
    instructions=HTML_INSTRUCTIONS,
    model=BASE_MODEL2
)
logger.info("✓ HTML Email Converter agent created")

html_tool = html_converter.as_tool(
    tool_name="html_converter",
    tool_description="Convert plain text email to HTML format"
)

# Email Manager Agent
logger.info("Creating Email Manager agent...")
email_tools = [subject_tool, html_tool, send_html_email_tool]
emailer_agent = Agent(
    name="Email Manager",
    instructions=EMAIL_MANAGER_INSTRUCTIONS,
    tools=email_tools,
    model=BASE_MODEL1,
    handoff_description="Format and send the email (generates subject, converts to HTML, sends)"
)
logger.info("✓ Email Manager agent created with 3 tools")

# Guardrail Agents
logger.info("Creating guardrail agents...")

guardrail_agent = Agent(
    name="Name Check Agent",
    instructions=NAME_CHECK_INSTRUCTIONS,
    model=BASE_MODEL3,
    output_type=NameCheckOutput
)
logger.info("✓ Name Check guardrail agent created")

input_guardrail_agent = Agent(
    name="Input Guardrail Agent",
    instructions=INPUT_GUARDRAIL_INSTRUCTIONS,
    model=BASE_MODEL3,
    output_type=InputGuardrailOutput
)
logger.info("✓ Input Guardrail agent created")

output_guardrail_agent = Agent(
    name="Output Guardrail Agent",
    instructions=OUTPUT_GUARDRAIL_INSTRUCTIONS,
    model=BASE_MODEL3,
    output_type=OutputGuardrailOutput
)
logger.info("✓ Output Guardrail agent created")

# Sales agent tools list
sales_tools = [tool1, tool2, tool3]

logger.info("=" * 60)
logger.info("Agent System Initialization Complete")
logger.info(f"Total Agents Created: 9")
logger.info(f"Total Tools Available: {len(sales_tools)} sales + {len(email_tools)} email")
logger.info("=" * 60)
