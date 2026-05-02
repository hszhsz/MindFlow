# MindFlow

**AI-powered input method for macOS** — Type keywords, get complete sentences.

*From "typing your words" to "AI speaks your thoughts"*

---

## Quick Demo

```
You type:    ;;项目进度延迟一周需要通知甲方
AI returns:  尊敬的甲方负责人，您好。关于本次项目进度，因XXX原因导致延迟约一周，
             我们计划于周三前与您确认新的交付时间节点。如有疑问请随时沟通。
```

Press **Tab** to accept and paste into your current app. That's it.

---

## Two Ways to Use

| Mode | How | Best for |
|------|-----|----------|
| **Inline (`;;` trigger)** | Type `;;your keywords` + Enter in any app | Quick completions without leaving context |
| **Panel (Cmd+Shift+M)** | Opens a floating input panel | Longer intents, seeing results before inserting |

### Supported Triggers

| Trigger | Chinese alias | Effect |
|---------|---------------|--------|
| `;;text` | — | AI continues / completes the text |
| `;;mail` | `;;邮件` | Generate a complete email draft |
| `;;summary` | `;;总结` | Organize input into bullet points |
| `;;polish` | `;;润色` | Rewrite with improvements |
| `;;translate en` | `;;翻译 en` | Translate to specified language |
| `;;context` | `;;上下文` | Inject screen context |

---

## Prerequisites

