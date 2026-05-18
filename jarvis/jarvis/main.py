#!/usr/bin/env python3
"""
JARVIS - Just A Rather Very Intelligent System
AI Desktop Assistant
"""

import sys
import os
import threading
import signal

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from core.assistant import JarvisAssistant
from ui.main_window import MainWindow
from ui.overlay import OverlayHUD
from core.config import Config


def main():
    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    app.setApplicationName("JARVIS")
    app.setOrganizationName("JarvisAI")
    app.setQuitOnLastWindowClosed(False)

    # Load config
    config = Config()

    # Initialize core assistant (AI brain)
    assistant = JarvisAssistant(config)

    # Build UI
    window = MainWindow(assistant, config)
    overlay = OverlayHUD(assistant, config)

    window.show()

    # Start assistant background services
    assistant.start()

    print("[JARVIS] System online. All modules loaded.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
