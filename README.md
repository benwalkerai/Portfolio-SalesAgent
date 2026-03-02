# Sales Agent

An AI-powered sales email generation and delivery system showcasing enterprise-grade agentic patterns—multi-agent orchestration, safety guardrails, CSV-driven personalization, and async email delivery.

This is a **portfolio project** demonstrating practical AI engineering: building with the official OpenAI Python SDK against local LLM inference (Ollama) or cloud APIs, designing safety-critical workflows, and coordinating autonomous agents to solve real business problems.

## Overview

The Sales Agent system guides users through a complete workflow:

1. **Compose** a sales request + upload recipient list (CSV)
2. **Generate** multiple draft emails via competing specialist agents (professional, humorous, concise)
3. **Score** and auto-select the best draft
4. **Approve** and mail-merge personalized tokens
5. **Send** via SendGrid with delivery tracking

## Key Features

- **Multi-Agent Orchestration:** A central Sales Manager agent delegates to three specialist writing agents, each with unique personas. They compete via automated scoring to produce the best output.
- **Flexible LLM Backend:** Uses the OpenAI Python SDK with configurable `base_url` and API keys—switch seamlessly between local Ollama, OpenAI-hosted models, or other compatible endpoints.
- **Safety Guardrails:** Dual guardrail system prevents security risks:
  - **Input guardrails** detect prompt injection and PII exposure
  - **Output guardrails** catch credential/secret leaks
- **Personalized Mail Merge:** Recipients are extracted from CSV; approved emails auto-fill `[Recipient Name]`, `[Your Name]`, and other tokens before sending.
- **Human Approval Loop:** Users explicitly approve before email delivery, enabling rejection and regeneration at any stage.
- **Observability:** Structured JSON logging tracks guardrail decisions, agent reasoning, and SendGrid delivery status.

## Architecture & Workflow

```
User Input + CSV
       ↓
[Input Guardrail] → Check for prompt injection & PII
       ↓
[Sales Manager Agent] → Coordinates three specialists
  ├─ Professional Agent (Mistral)
  ├─ Humorous Agent (Llama 3.2)
  └─ Concise Agent (Qwen 2.5)
       ↓
[Candidate Scoring] → Rank drafts, select best match
       ↓
[Output Guardrail] → Verify no secrets leak
       ↓
[User Approval] → Review & approve or regenerate
       ↓
[Email Manager Agent] → Mail-merge tokens per recipient
       ↓
[SendGrid] → Send personalized emails
       ↓
[Delivery Report] → Log success/failure per recipient
```

### Data Flow Diagram

![Sales Agent Flow](Docs/img/sales_agent_flow.png)

## UI Walkthrough

| Stage | Action | Screenshot |
|-------|--------|-----------|
| **1. Compose** | Enter sales prompt, sender name, upload contacts CSV | ![Step 1](Docs/img/screenshot1.png) |
| **2. Review** | View generated draft and per-agent scores | ![Step 2](Docs/img/screenshot2.png) |
| **3. Approve** | Approve & send, reject & regenerate, or manually edit | ![Step 3](Docs/img/screenshot3.png) |

## Getting Started

### Prerequisites

- **Python 3.12+**
- **Local LLM (or cloud API):**
  - Ollama with models: `mistral:7b`, `qwen2.5:3b`, `llama3.2:3b` (or adjust in `agent_setup.py`)
  - OR OpenAI API account
- **SendGrid account** and API key
- **UV package manager** (or pip)

### Installation & Setup

1. **Clone the repo and install dependencies:**

   ```bash
   cd Portfolio-SalesAgent
   uv sync
   # or: pip install -r requirements.txt
   ```

2. **Create `.env` file in the root directory:**

   ```env
   # LLM Configuration (Ollama local endpoint)
   LLM_API_URL=http://localhost:11434/v1
   LLM_API_KEY=ollama  # Dummy key for local Ollama

   # OR use OpenAI cloud API
   # LLM_API_URL=https://api.openai.com/v1
   # LLM_API_KEY=sk-...

   # Email Configuration
   SENDGRID_API_KEY=sg-...
   FROM_EMAIL=your-sales-email@company.com
   TO_EMAIL=default-recipient@example.com  # Optional

   # Safety Thresholds (optional, defaults provided)
   RISK_THRESHOLD=0.75
   TOXICITY_THRESHOLD=0.8
   ```

3. **Start Ollama (if using local models):**

   ```bash
   ollama serve
   # In another terminal, pull models:
   # ollama pull mistral:7b
   # ollama pull qwen2.5:3b
   # ollama pull llama3.2:3b
   ```

4. **Run the Gradio UI:**

   ```bash
   python interface.py
   ```

   The UI will open at `http://localhost:7860` (or the next available port).

5. **Use the application:**
   - Compose your sales message
   - Provide a CSV with columns: `name` and `email`
   - Click **Generate** and review candidate scores
   - Click **Approve & Send** to deliver personalized emails

### Example CSV Format

See `Docs/Example-contacts.csv`:

```csv
name,email
Alice Johnson,alice@techcorp.com
Bob Smith,bob@innovate.io
Carol White,carol@venture.com
```

## Safeguards & Guardrails

### Input Guardrail

