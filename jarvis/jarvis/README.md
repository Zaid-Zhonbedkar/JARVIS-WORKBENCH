# JARVIS — AI Desktop Assistant

> A Jarvis-style Python desktop AI with voice control, autonomous agents,
> screen understanding, persistent memory, and a hot-reload plugin system.

---

## Quick Start

### 1. Prerequisites

```bash
# System packages (Ubuntu/Debian)
sudo apt install portaudio19-dev tesseract-ocr python3-dev

# macOS
brew install portaudio tesseract
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium
```

### 3. Set up a local LLM (recommended: Ollama)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3          # fast, capable
ollama pull llava           # for screen understanding (vision)
```

### 4. Configure

Edit `config.yaml` — the defaults work with Ollama out of the box.

```yaml
ai:
  provider: "ollama"
  model: "llama3"

voice:
  wake_word: "jarvis"
  stt_backend: "google"    # free, requires internet
  # stt_backend: "whisper" # fully offline (pip install openai-whisper)
```

### 5. Run

```bash
python main.py
```

---

## Architecture

```
jarvis/
├── main.py                 # Entry point
├── config.yaml             # All settings
│
├── core/
│   ├── assistant.py        # Central brain — orchestrates all modules
│   └── config.py           # Config dataclasses + YAML loader
│
├── modules/
│   ├── ai_module.py        # LLM client (Ollama / OpenAI / HuggingFace)
│   └── voice_module.py     # STT + TTS + wake word loop
│
├── memory/
│   └── memory_store.py     # ChromaDB vector memory
│
├── agents/
│   └── agent_runner.py     # LangChain ReAct agent + tools
│
├── vision/
│   └── vision_module.py    # Screen capture + OCR + LLaVA understanding
│
├── ui/
│   ├── main_window.py      # PyQt6 terminal-style chat UI
│   └── overlay.py          # Transparent always-on-top HUD
│
└── plugins/
    ├── plugin_manager.py   # Discovery, loading, hot-reload
    └── builtin/
        └── weather/        # Example: weather plugin
```

---

## Voice Commands

Say **"Jarvis"** followed by your command:

| Command | What happens |
|---------|-------------|
| "Jarvis, what's the weather?" | Weather plugin intercepts, returns wttr.in |
| "Jarvis, open Chrome and search for X" | Agent uses Playwright browser tool |
| "Jarvis, find the file called budget" | Agent scans allowed paths |
| "Jarvis, run this Python code: …" | Agent executes in sandbox |
| "Jarvis, what's on my screen?" | Vision module runs OCR or LLaVA |
| "Jarvis, system status" | Returns CPU/RAM/disk via psutil |

---

## Writing a Plugin

Create `~/.jarvis/plugins/myplugin/__init__.py`:

```python
from plugins.plugin_manager import JarvisPlugin
from langchain.tools import Tool

class MyPlugin(JarvisPlugin):
    name = "my_plugin"
    description = "Does something cool"
    version = "1.0.0"

    def on_command(self, text: str):
        if "my trigger" in text.lower():
            return "I caught that command!"
        return None  # pass through to AI

    def get_tools(self):
        return [
            Tool(
                name="my_tool",
                func=lambda q: f"Tool result for: {q}",
                description="My custom tool for the agent"
            )
        ]
```

JARVIS hot-reloads it within 2 seconds. No restart needed.

---

## AI Backends

| Backend | Config | Notes |
|---------|--------|-------|
| Ollama | `provider: ollama` | Best choice — fully local, free |
| OpenAI | `provider: openai` + API key | GPT-4o, fast |
| HuggingFace | `provider: huggingface` | Any GGUF/HF model |

---

## Key Libraries

| Library | Role |
|---------|------|
| `PyQt6` | GUI + overlay |
| `langchain` | Agents, tools, LLM abstraction |
| `chromadb` | Vector memory |
| `sentence-transformers` | Embeddings for memory |
| `speechrecognition` | STT |
| `pyttsx3` / Coqui | TTS |
| `playwright` | Browser automation |
| `opencv-python` | Screen capture + image processing |
| `pytesseract` | OCR |
| `duckduckgo-search` | Web search (no API key) |
| `psutil` | System metrics |
