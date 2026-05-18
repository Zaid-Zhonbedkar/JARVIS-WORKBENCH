"""
JARVIS Core Assistant
Central brain that orchestrates all modules, voice, agents, and memory.
"""

import threading
import queue
import time
from typing import Optional, Callable
from PyQt6.QtCore import QObject, pyqtSignal

from core.config import Config


class JarvisAssistant(QObject):
    """
    Central orchestrator for JARVIS.
    Runs background threads for voice, agents, and memory.
    Emits Qt signals to update the UI.
    """

    # Qt signals for UI updates
    response_ready    = pyqtSignal(str)          # AI text response
    status_changed    = pyqtSignal(str)          # Status bar text
    listening_changed = pyqtSignal(bool)         # Mic active indicator
    thinking_changed  = pyqtSignal(bool)         # Processing spinner
    memory_updated    = pyqtSignal(list)         # Memory panel refresh
    overlay_message   = pyqtSignal(str)          # HUD overlay text
    module_log        = pyqtSignal(str, str)     # (module_name, log_line)

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self._running = False
        self._command_queue: queue.Queue = queue.Queue()
        self._response_callbacks: list[Callable] = []

        # Lazy-loaded modules (initialized in start())
        self.voice_module   = None
        self.ai_module      = None
        self.memory_module  = None
        self.agent_module   = None
        self.vision_module  = None
        self.plugin_manager = None

        self._threads: list[threading.Thread] = []

    # ------------------------------------------------------------------ #
    #  Lifecycle
    # ------------------------------------------------------------------ #

    def start(self):
        self._running = True
        self.status_changed.emit("Initializing modules…")
        init_thread = threading.Thread(target=self._init_modules, daemon=True)
        init_thread.start()

    def stop(self):
        self._running = False
        if self.voice_module:
            self.voice_module.stop()
        self.status_changed.emit("Offline")

    # ------------------------------------------------------------------ #
    #  Module initialization (background thread)
    # ------------------------------------------------------------------ #

    def _init_modules(self):
        self._load_ai()
        self._load_memory()
        self._load_agents()
        self._load_voice()
        self._load_vision()
        self._load_plugins()
        self.status_changed.emit("Online — ready")
        self.overlay_message.emit("JARVIS online.")

    def _load_ai(self):
        self.module_log.emit("AI", "Loading language model…")
        try:
            from modules.ai_module import AIModule
            self.ai_module = AIModule(self.config)
            self.module_log.emit("AI", f"Model ready: {self.config.ai.model}")
        except Exception as e:
            self.module_log.emit("AI", f"[WARN] Could not load AI module: {e}")

    def _load_memory(self):
        self.module_log.emit("Memory", "Initializing vector store…")
        try:
            from memory.memory_store import MemoryStore
            self.memory_module = MemoryStore(self.config)
            self.module_log.emit("Memory", "Memory store ready")
        except Exception as e:
            self.module_log.emit("Memory", f"[WARN] Memory unavailable: {e}")

    def _load_agents(self):
        self.module_log.emit("Agents", "Configuring agent runtime…")
        try:
            from agents.agent_runner import AgentRunner
            self.agent_module = AgentRunner(self.config, self.ai_module, self.memory_module)
            self.module_log.emit("Agents", "Agents ready")
        except Exception as e:
            self.module_log.emit("Agents", f"[WARN] Agent runtime error: {e}")

    def _load_voice(self):
        self.module_log.emit("Voice", "Starting voice engine…")
        try:
            from modules.voice_module import VoiceModule
            self.voice_module = VoiceModule(
                config=self.config,
                on_command=self._on_voice_command,
                on_listening=lambda v: self.listening_changed.emit(v),
            )
            self.voice_module.start()
            self.module_log.emit("Voice", f"Wake word: '{self.config.voice.wake_word}'")
        except Exception as e:
            self.module_log.emit("Voice", f"[WARN] Voice unavailable: {e}")

    def _load_vision(self):
        if not self.config.vision.enabled:
            return
        self.module_log.emit("Vision", "Starting vision pipeline…")
        try:
            from vision.vision_module import VisionModule
            self.vision_module = VisionModule(self.config)
            self.module_log.emit("Vision", "Screen understanding active")
        except Exception as e:
            self.module_log.emit("Vision", f"[WARN] Vision unavailable: {e}")

    def _load_plugins(self):
        self.module_log.emit("Plugins", "Scanning plugin directory…")
        try:
            from plugins.plugin_manager import PluginManager
            self.plugin_manager = PluginManager(self.config, self)
            count = self.plugin_manager.load_all()
            self.module_log.emit("Plugins", f"{count} plugin(s) loaded")
        except Exception as e:
            self.module_log.emit("Plugins", f"[WARN] Plugin system error: {e}")

    # ------------------------------------------------------------------ #
    #  Command handling
    # ------------------------------------------------------------------ #

    def _on_voice_command(self, text: str):
        """Called by VoiceModule when a command is recognized."""
        self.module_log.emit("Voice", f"Heard: {text}")
        self.process_command(text, source="voice")

    def process_command(self, text: str, source: str = "text"):
        """Entry point for any command — voice or typed."""
        self.thinking_changed.emit(True)
        self.status_changed.emit("Thinking…")

        thread = threading.Thread(
            target=self._run_command,
            args=(text, source),
            daemon=True,
        )
        thread.start()

    def _run_command(self, text: str, source: str):
        try:
            # Store user message in memory
            if self.memory_module:
                self.memory_module.add(role="user", content=text)

            # Try agentic route first for complex tasks
            response = None
            if self.agent_module and self._is_agentic(text):
                response = self.agent_module.run(text)
            elif self.ai_module:
                context = self._build_context(text)
                response = self.ai_module.chat(text, context=context)
            else:
                response = "[No AI module loaded — check config]"

            # Store assistant reply
            if self.memory_module and response:
                self.memory_module.add(role="assistant", content=response)

            self.response_ready.emit(response)
            self.overlay_message.emit(response[:120] + "…" if len(response) > 120 else response)

            # Speak response
            if source == "voice" and self.voice_module:
                self.voice_module.speak(response)

        except Exception as e:
            err = f"[Error] {e}"
            self.response_ready.emit(err)
        finally:
            self.thinking_changed.emit(False)
            self.status_changed.emit("Online — ready")

    def _is_agentic(self, text: str) -> bool:
        """Heuristic to detect if a command needs an agent (multi-step, tools, etc.)"""
        keywords = [
            "open", "search", "browse", "download", "run", "execute",
            "find file", "create file", "write code", "take screenshot",
            "click", "fill", "automate", "send email", "schedule",
        ]
        t = text.lower()
        return any(k in t for k in keywords)

    def _build_context(self, text: str) -> str:
        """Pull relevant memories to prepend as context."""
        if not self.memory_module:
            return ""
        memories = self.memory_module.search(text, k=self.config.memory.max_results)
        if not memories:
            return ""
        lines = "\n".join(f"- {m}" for m in memories)
        return f"Relevant context from memory:\n{lines}"

    # ------------------------------------------------------------------ #
    #  Vision helpers
    # ------------------------------------------------------------------ #

    def capture_screen_context(self) -> str:
        """Ask vision module to describe current screen."""
        if self.vision_module:
            return self.vision_module.describe_screen()
        return "Vision module not available."

    def ocr_screen(self) -> str:
        """Extract text from current screen via OCR."""
        if self.vision_module:
            return self.vision_module.ocr_screen()
        return "Vision module not available."
