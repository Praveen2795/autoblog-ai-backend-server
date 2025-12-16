<div align="center">

# 🤖 AutoBlog AI

### Email-Triggered Multi-Agent Blog Generation System

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![Gemini](https://img.shields.io/badge/Google-Gemini%202.5-orange.svg)](https://ai.google.dev)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Send an email → Get a polished blog post back. It's that simple.**

[Features](#-features) • [Architecture](#-architecture) • [Quick Start](#-quick-start) • [API](#-api-endpoints) • [Security](#-security)

</div>

---

## ✨ Features

- 📧 **Email-Triggered** - Send an email with your topic, receive a blog in your inbox
- 🤖 **Multi-Agent AI** - 4 specialized agents work together: Research → Draft → Review → Refine
- 🛡️ **3-Layer Guardrails** - Input validation, keyword filtering, and AI content moderation
- 🔄 **Self-Improving** - Review loop continues until quality score ≥ 90/100
- 📚 **Source Citations** - Research pulls from YouTube, articles, and academic papers
- 🎨 **Beautiful Output** - HTML-formatted emails with proper styling

---

## 🏗️ Architecture

### High-Level System Design

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                             AUTOBLOG AI SYSTEM                               │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌───────────────────────────────────────────────────┐  │
│  │              │     │                  FASTAPI BACKEND                  │  │
│  │   EMAIL      │     │  ┌─────────────────────────────────────────────┐  │  │
│  │   TRIGGER    │IMAP │  │             GUARDRAIL LAYER                 │  │  │
│  │              │────>│  │  ┌─────────┐ ┌─────────┐ ┌───────────────┐  │  │  │
│  │  Subject =   │     │  │  │ Input   │ │ Keyword │ │ AI Moderation │  │  │  │
│  │  Your Topic  │     │  │  │ Regex   │ │ Filter  │ │ (Gemini Flash)│  │  │  │
│  │              │     │  │  └────┬────┘ └────┬────┘ └───────┬───────┘  │  │  │
│  └──────────────┘     │  │       │           │              │          │  │  │
│         ^             │  │       └───────────┴──────────────┘          │  │  │
│         │             │  │                    │ PASS                   │  │  │
│         │             │  └────────────────────┼────────────────────────┘  │  │
│         │             │                       v                           │  │
│         │             │  ┌─────────────────────────────────────────────┐  │  │
│         │             │  │          MULTI-AGENT PIPELINE               │  │  │
│         │             │  │                                             │  │  │
│         │             │  │   ┌──────────┐    ┌──────────┐              │  │  │
│         │             │  │   │          │    │          │              │  │  │
│         │             │  │   │RESEARCHER│───>│ DRAFTER  │              │  │  │
│         │             │  │   │          │    │          │              │  │  │
│         │             │  │   └──────────┘    └────┬─────┘              │  │  │
│         │             │  │                        │                    │  │  │
│         │             │  │                        v                    │  │  │
│         │             │  │   ┌──────────┐    ┌──────────┐              │  │  │
│         │             │  │   │          │<───│          │              │  │  │
│         │             │  │   │ REFINER  │    │ REVIEWER │              │  │  │
│         │             │  │   │          │───>│ Score<90 │──┐           │  │  │
│         │             │  │   └──────────┘    └──────────┘  │           │  │  │
│         │             │  │        ^               │        │           │  │  │
│         │             │  │        └───────────────┘        │           │  │  │
│         │             │  │                          Score>=90          │  │  │
│         │             │  │                                 │           │  │  │
│         │             │  └─────────────────────────────────┼───────────┘  │  │
│         │             │                                    v              │  │
│         │             │  ┌─────────────────────────────────────────────┐  │  │
│         │   SMTP      │  │             EMAIL SERVICE                   │  │  │
│         │<────────────│  │  Format Blog -> HTML + Plain Text -> Send   │  │  │
│         │             │  └─────────────────────────────────────────────┘  │  │
│  ┌──────┴───────┐     │                                                   │  │
│  │              │     └───────────────────────────────────────────────────┘  │
│  │   INBOX      │                                                            │
│  │              │     ┌───────────────────────────────────────────────────┐  │
│  │  Beautiful   │     │                  GOOGLE GEMINI                    │  │
│  │  Blog Post!  │     │  ┌───────────┐  ┌───────────┐  ┌───────────┐      │  │
│  │              │     │  │gemini-2.5 │  │gemini-2.5 │  │  Google   │      │  │
│  │              │     │  │  flash    │  │   pro     │  │  Search   │      │  │
│  └──────────────┘     │  │(fast ops) │  │ (quality) │  │  (tools)  │      │  │
│                       │  └───────────┘  └───────────┘  └───────────┘      │  │
│                       └───────────────────────────────────────────────────┘  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Agent Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AGENT PIPELINE DETAIL                              │
└─────────────────────────────────────────────────────────────────────────────┘

    Topic: "Best practices for Python testing"
                           │
                           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  🔍 RESEARCHER AGENT                                          │
    │  ─────────────────────                                        │
    │  • Uses Google Search via Gemini                              │
    │  • Finds YouTube videos, articles, academic papers            │
    │  • Extracts key insights and sources                          │
    │  • Output: ResearchData (sources, summaries, key points)      │
    └──────────────────────────────────────────────────────────────┘
                           │
                           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  ✍️ DRAFTER AGENT                                             │
    │  ─────────────────────                                        │
    │  • Takes research data as input                               │
    │  • Structures content with headers, sections                  │
    │  • Creates engaging introduction and conclusion               │
    │  • Output: First draft (Markdown format)                      │
    └──────────────────────────────────────────────────────────────┘
                           │
                           ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  📋 REVIEWER AGENT                                            │
    │  ─────────────────────                                        │
    │  • Evaluates draft quality (0-100 score)                      │
    │  • Checks: accuracy, clarity, engagement, structure           │
    │  • Provides specific improvement suggestions                  │
    │  • Output: Score + Detailed feedback                          │
    └──────────────────────────────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
         Score < 90                Score ≥ 90
              │                         │
              ▼                         ▼
    ┌─────────────────────┐    ┌─────────────────────┐
    │  🔧 REFINER AGENT   │    │   ✅ APPROVED!      │
    │  ─────────────────  │    │   ─────────────     │
    │  • Takes feedback   │    │   Blog is ready     │
    │  • Improves draft   │    │   for delivery      │
    │  • Returns to       │    │                     │
    │    REVIEWER         │    │                     │
    └─────────┬───────────┘    └──────────┬──────────┘
              │                           │
              └───────► LOOP ◄────────────┘
                    (max 5 iterations)
```

### Security Guardrails

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         3-LAYER GUARDRAIL SYSTEM                             │
└─────────────────────────────────────────────────────────────────────────────┘

   Input Topic
        │
        ▼
┌───────────────────────────────────────┐
│  LAYER 1: INPUT VALIDATION (Regex)    │  ⚡ Instant (No API call)
│  ─────────────────────────────────    │
│  ✗ Empty/whitespace                   │
│  ✗ Too short (<3 chars)               │
│  ✗ Too long (>500 chars)              │
│  ✗ Only symbols (@#$%^&*)             │
│  ✗ Gibberish (no vowels: "qwrtyp")    │
│  ✗ Repetitive ("helloooooo")          │
│  ✗ Code injection (SQL, XSS)          │
│  ✗ Only numbers                       │
└───────────────┬───────────────────────┘
                │ PASS
                ▼
┌───────────────────────────────────────┐
│  LAYER 2: KEYWORD FILTER              │  ⚡ Instant (No API call)
│  ─────────────────────────────────    │
│  ✗ Violence: kill, bomb, terrorist    │
│  ✗ Sexual: porn, xxx, nude            │
│  ✗ Illegal: hack into, steal, fraud   │
│  ✗ Weapons: make bomb, 3d print gun   │
│  ✗ Drugs: cook meth, drug dealing     │
│  ✗ Hate: white supremacy, nazi        │
└───────────────┬───────────────────────┘
                │ PASS
                ▼
┌───────────────────────────────────────┐
│  LAYER 3: AI MODERATION (Gemini)      │  🤖 Smart (API call)
│  ─────────────────────────────────    │
│  ✗ Political bias/propaganda          │
│  ✗ Subtle harmful content             │
│  ✗ Contextual violations              │
│  ✓ Educational content                │
│  ✓ Technology/programming             │
│  ✓ Business/lifestyle                 │
└───────────────┬───────────────────────┘
                │ PASS
                ▼
        ┌───────────────┐
        │  ✅ APPROVED   │ ──► Start Pipeline
        └───────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Google Gemini API Key ([Get one free](https://aistudio.google.com/apikey))
- Gmail account with App Password

### 1. Clone & Setup

```bash
git clone https://github.com/yourusername/autoblog-ai.git
cd autoblog-ai

# Run setup script
chmod +x setup-backend.sh
./setup-backend.sh
```

### 2. Configure Environment

```bash
cd backend
cp .env.example .env
```

Edit `.env`:
```env
# Required
GEMINI_API_KEY=your-gemini-api-key

# Email Pipeline
EMAIL_ADDRESS=your-bot@gmail.com
EMAIL_PASSWORD=xxxx-xxxx-xxxx-xxxx  # Gmail App Password
EMAIL_IMAP_SERVER=imap.gmail.com
EMAIL_SMTP_SERVER=smtp.gmail.com

# Security: Only these emails can trigger blog generation
EMAIL_ALLOWED_SENDERS=your-personal@gmail.com
```

### 3. Get Gmail App Password

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable **2-Step Verification**
3. Go to [App Passwords](https://myaccount.google.com/apppasswords)
4. Create password for "Mail"
5. Copy the 16-character password to `.env`

### 4. Start Server

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --port 8000
```

### 5. Start Email Pipeline

```bash
curl -X POST http://localhost:8000/api/email-pipeline/start
```

### 6. Send Your First Blog Request! 🎉

Send an email:
- **To:** `your-bot@gmail.com`
- **Subject:** `The Future of AI Agents`
- **Body:** *(leave empty)*

Within 2-5 minutes, you'll receive a polished blog post in your inbox!

---

## 📡 API Endpoints

This backend exposes two interface modes:

| Mode | Use Case | Requires Email Config? |
|------|----------|------------------------|
| **📧 Email Pipeline** | Automated blog generation via email | ✅ Yes |
| **🌐 HTTP API** | Direct API calls for testing/integration | ❌ No |

---

### 📧 Email Pipeline Endpoints

*Primary interface - send an email, get a blog back automatically.*

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/email-pipeline/status` | GET | Pipeline status & job counts |
| `/api/email-pipeline/start` | POST | Start email monitoring (IMAP polling) |
| `/api/email-pipeline/stop` | POST | Stop email monitoring |
| `/api/email-pipeline/trigger` | POST | Manually trigger a blog job |
| `/api/email-pipeline/jobs` | GET | List all jobs (active + completed) |
| `/api/email-pipeline/check-topic` | POST | Test guardrails on a topic |
| `/api/email-pipeline/test-email` | POST | Test IMAP/SMTP connection |
| `/api/email-pipeline/config` | GET | Current email configuration |

**Services Used:** `email_service.py`, `email_pipeline.py`, `guardrail.py`, `gemini.py`

---

### 🌐 HTTP API Endpoints

*Alternative interface for direct programmatic access, testing, or building custom integrations.*

#### Full Pipeline (Streaming)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/pipeline` | POST | Run full pipeline with Server-Sent Events (SSE) streaming |

**Use Case:** Build custom frontends, integrate with other systems, or test the pipeline without email setup.

#### Individual Agent Endpoints

| Endpoint | Method | Description | Agent Used |
|----------|--------|-------------|------------|
| `/api/research` | POST | Research a topic | 🔍 Researcher |
| `/api/draft` | POST | Generate draft from research | ✍️ Drafter |
| `/api/review` | POST | Review and score a draft | 📋 Reviewer |
| `/api/refine` | POST | Refine draft with feedback | 🔧 Refiner |
| `/api/visualize` | POST | Generate images for slides | 🎨 Visualizer |
| `/api/config-chat` | POST | Natural language source config | 💬 Config Chat |

**Use Case:** Fine-grained control over individual pipeline stages, debugging, or building custom workflows.

**Services Used:** `gemini.py` only (no email services)

---

### 🔧 Utility Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check (used by Docker) |

---

### Endpoint Comparison

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ENDPOINT ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  📧 EMAIL PIPELINE (/api/email-pipeline/*)                              │
│  ─────────────────────────────────────────                              │
│  • Automated inbox monitoring                                            │
│  • Full pipeline with guardrails                                         │
│  • Results sent via email                                                │
│  • Background processing                                                 │
│                                                                          │
│  Services: email_service → guardrail → gemini → email_service           │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  🌐 HTTP API (/api/pipeline, /api/research, etc.)                       │
│  ───────────────────────────────────────────────                        │
│  • Direct API calls                                                      │
│  • SSE streaming for real-time updates                                   │
│  • Results returned in response                                          │
│  • Synchronous processing                                                │
│                                                                          │
│  Services: gemini (direct)                                               │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  📦 SHARED COMPONENTS                                                    │
│  ────────────────────                                                    │
│  • GeminiService (gemini.py) - All AI operations                        │
│  • Prompts (prompts/) - Agent prompts                                    │
│  • Schemas (models/) - Request/response types                            │
│                                                                          │
│  📧 EMAIL-ONLY COMPONENTS                                                │
│  ────────────────────────                                                │
│  • EmailService (email_service.py) - IMAP/SMTP                          │
│  • EmailPipelineOrchestrator (email_pipeline.py) - Job management       │
│  • GuardrailService (guardrail.py) - Content moderation                 │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```
| `/api/refine` | POST | Refine agent only |

### Example: Test Guardrails

```bash
# Safe topic
curl -X POST http://localhost:8000/api/email-pipeline/check-topic \
  -H "Content-Type: application/json" \
  -d '{"topic": "Machine learning best practices"}'

# Response: {"is_safe": true, "reason": "Educational technology topic"}
```

### Example: Manual Trigger

```bash
curl -X POST http://localhost:8000/api/email-pipeline/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "How to Build a SaaS in 2025",
    "recipient_email": "you@email.com"
  }'
```

---

## 📁 Project Structure

```
autoblog-ai/
├── backend/
│   ├── app/
│   │   ├── auth/                  # 🔐 JWT authentication (ready for future use)
│   │   │   ├── jwt.py             #    Token creation/verification
│   │   │   └── dependencies.py    #    FastAPI auth dependencies
│   │   ├── models/
│   │   │   └── schemas.py         # 📦 Pydantic models (shared)
│   │   ├── prompts/
│   │   │   └── templates.py       # 🤖 AI prompts (protected, shared)
│   │   ├── routers/
│   │   │   ├── email_pipeline.py  # 📧 Email trigger endpoints
│   │   │   ├── pipeline.py        # 🌐 HTTP: Full pipeline (SSE)
│   │   │   ├── research.py        # 🌐 HTTP: Research agent
│   │   │   ├── draft.py           # 🌐 HTTP: Draft agent
│   │   │   ├── review.py          # 🌐 HTTP: Review agent
│   │   │   ├── refine.py          # 🌐 HTTP: Refine agent
│   │   │   ├── visualize.py       # 🌐 HTTP: Image generation
│   │   │   ├── config_chat.py     # 🌐 HTTP: NL source config
│   │   │   └── health.py          # 🔧 Health check
│   │   ├── services/
│   │   │   ├── gemini.py          # 🤖 Gemini AI service (shared)
│   │   │   ├── email_service.py   # 📧 IMAP/SMTP handling
│   │   │   ├── email_pipeline.py  # 📧 Pipeline orchestrator
│   │   │   └── guardrail.py       # 📧 Content moderation
│   │   ├── config.py              # ⚙️ Environment config
│   │   └── main.py                # 🚀 FastAPI app
│   ├── .env.example
│   └── requirements.txt
├── setup-backend.sh
└── README.md

Legend: 📧 Email-specific | 🌐 HTTP API | 🤖 Shared AI | 🔧 Utility
```

---

## 🛡️ Security

### Guardrail System
- ✅ **3-layer content moderation** (regex → keywords → AI)
- ✅ **Email whitelist** - Only allowed senders can trigger

### Infrastructure
- ✅ **API keys server-side only** - Never exposed to clients
- ✅ **Prompts protected** - No prompt leakage endpoints
- ✅ **JWT authentication ready** - For future multi-user support
- ✅ **CORS configured** - Restricted origins

### Best Practices
- ✅ Use a **dedicated email** for the bot (not your personal email)
- ✅ Set **EMAIL_ALLOWED_SENDERS** to restrict who can trigger
- ✅ Change **JWT_SECRET_KEY** in production

---

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | ✅ | - | Google Gemini API key |
| `EMAIL_ADDRESS` | ✅* | - | Bot's email address |
| `EMAIL_PASSWORD` | ✅* | - | Gmail App Password |
| `EMAIL_ALLOWED_SENDERS` | ⚠️ | - | Whitelist (comma-separated) |
| `EMAIL_IMAP_SERVER` | - | imap.gmail.com | IMAP server |
| `EMAIL_SMTP_SERVER` | - | smtp.gmail.com | SMTP server |
| `EMAIL_CHECK_INTERVAL` | - | 60 | Seconds between inbox checks |
| `QUALITY_THRESHOLD` | - | 90 | Min score to approve blog |
| `MAX_REFINEMENT_ITERATIONS` | - | 5 | Max review-refine loops |

*Required for email pipeline

---

## 🧪 Development

### Run Tests

```bash
cd backend
source venv/bin/activate
pytest
```

### API Documentation

With `DEBUG=true`, visit: http://localhost:8000/docs

### Local Development

```bash
# Start with auto-reload
uvicorn app.main:app --reload --port 8000
```

---

## 📝 License

MIT License - see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with ❤️ using FastAPI + Google Gemini**

[Report Bug](https://github.com/yourusername/autoblog-ai/issues) • [Request Feature](https://github.com/yourusername/autoblog-ai/issues)

</div>
