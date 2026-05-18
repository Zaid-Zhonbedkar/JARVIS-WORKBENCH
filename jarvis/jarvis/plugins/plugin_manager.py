"""
JARVIS Plugin Manager
Hot-reloadable plugin system.
Plugins live in ~/.jarvis/plugins/ as Python packages.
"""

import os
import sys
import importlib
import importlib.util
import threading
import time
from pathlib import Path
from typing import Any, Optional
from core.config import Config


class JarvisPlugin:
    """
    Base class all JARVIS plugins must inherit from.

    Required:
        name: str          — unique plugin identifier
        description: str   — shown in UI
        version: str       — semver string

    Optional overrides:
        on_load(assistant)     — called when plugin loads
        on_unload()            — called when plugin unloads
        on_command(text) -> str|None  — intercept commands before AI
        get_tools() -> list    — return LangChain Tool objects
        get_ui_widget()        — return a PyQt6 widget (for sidebar)
    """

    name: str = "unnamed_plugin"
    description: str = ""
    version: str = "0.1.0"

    def __init__(self):
        self.assistant = None
        self.enabled = True

    def on_load(self, assistant: Any):
        self.assistant = assistant

    def on_unload(self):
        pass

    def on_command(self, text: str) -> Optional[str]:
        """
        Return a response string to short-circuit normal AI processing.
        Return None to let the command pass through to the AI.
        """
        return None

    def get_tools(self) -> list:
        """Return additional LangChain Tool objects for the agent."""
        return []

    def get_ui_widget(self) -> Any:
        """Return a PyQt6 QWidget to embed in the sidebar, or None."""
        return None


class PluginManager:
    """
    Discovers, loads, and hot-reloads JARVIS plugins.
    Watches the plugin directory for changes.
    """

    BUILTIN_PLUGIN_DIR = Path(__file__).parent / "builtin"
    USER_PLUGIN_DIR    = Path.home() / ".jarvis" / "plugins"

    def __init__(self, config: Config, assistant: Any):
        self.config = config
        self.assistant = assistant
        self._plugins: dict[str, JarvisPlugin] = {}
        self._modules: dict[str, Any] = {}
        self._watcher_thread: Optional[threading.Thread] = None
        self._mtimes: dict[str, float] = {}

    def load_all(self) -> int:
        """Load all plugins from builtin + user directories."""
        count = 0
        for directory in [self.BUILTIN_PLUGIN_DIR, self.USER_PLUGIN_DIR]:
            if directory.exists():
                for plugin_dir in directory.iterdir():
                    if plugin_dir.is_dir() and (plugin_dir / "__init__.py").exists():
                        if self._load_plugin(plugin_dir):
                            count += 1

        self._start_watcher()
        return count

    def _load_plugin(self, path: Path) -> bool:
        """Load a single plugin package."""
        pkg_name = f"jarvis_plugin_{path.name}"
        try:
            spec = importlib.util.spec_from_file_location(
                pkg_name, path / "__init__.py"
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[pkg_name] = module
            spec.loader.exec_module(module)

            # Find the Plugin class
            plugin_cls = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, JarvisPlugin)
                    and attr is not JarvisPlugin
                ):
                    plugin_cls = attr
                    break

            if not plugin_cls:
                print(f"[Plugins] No JarvisPlugin subclass in {path.name}")
                return False

            plugin = plugin_cls()
            plugin.on_load(self.assistant)

            self._plugins[plugin.name] = plugin
            self._modules[plugin.name] = module
            self._mtimes[str(path)] = (path / "__init__.py").stat().st_mtime

            # Register any additional tools with the agent
            if self.assistant.agent_module:
                for tool in plugin.get_tools():
                    self.assistant.agent_module._tools.append(tool)
                    print(f"[Plugins] Tool '{tool.name}' registered from {plugin.name}")

            print(f"[Plugins] Loaded: {plugin.name} v{plugin.version}")
            return True

        except Exception as e:
            print(f"[Plugins] Error loading {path.name}: {e}")
            return False

    def unload_plugin(self, name: str):
        """Unload and remove a plugin."""
        if name in self._plugins:
            self._plugins[name].on_unload()
            del self._plugins[name]
            print(f"[Plugins] Unloaded: {name}")

    def reload_plugin(self, path: Path):
        """Hot-reload a changed plugin."""
        # Find and unload existing
        for name, mod in list(self._modules.items()):
            if mod.__file__ and Path(mod.__file__).parent == path:
                self.unload_plugin(name)
                del self._modules[name]
                break
        self._load_plugin(path)

    def dispatch_command(self, text: str) -> Optional[str]:
        """
        Let all plugins intercept a command.
        Returns first non-None response, or None.
        """
        for plugin in self._plugins.values():
            if plugin.enabled:
                response = plugin.on_command(text)
                if response is not None:
                    return response
        return None

    def get_all_widgets(self) -> list:
        """Collect UI widgets from all plugins."""
        widgets = []
        for plugin in self._plugins.values():
            if plugin.enabled:
                w = plugin.get_ui_widget()
                if w:
                    widgets.append((plugin.name, w))
        return widgets

    def list_plugins(self) -> list[dict]:
        return [
            {"name": p.name, "description": p.description, "version": p.version, "enabled": p.enabled}
            for p in self._plugins.values()
        ]

    # ------------------------------------------------------------------ #
    #  Hot-reload file watcher
    # ------------------------------------------------------------------ #

    def _start_watcher(self):
        self._watcher_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watcher_thread.start()

    def _watch_loop(self):
        """Watch plugin directories for changes every 2 seconds."""
        while True:
            time.sleep(2)
            for directory in [self.BUILTIN_PLUGIN_DIR, self.USER_PLUGIN_DIR]:
                if not directory.exists():
                    continue
                for plugin_dir in directory.iterdir():
                    init = plugin_dir / "__init__.py"
                    if not init.exists():
                        continue
                    mtime = init.stat().st_mtime
                    key = str(plugin_dir)
                    if key in self._mtimes and self._mtimes[key] != mtime:
                        print(f"[Plugins] Change detected in {plugin_dir.name}, reloading…")
                        self.reload_plugin(plugin_dir)
