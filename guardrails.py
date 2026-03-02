"""
Input and output guardrails for agent safety.
Author: Ben Walker (BenRWalker@icloud.com)
"""

import os
import re
from typing import List
from agents import input_guardrail, output_guardrail, GuardrailFunctionOutput
from logger_config import setup_logger
from models import InputGuardrailOutput, OutputGuardrailOutput

logger = setup_logger('guardrails', use_json=True)

RISK_THRESHOLD = float(os.environ.get('RISK_THRESHOLD', '0.75'))
TOXICITY_THRESHOLD = float(os.environ.get('TOXICITY_THRESHOLD', '0.8'))

PROMPT_INJECTION_PATTERNS = [
    r'ignore\s+all\s+previous\s+instructions',
    r'forget\s+your\s+role',
    r'you\s+are\s+now\s+a',
    r'<\|im_start\|>system',
    r'\[INST\].*ignore',
]

PII_PATTERNS = [
    r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
    r'\b\d{16}\b',  # Credit card
    r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # Phone
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
]


def heuristic_injection_check(text: str) -> tuple[bool, List[str]]:
    detected_patterns = []
    text_lower = text.lower()
    
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, text_lower):
            detected_patterns.append(pattern)
            logger.warning(f"Injection pattern detected: {pattern}")
    
    return len(detected_patterns) > 0, detected_patterns


def heuristic_pii_check(text: str) -> tuple[bool, List[str], float]:
    detected_pii = []
    
    for pattern in PII_PATTERNS:
        if re.search(pattern, text):
            detected_pii.append(pattern)
            logger.warning(f"PII pattern detected: {pattern}")
    
    confidence = min(1.0, len(detected_pii) * 0.3) if detected_pii else 0.0
    return len(detected_pii) > 0, detected_pii, confidence


@input_guardrail
async def comprehensive_input_guardrail(ctx, agent, message):
    logger.info(f"Running input guardrail on message length: {len(message)}")
    
    has_injection, injection_issues = heuristic_injection_check(message)
    has_pii, pii_issues, pii_confidence = heuristic_pii_check(message)

    flagged_issues: List[str] = []
    if has_injection:
        flagged_issues.extend([f"prompt_injection:{pattern}" for pattern in injection_issues])
    if has_pii:
        flagged_issues.extend([f"pii:{pattern}" for pattern in pii_issues])

    risk_score = 0.0
    if has_injection:
        risk_score = max(risk_score, 0.9)
    if has_pii:
        risk_score = max(risk_score, min(1.0, 0.6 + pii_confidence * 0.4))
    if not flagged_issues:
        risk_score = 0.1

    guardrail_output = InputGuardrailOutput(
        is_safe=not (has_injection or (has_pii and pii_confidence > 0.7)),
        is_prompt_injection=has_injection,
        contains_pii=has_pii,
        is_off_topic=False,
        is_harmful=False,
        risk_score=risk_score,
        flagged_issues=flagged_issues,
        sanitized_input=None
    )

    logger.info(
        "Input guardrail evaluation",
        extra={
            "issues": flagged_issues,
            "risk_score": guardrail_output.risk_score
        }
    )

    if has_injection:
        logger.error(f"Input blocked - prompt injection detected: {injection_issues}")
        return GuardrailFunctionOutput(
            output_info={
                "blocked": True,
                "reason": "Prompt injection pattern detected",
                "details": guardrail_output.model_dump()
            },
            tripwire_triggered=True
        )
    
    if has_pii and pii_confidence > 0.7:
        logger.warning(f"PII detected: {pii_issues}")
        return GuardrailFunctionOutput(
            output_info={
                "blocked": True,
                "reason": "PII detected in input",
                "details": guardrail_output.model_dump()
            },
            tripwire_triggered=True
        )
    
    logger.info("Input passed guardrail checks")
    return GuardrailFunctionOutput(
        output_info={
            "blocked": False,
            "details": guardrail_output.model_dump()
        },
        tripwire_triggered=False
    )


@output_guardrail
async def comprehensive_output_guardrail(ctx, agent, output):
    logger.info(f"Running output guardrail on output length: {len(str(output))}")
    
    output_text = str(output)
    
    leak_patterns = [
        r'api[_-]?key[:=]\s*["\']?[^\s"\'\n]+',
        r'password[:=]\s*["\']?[^\s"\'\n]+',
    ]
    
    detected_leaks = []
    for pattern in leak_patterns:
        if re.search(pattern, output_text, re.IGNORECASE):
            detected_leaks.append(pattern)
            logger.error(f"Potential data leak detected: {pattern}")
    
    guardrail_output = OutputGuardrailOutput(
        is_safe=not detected_leaks,
        contains_sensitive_data=bool(detected_leaks),
        is_harmful_content=False,
        is_hallucination=False,
        is_off_topic=False,
        toxicity_score=0.0,
        flagged_issues=[f"leak:{pattern}" for pattern in detected_leaks],
        redacted_output=None
    )

    logger.info(
        "Output guardrail evaluation",
        extra={
            "issues": guardrail_output.flagged_issues,
            "is_safe": guardrail_output.is_safe
        }
    )
    
    if detected_leaks:
        logger.error(f"Output blocked - {len(detected_leaks)} leak patterns detected")
        return GuardrailFunctionOutput(
            output_info={
                "blocked": True,
                "reason": "Potential data leak detected",
                "details": guardrail_output.model_dump()
            },
            tripwire_triggered=True
        )
    
    logger.info("Output passed guardrail checks")
    return GuardrailFunctionOutput(
        output_info={
            "blocked": False,
            "details": guardrail_output.model_dump()
        },
        tripwire_triggered=False
    )