- **macOS 12.0+** (Monterey or later)
- **Python 3.11+**
- **Xcode 15+** (for building the frontend)
- An LLM API key — **one** of the following:
  - **Anthropic API key** ([get one here](https://console.anthropic.com/)) — default provider
  - **OpenAI API key** ([get one here](https://platform.openai.com/api-keys))

---

## Installation & Setup

### Step 1: Clone the repo

```bash
git clone https://github.com/hszhsz/MindFlow.git
cd MindFlow
```

### Step 2: Set up the Python backend

```bash
# Create a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r src/backend/requirements.txt

# Create a .env file — choose ONE provider:

# Option A: Anthropic (default)
cat > .env << 'EOF'
MINDFLOW_LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-key-here
EOF

# Option B: OpenAI
cat > .env << 'EOF'
MINDFLOW_LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-openai-key-here
EOF

# Option C: OpenAI-compatible endpoint (Azure, local vLLM, Ollama, etc.)
cat > .env << 'EOF'
MINDFLOW_LLM_PROVIDER=openai
OPENAI_API_KEY=your-key-here
OPENAI_BASE_URL=http://localhost:11434/v1
MINDFLOW_MODEL_NAME=llama3
EOF
```

> **Note**: The backend reads API keys from environment variables or from a `.env` file in the project root. You can use either the standard names (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) or the prefixed form (`MINDFLOW_ANTHROPIC_API_KEY`, `MINDFLOW_OPENAI_API_KEY`).

### Step 3: Start the backend

```bash
# From the project root directory
python -m uvicorn src.backend.main:app --host 127.0.0.1 --port 8765

# You should see:
# INFO:     Started server process
# INFO:     Uvicorn running on http://127.0.0.1:8765
```

Verify it's running:

```bash
curl http://localhost:8765/health
# Expected: {"status":"ok","llm_available":true,"model":"claude-sonnet-4-20250514"}
```

### Step 4: Build the macOS frontend

**Option A: Using Xcode directly**

```bash
cd src/frontend
open MindFlow.xcodeproj
```

In Xcode:
1. Select the **MindFlow** target
2. Set signing to "Sign to Run Locally" (no Apple Developer account needed)
3. Press **Cmd+R** to build and run

**Option B: Using XcodeGen (if you modified project.yml)**

```bash
# Install XcodeGen if you don't have it
brew install xcodegen

# Generate the Xcode project
cd src/frontend
xcodegen generate

# Open and build
open MindFlow.xcodeproj
```

### Step 5: Grant Accessibility permission

On first launch, macOS will prompt you to grant Accessibility permission:

1. Go to **System Settings > Privacy & Security > Accessibility**
2. Toggle **MindFlow** ON
3. Restart the app if needed

> This is required for global hotkey detection and text insertion.

---

## Configuration

All backend settings can be configured via environment variables or `.env` file:

### Provider Selection

| Variable | Default | Description |
|----------|---------|-------------|
| `MINDFLOW_LLM_PROVIDER` | `anthropic` | LLM backend: `anthropic` or `openai` |

### Anthropic Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Your Anthropic API key (required when provider=anthropic) |
| `MINDFLOW_MODEL_NAME` | `claude-sonnet-4-20250514` | Model identifier |

### OpenAI Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | Your OpenAI API key (required when provider=openai) |
| `OPENAI_BASE_URL` | — | Custom endpoint URL (for Azure, vLLM, Ollama, etc.) |
| `MINDFLOW_MODEL_NAME` | `gpt-4o` | Model identifier |

### General Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `MINDFLOW_MAX_TOKENS` | `512` | Max tokens per generation |
| `MINDFLOW_SERVER_HOST` | `127.0.0.1` | Backend bind address |
| `MINDFLOW_SERVER_PORT` | `8765` | Backend port |
| `MINDFLOW_CONTEXT_HISTORY_SIZE` | `20` | Conversation turns to remember |

> **Tip**: All `MINDFLOW_`-prefixed variables override their non-prefixed equivalents. For example, `MINDFLOW_OPENAI_API_KEY` takes precedence over `OPENAI_API_KEY`.

Frontend settings (backend URL) can also be configured via the menu bar icon > **Settings**.

---

## Running Tests

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_intent_classifier.py
```

---

## Project Structure

```
MindFlow/
├── README.md
├── DESIGN.md              # Product design document
├── TECH-DESIGN.md         # Technical architecture
├── .env                   # Your local config (git-ignored)
├── pytest.ini             # Pytest configuration
├── requirements-dev.txt   # Dev/test dependencies
├── src/
│   ├── backend/           # Python backend service
│   │   ├── main.py        # FastAPI app (endpoints)
│   │   ├── config.py      # Settings management (pydantic-settings)
│   │   ├── llm_client.py  # Async Claude API client + streaming
│   │   ├── intent_classifier.py  # Trigger parsing & intent routing
│   │   ├── context_manager.py    # Session & long-term memory
│   │   └── requirements.txt
│   └── frontend/          # macOS menu bar app (Swift)
│       ├── main.swift                # App entry point
│       ├── AppDelegate.swift         # Lifecycle, hotkey registration
│       ├── HotkeyManager.swift       # ;; detection state machine
│       ├── InputPanel.swift          # Cmd+Shift+M floating panel
│       ├── CandidateWindow.swift     # Ghost candidate display
│       ├── StatusMenuController.swift # Menu bar UI & settings
│       ├── APIClient.swift           # Async HTTP + SSE client
│       ├── project.yml               # XcodeGen project definition
│       └── MindFlow.xcodeproj/       # Xcode project
└── tests/                 # Backend test suite (179 tests)
    ├── conftest.py
    ├── test_intent_classifier.py
    ├── test_context_manager.py
    ├── test_api.py
    └── test_llm_client.py
```

---

## API Reference

The backend exposes these endpoints on `http://127.0.0.1:8765`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check + LLM status |
| `/generate` | POST | Single-shot text generation |
| `/generate/stream` | POST | Streaming generation (SSE) |
| `/context` | POST | Update session context (app_type, language, project, topic) |
| `/forget` | POST | Clear session or all memory |

**Example request:**

```bash
curl -X POST http://localhost:8765/generate \
  -H "Content-Type: application/json" \
  -d '{"text": ";;mail 项目延期一周需要通知客户"}'
```

**Example response:**

```json
{
  "candidate": "尊敬的客户：\n\n感谢您一直以来对本项目的关注与支持...",
  "confidence": 0.92,
  "model": "claude-sonnet-4-20250514"
}
```

---

## Troubleshooting

### Backend won't start

```bash
# Check Python version (need 3.11+)
python3 --version

# Check if port is already in use
lsof -i :8765

# Run with debug logging
python -m uvicorn src.backend.main:app --host 127.0.0.1 --port 8765 --log-level debug
```

### "LLM not available" error

```bash
# Verify your API key is set (depends on which provider you chose)
echo $ANTHROPIC_API_KEY    # for Anthropic
echo $OPENAI_API_KEY       # for OpenAI

# Or check .env file exists in project root
cat .env

# Make sure MINDFLOW_LLM_PROVIDER matches the API key you've set
```

### Hotkeys not working

1. Ensure Accessibility permission is granted (System Settings > Privacy & Security > Accessibility)
2. Restart the app after granting permission
3. Check Console.app for `[MindFlow]` log messages

### Frontend can't connect to backend

- Ensure the backend is running (`curl http://localhost:8765/health`)
- Check the backend URL in menu bar > Settings (default: `http://localhost:8765`)
- If using a custom port, update both backend and frontend settings

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                macOS Menu Bar App (Swift)                 │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │StatusMenu│  │HotkeyManager │  │   InputPanel      │  │
│  │(on/off)  │  │(;; trigger)  │  │   (Cmd+Shift+M)   │  │
│  └──────────┘  └──────┬───────┘  └─────────┬─────────┘  │
│                        │                    │             │
│                        └────────┬───────────┘             │
│                                 │ async HTTP / SSE        │
│                     ┌───────────┴──────────┐              │
│                     │     APIClient        │              │
│                     └───────────┬──────────┘              │
└─────────────────────────────────┼────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────┐
│               Python Backend (FastAPI)                    │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │  Router  │  │Intent Classif│  │   LLM Client      │  │
│  │ (main.py)│  │(;;mail/总结) │  │(Anthropic/OpenAI) │  │
│  └──────────┘  └──────────────┘  └───────────────────┘  │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │  Config  │  │Context Manager│  │  SSE Streaming    │  │
│  │(settings)│  │(memory/history)│ │  (sse-starlette)  │  │
│  └──────────┘  └──────────────┘  └───────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

---

## Roadmap

- [x] Multi-provider LLM support (Anthropic Claude + OpenAI GPT + any OpenAI-compatible API)
- [ ] Personal style fine-tuning (learn your writing patterns)
- [ ] Cross-session memory with vector storage
- [ ] Local LLM support via Apple MLX / llama.cpp
- [ ] Screen OCR for deep context awareness
- [ ] Multi-language UI support
- [ ] Plugin ecosystem for application-specific behavior

---

## License

**GPL v3** with commercial licensing terms.

- Personal and educational use: **Free** under GPL v3
- Cloud-hosted services, enterprise embedding, SaaS: **Commercial license required**

See [LICENSE](LICENSE) for full details.

---

## Contributing

Contributions are welcome! Please:

1. Fork the repo
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Commit your changes
4. Push and open a Pull Request

By contributing, you agree that your contributions are licensed under the same license as the project.
