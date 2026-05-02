# MindFlow Technical Design

## Overview

MindFlow uses a **menu bar app + Python backend** architecture for macOS. The menu bar app handles user interaction and keyboard monitoring, while a Python backend handles LLM inference and AI logic.

**Core Principle:** Simple on the client, sophisticated on the backend.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     macOS Menu Bar App (Swift)              │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Status Menu  │  │ Hotkey Monitor │  │ HTTP/Unix Socket │  │
│  │ (On/Off)     │  │ (;; trigger)   │  │ Client           │  │
│  └─────────────┘  └──────────────┘  └────────┬─────────┘  │
└──────────────────────────────────────────────┼─────────────┘
                                               │
                                               ▼
┌────────────────────────────────────────────────────────────────┐
│                     Python Backend Service                      │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ FastAPI      │  │ LLM Client   │  │ Intent Classifier   │  │
│  │ (REST API)   │  │ (Multi-backend)│ │ (Trigger parsing)   │  │
│  └──────────────┘  └──────────────┘  └────────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ Context Mgr  │  │ Style Engine │  │ Cache Layer        │  │
│  │ (Session)    │  │ (Personal)   │  │ (Redis/Memory)      │  │
│  └──────────────┘  └──────────────┘  └────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

---

## Module Details

### 1. Frontend: macOS Menu Bar App (Swift)

**Responsibilities:**
- Display status menu (MindFlow icon, on/off toggle)
- Register global hotkey (`;;`)
- Monitor keyboard input for trigger sequence
- Send user input to backend and display candidates
- Handle candidate selection (Tab/Enter)

**Key Components:**

| Component | Description |
|-----------|-------------|
| `StatusMenuController` | Manages menu bar icon and dropdown |
| `HotkeyManager` | Registers and handles global hotkey events |
| `APIClient` | HTTP/Unix socket client to backend service |
| `CandidateWindow` | NSPanel to display ghost candidates |

**Technology:** Swift + AppKit (no SwiftUI for better performance)

---

### 2. Backend: Python Service

**Technology Stack:**
- **Framework:** FastAPI (async, lightweight)
- **LLM Clients:** OpenAI SDK, Anthropic SDK, llama.cpp Python bindings
- **Runtime:** Python 3.11+

**Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/generate` | POST | Generate text continuation |
| `/intent` | POST | Classify user intent from trigger |
| `/context` | POST | Update/push context (screen content) |
| `/health` | GET | Health check |

**Request/Response Example:**
```json
// POST /generate
{
  "text": "项目进度延迟一周",
  "intent": "continue",
  "context": {
    "app": "mail",
    "language": "zh"
  }
}

// Response
{
  "candidate": "，需要周三前通知甲方确认新的交付时间",
  "confidence": 0.92,
  "model": "claude-3-5-sonnet"
}
```

---

### 3. Intent Classifier

Classifies user input to route to appropriate handler.

**Supported Intents:**

| Intent | Trigger | Handler |
|--------|---------|---------|
| `continue` | `;;` followed by text | LLM continuation |
| `mail` | `;;mail` | Email template generator |
| `summary` | `;;summary` | Bullet point summarizer |
| `polish` | `;;polish` | Style improver |
| `translate` | `;;translate [lang]` | Translator |
| `context` | `;;context` | Inject screen context |

---

### 4. LLM Client (Multi-Backend)

```python
class LLMClient:
    """Routes to appropriate LLM backend based on task complexity."""

    def __init__(self):
        self.clients = {
            'local': LlamaCppClient(),      # Simple tasks, offline
            'claude': AnthropicClient(),     # Complex tasks
            'openai': OpenAIClient(),        # Fallback
        }
        self.strategy = HybridStrategy()

    async def generate(self, prompt, intent):
        # Route based on intent complexity
        backend = self.strategy.select(intent)
        return await self.clients[backend].complete(prompt)
```

**Routing Strategy:**
- Simple continuation (`;;text`) → Local model (llama.cpp)
- Complex generation (mail, summary) → Claude/GPT-4

---

### 5. Context Manager

Manages cross-session state and context awareness.

**Data Stored:**
```python
class SessionContext:
    project: str              # Current project name
    topic: str                # Discussion topic
    history: List[Turn]       # Recent input/output pairs
    app_type: str            # Current application (mail, code, chat)
    language: str            # Input/output language
