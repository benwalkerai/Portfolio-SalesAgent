"""
Main Sales manager agent that coordinates the team.

Author: Ben Walker (BenRWalker@icloud.com)
"""

from agents import Agent
from prompts import SALES_MANAGER_INSTRUCTIONS
from agent_setup import BASE_MODEL2, sales_tools
from guardrails import comprehensive_input_guardrail, comprehensive_output_guardrail
from logger_config import setup_logger

# Set up logger for this module
logger = setup_logger('sales_manager')

logger.info("Creating Sales Manager Agent")
# Create the main sales manager agent with enhanced guardrails
careful_sales_manager = Agent(
    name="Sales Manager",
    instructions=SALES_MANAGER_INSTRUCTIONS,
    tools=sales_tools,
    model=BASE_MODEL2,
    input_guardrails=[comprehensive_input_guardrail],
    output_guardrails=[comprehensive_output_guardrail]
)
logger.info("✓ Sales Manager agent created with:")
logger.info(f"  - {len(sales_tools)} sales agent tools")
logger.info(f"  - 0 handoffs (direct response)")
logger.info(f"  - Input guardrails: enabled")
logger.info(f"  - Output guardrails: enabled")
logger.info(f"  - Model: BASE_MODEL2")
