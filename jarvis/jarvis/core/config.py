"""
JARVIS Configuration System
Loads and manages all settings from config.yaml
"""

import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VoiceConfig:
    wake_word: str = "jarvis"
    language: str = "en-US"
    energy_threshold: int = 300
    pause_threshold: float = 0.8
    tts_engine: str = "pyttsx3"       # pyttsx3 | coqui
    tts_rate: int = 175
    tts_volume: float = 0.9
    stt_backend: str = "google"        # google | whisper | vosk
    whisper_model: str = "base"


@dataclass
class AIConfig:
    provider: str = "ollama"           # ollama | openai | huggingface
    model: str = "llama3"
    ollama_host: str = "http://localhost:11434"
    openai_api_key: str = ""
    temperature: float = 0.7
    max_tokens: int = 2048
    system_prompt: str = (
        "You are JARVIS, an advanced AI desktop assistant. "
        "You are helpful, concise, and proactive. "
        "You have access to the user's computer and can execute tasks autonomously. "
        "Always confirm before making irreversible changes."
    )


@dataclass
class MemoryConfig:
    backend: str = "chroma"            # chroma | faiss | sqlite
    db_path: str = "~/.jarvis/memory"
    collection_name: str = "jarvis_memory"
    embedding_model: str = "all-MiniLM-L6-v2"
    max_results: int = 5
    conversation_window: int = 20


@dataclass
class VisionConfig:
    enabled: bool = True
    ocr_engine: str = "tesseract"
    screen_capture_fps: int = 1
    vision_model: str = "llava"        # requires ollama + llava
    screenshot_dir: str = "~/.jarvis/screenshots"


@dataclass
class UIConfig:
    theme: str = "dark"               # dark | light
    overlay_enabled: bool = True
    overlay_opacity: float = 0.92
    overlay_position: str = "top-right"
    font_family: str = "JetBrains Mono"
    accent_color: str = "#00FFB2"
    window_width: int = 900
    window_height: int = 650


@dataclass
class AgentConfig:
    max_iterations: int = 10
    timeout: int = 60
    browser_headless: bool = False
    code_sandbox: bool = True
    allowed_paths: list = field(default_factory=lambda: ["~/Documents", "~/Downloads", "~/Desktop"])


class Config:
    """Central configuration manager."""

    DEFAULT_CONFIG_PATH = Path.home() / ".jarvis" / "config.yaml"
    PROJECT_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

    def __init__(self, path: Optional[str] = None):
        self.voice = VoiceConfig()
        self.ai = AIConfig()
        self.memory = MemoryConfig()
        self.vision = VisionConfig()
        self.ui = UIConfig()
        self.agent = AgentConfig()

        config_path = path or self._find_config()
        if config_path and Path(config_path).exists():
            self._load(config_path)
        else:
            self._save_defaults()

    def _find_config(self) -> Optional[Path]:
        for p in [self.PROJECT_CONFIG_PATH, self.DEFAULT_CONFIG_PATH]:
            if p.exists():
                return p
        return None

    def _load(self, path: Path):
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
        self._apply(self.voice, data.get("voice", {}))
        self._apply(self.ai, data.get("ai", {}))
        self._apply(self.memory, data.get("memory", {}))
        self._apply(self.vision, data.get("vision", {}))
        self._apply(self.ui, data.get("ui", {}))
        self._apply(self.agent, data.get("agent", {}))
        print(f"[Config] Loaded from {path}")

    def _apply(self, obj, data: dict):
        for k, v in data.items():
            if hasattr(obj, k):
                setattr(obj, k, v)

    def _save_defaults(self):
        path = self.DEFAULT_CONFIG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "voice": self.voice.__dict__,
            "ai": self.ai.__dict__,
            "memory": self.memory.__dict__,
            "vision": self.vision.__dict__,
            "ui": self.ui.__dict__,
            "agent": self.agent.__dict__,
        }
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)
        print(f"[Config] Default config saved to {path}")

    def get_memory_path(self) -> Path:
        return Path(self.memory.db_path).expanduser()

    def get_screenshot_path(self) -> Path:
        return Path(self.vision.screenshot_dir).expanduser()