Protects against malicious input before agents process requests:
- **Prompt Injection Detection:** Identifies patterns like `ignore all previous instructions`, `you are now a`, `<|im_start|>system`, etc.
- **PII Detection:** Flags SSNs, credit cards, phone numbers, and email addresses
- **Risk Scoring:** Computes confidence; high-risk inputs are rejected with structured feedback
- **Configurable Threshold:** `RISK_THRESHOLD` env var controls sensitivity (default: 0.75)

### Output Guardrail

Prevents secrets and credentials from leaking in generated emails:
- **Secret Pattern Matching:** Detects API keys, passwords, and common credential formats
- **Structured Response:** Returns pass/fail with detected patterns for logging
- **Audit Trail:** All guardrail decisions logged as JSON for compliance

## Project Structure

```
Portfolio-SalesAgent/
├── agent_setup.py           # Agent definitions, model initialization, tool registration
├── sales_manager.py         # Central Sales Manager agent with guardrails
├── guardrails.py            # Input/output guardrail implementations
├── email_service.py         # SendGrid integration and email-sending tools
├── interface.py             # Gradio UI: compose, review, approve, send workflow
├── config.py                # LLM client setup, environment validation
├── prompts.py               # Instructions for all agents (professional, humorous, concise, etc.)
├── models.py                # Pydantic models for guardrail outputs and agent responses
├── logger_config.py         # Structured JSON logging configuration
├── email_logger.py          # SendGrid delivery tracking and logging
├── pyproject.toml           # Project metadata, dependencies (uv-compatible)
├── LICENSE                  # MIT License
├── README.md                # This file
└── Docs/
    ├── img/
    │   ├── sales_agent_flow.png       # Architecture diagram
    │   ├── screenshot1.png             # UI: Compose stage
    │   ├── screenshot2.png             # UI: Review stage
    │   └── screenshot3.png             # UI: Approval/Send stage
    └── Example-contacts.csv            # Sample recipient list for testing
```

## Tech Stack

| Component | Technology | Notes |
|-----------|-----------|-------|
| **LLM Inference** | OpenAI Python SDK | Compatible with Ollama, OpenAI, Azure OpenAI, etc. |
| **Local Models** | Ollama | Mistral 7B, Qwen 2.5, Llama 3.2 (configurable) |
| **Agent Framework** | OpenAI Agents SDK | Multi-step reasoning, tool use, guardrail hooks |
| **UI/UX** | Gradio 6.8+ | Interactive web interface for compose → review → approve flow |
| **Email Delivery** | SendGrid | Transactional email API with delivery tracking |
| **Logging** | python-json-logger | Structured JSON logs for observability and debugging |
| **Config** | python-dotenv | Environment-based configuration |
| **Type Safety** | Pydantic 2.12+ | Data validation for outputs and guardrail responses |
| **Async/Await** | asyncio | Non-blocking I/O for agent calls and email dispatch |
| **Package Management** | UV | Fast Python package installer and dependency resolver |

## Portfolio Highlights

This project demonstrates:

- ✅ **Modern AI Architecture:** Multi-agent patterns with coordination, scoring, and decision-making
- ✅ **SDK Flexibility:** Show how to make OpenAI SDK work with any compatible endpoint (local LLM, cloud, self-hosted)
- ✅ **Security-First Design:** Dual guardrails, input validation, output scanning, structured audit logs
- ✅ **User Experience:** Gradio-based workflow balancing automation with human approval gates
- ✅ **Production Readiness:** Async execution, error handling, comprehensive logging, SendGrid integration
- ✅ **Clean Code:** Modular architecture, type hints, clear separation of concerns

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| `Missing required environment variable 'LLM_API_KEY'` | `.env` file not loaded or missing | Verify `.env` exists in root directory and `load_dotenv()` is called early in `config.py` |
| `ModuleNotFoundError: No module named 'agents'` | Missing OpenAI Agents SDK | Run `uv sync` or `pip install openai-agents>=0.10.2` |
| `Connection refused` on `localhost:11434` | Ollama not running | Start Ollama with `ollama serve` |
| Model not found (e.g., `mistral:7b`) | Model not pulled to local Ollama | Run `ollama pull mistral:7b` (and qwen2.5, llama3.2) |
| `SENDGRID_API_KEY` errors | Invalid or missing SendGrid key | Verify key format (`sg-...`) and SendGrid account is active |
| Guardrail errors after sending emails | PII or injection patterns in emails | Review guardrail patterns in `guardrails.py`; adjust `RISK_THRESHOLD` if too strict |

## Development & Contributions

To extend this project:

- **Add new writing agents:** Create new `Agent` instances in `agent_setup.py` with unique personas
- **Customize guardrails:** Edit patterns in `guardrails.py` or add new guardrail functions
- **Switch LLM backends:** Update `LLM_API_URL` and model names in `.env`
- **Adjust scoring logic:** Modify candidate evaluation in `interface.py` → `score_candidates()`
- **Monitor email delivery:** Check `email_logger.py` for SendGrid webhook handling and status updates

## Author & License

**Author:** Ben Walker (BenRWalker@icloud.com)

**License:** MIT License © 2025 — See [LICENSE](LICENSE) for details.

---

**Ready to generate your first sales email?** Update your `.env`, provide a CSV of contacts, and click "Generate Email" in the Gradio UI!
