# MindFlow Design Document

## Overview

MindFlow is an AI-powered input method that transforms the way knowledge workers interact with text. Instead of typing word-by-word, users input keywords and意图 and let the LLM generate complete, contextually appropriate text. Designed for quiet environments where disrupting thought flow is unacceptable.

**Core Philosophy:** From "typing your words" to "AI speaks your thoughts"

---

## Core Features

### 1. Intent-Driven Sentence/Paragraph Generation

**Current state:** Traditional input methods predict the next character or word.

**Innovation:** Users input a few keywords or a意图 description, and the LLM generates a complete, structured sentence or paragraph.

**Example:**
```
User input: 项目进度延迟一周需要周三前通知甲方确认新的交付时间
AI output: 生成一封结构完整的邮件，包含称呼、说明、请求和截止日期
```

**Key Design:** Real-time progressive generation — as the user types, AI continuously completes the remaining text. Not waiting for full input, then generating.

---

### 2. Screen/Document Context Awareness

**Current state:** Input methods have no awareness of which application or document the user is working in.

**Innovation:** Read the current window's text content (via OCR or accessibility APIs), understand the context, and generate relevant candidates.

**Use cases:**
- Writing code → complete comments in project's coding style
- Composing email → suggest contextually appropriate replies
- Editing documents → generate text coherent with preceding content

---

### 3. Personal Style Learning

**Current state:** All users receive the same AI completions.

**Innovation:** Fine-tune a lightweight model (or use prompt engineering) to learn the user's:
- Word preferences ("我觉得" vs "我认为")
- Sentence length preferences
- Tone formality level
- Common expression patterns

Result: Generated text "sounds like you" — not generic AI output.

---

### 4. Cross-Session Thought Continuity

**Current state:** Each input session is independent with no context from previous sessions.

**Innovation:** Remember projects, topics under discussion, and content already covered — across sessions.

**Example:**
```
User input: "接着上次的"
AI output: 结合几小时前的 discussion, continues the thought seamlessly
```

---

### 5. Non-Disruptive Interaction Design

**Core Constraint:** Quiet environments require zero interruption to thought flow.

**Design Principles:**

- **Ghost Candidates:** Generated text enters buffer directly; user presses Tab to confirm, Enter to keep original input
- **Silent Mode:** AI runs in background; candidates shown only when user triggers or hovers
- **Minimal Visual:** No distractions, no focus stealing

---

### 6. Structured Input Protocol

Intent classification via short trigger words:

| Trigger | Effect |
|---------|--------|
| `;;` | AI continues current sentence |
| `;;mail` | Generate a complete email draft |
| `;;summary` | Organize scattered input into bullet points |
| `;;polish` | Rewrite selected text with improvements |
| `;;translate` | Instant translation (quiet environment = no speaking needed) |
| `;;context` | Inject relevant context from screen/document |

---

## Technical Architecture

```
User Input → Local LLM Client → Intent Classification → Routing
                                                     ├→ Continuation
                                                     ├→ Template Fill
                                                     ├→ Style Rewrite
                                                     └→ Cross-Session Memory
```

### Local vs Cloud Decision

| Approach | Pros | Cons |
|----------|------|------|
| **Local (llama.cpp/MLX)** | Privacy, works offline | Higher latency, needs GPU |
| **Cloud (OpenAI/Claude API)** | Better capability, lower latency | Privacy concerns, internet required |
| **Hybrid (Recommended)** | Simple tasks local, complex tasks cloud | More complex implementation |

---

## MVP Scope

First version focuses on simplest but highest-value features:

1. **`;;` Continuation** — trigger AI to complete current sentence
2. **Ghost Candidates** — generated text silently queued, Tab to accept
3. **Basic Context Awareness** — detect current application type (browser/IDE/email)

---

## Future Considerations

- Personal style fine-tuning
- Cross-session memory with vector storage
- Screen OCR for deep context
- Multi-language support
- Plugin ecosystem for different applications
