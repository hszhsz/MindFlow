# MindFlow

**AI-powered input method for macOS** — Transform keywords into complete, contextually appropriate text.

*From "typing your words" to "AI speaks your thoughts"*

---

## Features

### Intent-Driven Text Generation

Traditional input methods predict character by character. MindFlow generates complete sentences and paragraphs from keywords and intent.

```
User input: ;;项目进度延迟一周需要周三前通知甲方确认新的交付时间
AI output: ，需要周三前通知甲方确认新的交付时间，请查收并尽快回复。
```

### Screen Context Awareness

MindFlow understands which application you're working in — email, code editor, document — and generates contextually appropriate text.

### Personal Style Learning

Generated text sounds like you, not generic AI output. MindFlow learns your word preferences, tone, and expression patterns over time.

### Non-Disruptive Design

Designed for quiet environments:
- **Ghost Candidates** — Generated text silently queues; press Tab to accept
- **Minimal UI** — No distractions, no focus stealing
- **Keyboard-first** — No mouse required

### Structured Input Protocol

| Trigger | Effect |
|---------|--------|
| `;;` | AI continues current sentence |
| `;;mail` | Generate a complete email draft |
| `;;summary` | Organize input into bullet points |
| `;;polish` | Rewrite with improvements |
| `;;translate [lang]` | Instant translation |

---

## Architecture

```
┌──────────────────────────────┐
│   macOS Menu Bar App (Swift) │
│  Status Menu │ Hotkey Monitor │
└──────────────┼───────────────┘
               │ HTTP
               ▼
┌──────────────────────────────┐
│   Python Backend (FastAPI)    │
│  LLM Client │ Intent Classifier│
└──────────────────────────────┘
```

- **Frontend**: Swift + AppKit menu bar application
- **Backend**: Python 3.11+ with FastAPI
- **LLM**: Claude API (cloud) / llama.cpp (local, future)

---

## Getting Started

### Prerequisites

- macOS 12.0+
- Python 3.11+
- Claude API key (or other LLM provider)

### Backend Setup

```bash
cd src/backend
pip install -r requirements.txt

# Set your API key
export ANTHROPIC_API_KEY="your-key-here"

# Run the backend
python main.py
```

### Frontend Setup

```bash
cd src/frontend
open MindFlow.xcodeproj
```

Build and run in Xcode. The app will appear in your menu bar.

---

## Project Structure

```
MindFlow/
├── LICENSE
├── README.md
├── DESIGN.md              # Product design document
├── TECH-DESIGN.md         # Technical architecture
├── src/
│   ├── frontend/          # macOS menu bar app (Swift)
│   │   ├── main.swift
│   │   ├── StatusMenuController.swift
│   │   ├── HotkeyManager.swift
│   │   ├── CandidateWindow.swift
│   │   └── APIClient.swift
│   └── backend/          # Python backend service
│       ├── main.py
│       ├── llm_client.py
│       ├── intent_classifier.py
│       └── context_manager.py
└── tests/
```

---

## License

This project is open source under **GPL v3** with commercial licensing terms.

- Personal and educational use: **Free** under GPL v3
- Cloud-hosted services, enterprise embedding, SaaS: **Commercial license required**

See [LICENSE](LICENSE) for full details.

---

## Contributing

Contributions are welcome. By contributing, you agree that your contributions are licensed under the same license as the project.

---

## Roadmap

- [ ] Personal style fine-tuning
- [ ] Cross-session memory with vector storage
- [ ] Local LLM support (llama.cpp)
- [ ] Screen OCR for deep context
- [ ] Multi-language support