```

**Context Sources:**
- Explicit: User input via triggers
- Implicit: Active window title (via Accessibility API)

---

### 6. Cache Layer

**Why:** Reduce LLM API calls and latency.

**Strategies:**
- **Intent caching:** Same intent + context → cached response
- **Semantic caching:** Vector similarity search on recent prompts
- **Session cache:** In-memory for current session

**Technology:** In-memory dict (MVP) → Redis (production)

---

## Communication Protocol

### Option A: HTTP (Simpler)

```python
# Swift client
let response = try await URLSession.shared.post(
    "http://localhost:8765/generate",
    body: request
)
```

Pros: Simple, well-supported
Cons: Higher latency per request

### Option B: Unix Socket (Lower Latency)

```python
# Python backend
async with UnixHTTPServer(sock_path="/tmp/mindflow.sock"):
    ...
```

Pros: Lower latency, more secure
Cons: Slightly more complex setup

**Decision:** HTTP for MVP (simpler to debug), Unix socket for production.

---

## Data Flow

```
1. User types ";;项目进度延迟一周" in any app
          │
          ▼
2. Swift HotkeyMonitor detects trigger sequence
          │
          ▼
3. Swift extracts text after ";;" → sends to backend
          │
          ▼
4. Python IntentClassifier parses "continue"
          │
          ▼
5. LLMClient routes to appropriate model
          │
          ▼
6. Backend returns candidate text
          │
          ▼
7. Swift CandidateWindow shows ghost text
          │
          ▼
8. User presses Tab → Candidate injected into active app
          │              OR
          User presses Enter → Original input kept
```

---

## MVP Technology Choices

| Layer | Technology | Reason |
|-------|-----------|--------|
| Frontend | Swift + AppKit | Native macOS performance |
| Backend | Python 3.11 + FastAPI | Rapid development, async |
| LLM | Claude API (initial) | Best quality/price, good Chinese |
| Local LLM | llama.cpp (future) | Offline capability |
| Communication | HTTP | Simpler debugging |
| Context | In-memory (MVP) | Simplicity |

---

## File Structure

```
MindFlow/
├── README.md
├── DESIGN.md
├── TECH-DESIGN.md
├── src/
│   ├── frontend/           # macOS menu bar app
│   │   ├── main.swift
│   │   ├── StatusMenuController.swift
│   │   ├── HotkeyManager.swift
│   │   └── CandidateWindow.swift
│   └── backend/           # Python service
│       ├── main.py
│       ├── llm_client.py
│       ├── intent_classifier.py
│       └── context_manager.py
├── tests/
└── docs/
```

---

## Next Steps

1. Set up project structure
2. Implement Python backend with Claude API integration
3. Build Swift menu bar app skeleton
4. Wire up hotkey → backend → candidate display flow
5. Test end-to-end with actual input

---

## Decisions

| Question | Decision |
|----------|----------|
| Local model support | MVP 后再加，先用 Claude API |
| Multi-monitor/multi-app context | **最近焦点 + 可手动覆盖**：默认使用当前聚焦应用的上下文，用户可通过 `;;context` 手动指定或刷新上下文 |
| LLM unavailable fallback | 暂时不可用，等待 LLM 恢复 |
| Context data storage | 长短期记忆：短期（当前会话）+ 长期（跨会话重要上下文） |

---

## Multi-App Context Strategy

**Core Principle:** "Focus-following" — follow the user's current attention.

**Implementation:**
```
1. Monitor focused application (via macOS Accessibility API)
2. Extract context from focused app:
   - App bundle ID → app type (mail, code, chat, browser)
   - Active window title → document/project context
3. Use app type for intent routing
4. User can override with ;;context to force refresh
```

**App Type Classification:**
| App Type | Examples | Context Behavior |
|----------|----------|------------------|
| `mail` | Mail, Outlook | Previous emails in thread |
| `code` | VS Code, Xcode | Current file language/style |
| `chat` | Slack, WeChat | Recent messages in conversation |
| `doc` | Word, Notes, Notion | Document topic and structure |
| `other` | Default | General purpose |

**Privacy:** No screen content is captured — only app type and window title (which users can opt out of).
