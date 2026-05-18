"""
JARVIS Main Window
PyQt6 terminal-style HUD interface with chat, logs, memory panel.
"""

import time
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel,
    QSplitter, QFrame, QScrollArea, QSystemTrayIcon, QMenu,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QThread
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QTextCursor, QIcon,
    QKeyEvent, QAction,
)

from core.config import Config


DARK_STYLE = """
QMainWindow, QWidget {
    background: #0A0B0D;
    color: #C8D0D8;
    font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
    font-size: 13px;
}
QTextEdit {
    background: #0D0F12;
    border: 1px solid #1E2530;
    border-radius: 6px;
    color: #C8D0D8;
    selection-background-color: #1D3A2F;
    padding: 8px;
}
QLineEdit {
    background: #0D0F12;
    border: 1px solid #1E2530;
    border-radius: 6px;
    color: #E8EDF2;
    padding: 8px 12px;
    font-size: 14px;
}
QLineEdit:focus {
    border: 1px solid #00FFB2;
}
QPushButton {
    background: transparent;
    border: 1px solid #1E2530;
    border-radius: 5px;
    color: #00FFB2;
    padding: 6px 16px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
}
QPushButton:hover {
    background: #0D2420;
    border-color: #00FFB2;
}
QPushButton:pressed {
    background: #0A1A16;
}
QPushButton#danger {
    color: #FF5555;
    border-color: #2A1515;
}
QPushButton#danger:hover {
    background: #1A0808;
    border-color: #FF5555;
}
QSplitter::handle {
    background: #1E2530;
    width: 1px;
}
QScrollBar:vertical {
    background: #0A0B0D;
    width: 6px;
    border-radius: 3px;
}
QScrollBar::handle:vertical {
    background: #2A3040;
    border-radius: 3px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QLabel#header {
    color: #00FFB2;
    font-size: 11px;
    letter-spacing: 2px;
    padding: 4px 0;
}
QLabel#status {
    color: #5A7A6A;
    font-size: 11px;
}
QFrame#separator {
    background: #1E2530;
    max-height: 1px;
}
"""


class MainWindow(QMainWindow):
    def __init__(self, assistant, config: Config):
        super().__init__()
        self.assistant = assistant
        self.config = config
        self._history: list[str] = []
        self._history_idx: int = -1
        self._thinking_timer = QTimer()
        self._thinking_frames = ["◐", "◓", "◑", "◒"]
        self._thinking_i = 0

        self._setup_window()
        self._setup_ui()
        self._connect_signals()
        self._setup_tray()
        self._start_clock()

    # ------------------------------------------------------------------ #
    #  Window setup
    # ------------------------------------------------------------------ #

    def _setup_window(self):
        self.setWindowTitle("JARVIS — AI Desktop Assistant")
        self.setMinimumSize(800, 560)
        self.resize(self.config.ui.window_width, self.config.ui.window_height)
        self.setStyleSheet(DARK_STYLE)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar
        root.addWidget(self._build_topbar())
        root.addWidget(self._separator())

        # Main content area
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_chat_panel())
        splitter.addWidget(self._build_sidebar())
        splitter.setSizes([620, 260])
        splitter.setHandleWidth(1)
        root.addWidget(splitter, 1)

        root.addWidget(self._separator())
        root.addWidget(self._build_input_bar())
        root.addWidget(self._build_statusbar())

    # ------------------------------------------------------------------ #
    #  Sub-panels
    # ------------------------------------------------------------------ #

    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(44)
        bar.setStyleSheet("background: #08090B; border-bottom: 1px solid #141820;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)

        dot_green = QLabel("●")
        dot_green.setStyleSheet("color: #00FFB2; font-size: 10px;")
        layout.addWidget(dot_green)

        title = QLabel("J·A·R·V·I·S")
        title.setStyleSheet(
            "color: #00FFB2; font-size: 13px; letter-spacing: 4px; "
            "font-weight: bold; margin-left: 8px;"
        )
        layout.addWidget(title)

        subtitle = QLabel("AI DESKTOP ASSISTANT")
        subtitle.setStyleSheet("color: #2A4A3A; font-size: 10px; letter-spacing: 3px; margin-left: 12px;")
        layout.addWidget(subtitle)

        layout.addStretch()

        self.lbl_listening = QLabel("◉ MIC")
        self.lbl_listening.setStyleSheet("color: #1E3A2A; font-size: 10px; letter-spacing: 2px;")
        layout.addWidget(self.lbl_listening)

        layout.addSpacing(16)

        self.lbl_clock = QLabel()
        self.lbl_clock.setStyleSheet("color: #3A5A4A; font-size: 11px; letter-spacing: 1px;")
        layout.addWidget(self.lbl_clock)

        return bar

    def _build_chat_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 6, 12)
        layout.setSpacing(8)

        hdr = QLabel("// CHAT")
        hdr.setObjectName("header")
        layout.addWidget(hdr)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout.addWidget(self.chat_display, 1)

        self._append_chat("system", "JARVIS online. All systems initializing…")
        return panel

    def _build_sidebar(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet("background: #08090B;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 12, 12, 12)
        layout.setSpacing(12)

        # Module log
        log_hdr = QLabel("// MODULE LOG")
        log_hdr.setObjectName("header")
        layout.addWidget(log_hdr)

        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMaximumHeight(200)
        layout.addWidget(self.log_display)

        sep = self._separator()
        layout.addWidget(sep)

        # Memory panel
        mem_hdr = QLabel("// MEMORY")
        mem_hdr.setObjectName("header")
        layout.addWidget(mem_hdr)

        self.memory_display = QTextEdit()
        self.memory_display.setReadOnly(True)
        self.memory_display.setPlaceholderText("No memories yet…")
        layout.addWidget(self.memory_display, 1)

        sep2 = self._separator()
        layout.addWidget(sep2)

        # Quick actions
        qa_hdr = QLabel("// QUICK ACTIONS")
        qa_hdr.setObjectName("header")
        layout.addWidget(qa_hdr)

        actions = [
            ("Screenshot + OCR", lambda: self._quick("Take a screenshot and extract the text from my screen")),
            ("System Status",    lambda: self._quick("What is the current system status?")),
            ("Clear Memory",     lambda: self._confirm_clear_memory()),
            ("List Plugins",     lambda: self._quick("List all loaded plugins")),
        ]
        for label, fn in actions:
            btn = QPushButton(label)
            btn.clicked.connect(fn)
            layout.addWidget(btn)

        btn_danger = QPushButton("Clear Chat")
        btn_danger.setObjectName("danger")
        btn_danger.clicked.connect(self._clear_chat)
        layout.addWidget(btn_danger)

        return panel

    def _build_input_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(56)
        bar.setStyleSheet("background: #08090B;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        prefix = QLabel(">_")
        prefix.setStyleSheet("color: #00FFB2; font-size: 16px; font-weight: bold;")
        layout.addWidget(prefix)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Command JARVIS…")
        self.input_field.returnPressed.connect(self._submit)
        layout.addWidget(self.input_field, 1)

        self.send_btn = QPushButton("SEND")
        self.send_btn.setFixedWidth(64)
        self.send_btn.clicked.connect(self._submit)
        layout.addWidget(self.send_btn)

        return bar

    def _build_statusbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(24)
        bar.setStyleSheet("background: #06070A; border-top: 1px solid #141820;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)

        self.status_label = QLabel("Initializing…")
        self.status_label.setObjectName("status")
        layout.addWidget(self.status_label)

        layout.addStretch()

        self.thinking_label = QLabel()
        self.thinking_label.setStyleSheet("color: #00FFB2; font-size: 12px;")
        layout.addWidget(self.thinking_label)

        return bar

    def _separator(self) -> QFrame:
        line = QFrame()
        line.setObjectName("separator")
        line.setFrameShape(QFrame.Shape.HLine)
        return line

    # ------------------------------------------------------------------ #
    #  Signal connections
    # ------------------------------------------------------------------ #

    def _connect_signals(self):
        a = self.assistant
        a.response_ready.connect(self._on_response)
        a.status_changed.connect(self._on_status)
        a.listening_changed.connect(self._on_listening)
        a.thinking_changed.connect(self._on_thinking)
        a.module_log.connect(self._on_module_log)
        a.memory_updated.connect(self._on_memory_updated)

        self._thinking_timer.timeout.connect(self._tick_thinking)

    # ------------------------------------------------------------------ #
    #  Slots
    # ------------------------------------------------------------------ #

    @pyqtSlot(str)
    def _on_response(self, text: str):
        self._append_chat("assistant", text)

    @pyqtSlot(str)
    def _on_status(self, text: str):
        self.status_label.setText(text)

    @pyqtSlot(bool)
    def _on_listening(self, active: bool):
        if active:
            self.lbl_listening.setStyleSheet("color: #00FFB2; font-size: 10px; letter-spacing: 2px;")
        else:
            self.lbl_listening.setStyleSheet("color: #1E3A2A; font-size: 10px; letter-spacing: 2px;")

    @pyqtSlot(bool)
    def _on_thinking(self, active: bool):
        if active:
            self._thinking_i = 0
            self._thinking_timer.start(120)
        else:
            self._thinking_timer.stop()
            self.thinking_label.setText("")
            self.send_btn.setEnabled(True)
            self.input_field.setEnabled(True)

        self.send_btn.setEnabled(not active)
        self.input_field.setEnabled(not active)

    def _tick_thinking(self):
        frame = self._thinking_frames[self._thinking_i % len(self._thinking_frames)]
        self.thinking_label.setText(f"{frame} processing")
        self._thinking_i += 1

    @pyqtSlot(str, str)
    def _on_module_log(self, module: str, msg: str):
        ts = time.strftime("%H:%M:%S")
        color_map = {
            "AI": "#00C8FF", "Voice": "#00FFB2", "Memory": "#FFB800",
            "Agents": "#FF8C00", "Vision": "#C85AFF", "Plugins": "#FF5A8C",
        }
        color = color_map.get(module, "#5A7A6A")
        html = (
            f'<span style="color:#3A5060;">[{ts}]</span> '
            f'<span style="color:{color};">[{module}]</span> '
            f'<span style="color:#8A9AAA;">{msg}</span>'
        )
        self.log_display.append(html)
        self.log_display.moveCursor(QTextCursor.MoveOperation.End)

    @pyqtSlot(list)
    def _on_memory_updated(self, entries: list):
        self.memory_display.clear()
        for entry in entries[:10]:
            role = entry.get("role", "?")
            content = entry.get("content", "")[:100]
            ts = entry.get("ts_human", "")
            color = "#00FFB2" if role == "assistant" else "#00C8FF"
            html = (
                f'<span style="color:{color};">[{role}]</span> '
                f'<span style="color:#5A7A6A; font-size:10px;">{ts}</span><br>'
                f'<span style="color:#8A9AAA;">{content}</span><br>'
            )
            self.memory_display.append(html)

    # ------------------------------------------------------------------ #
    #  Actions
    # ------------------------------------------------------------------ #

    def _submit(self):
        text = self.input_field.text().strip()
        if not text:
            return
        self.input_field.clear()
        self._history.append(text)
        self._history_idx = len(self._history)
        self._append_chat("user", text)
        self.assistant.process_command(text, source="text")

    def _append_chat(self, role: str, text: str):
        ts = time.strftime("%H:%M:%S")
        color_map = {
            "user":      ("#00C8FF", "YOU"),
            "assistant": ("#00FFB2", "JARVIS"),
            "system":    ("#FFB800", "SYS"),
        }
        color, label = color_map.get(role, ("#8A9AAA", role.upper()))
        html = (
            f'<div style="margin: 6px 0;">'
            f'<span style="color:{color}; font-weight:bold;">[{label}]</span> '
            f'<span style="color:#3A5060; font-size:10px;">{ts}</span><br>'
            f'<span style="color:#D0D8E0;">{text}</span>'
            f'</div>'
        )
        self.chat_display.append(html)
        self.chat_display.moveCursor(QTextCursor.MoveOperation.End)

    def _quick(self, cmd: str):
        self._append_chat("user", cmd)
        self.assistant.process_command(cmd, source="text")

    def _clear_chat(self):
        self.chat_display.clear()

    def _confirm_clear_memory(self):
        if self.assistant.memory_module:
            self.assistant.memory_module.delete_all()
            self._on_module_log("Memory", "Memory wiped by user")

    # ------------------------------------------------------------------ #
    #  Keyboard history navigation
    # ------------------------------------------------------------------ #

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Up and self._history:
            self._history_idx = max(0, self._history_idx - 1)
            self.input_field.setText(self._history[self._history_idx])
        elif event.key() == Qt.Key.Key_Down and self._history:
            self._history_idx = min(len(self._history), self._history_idx + 1)
            text = self._history[self._history_idx] if self._history_idx < len(self._history) else ""
            self.input_field.setText(text)
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------ #
    #  System tray
    # ------------------------------------------------------------------ #

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setToolTip("JARVIS")
        tray_menu = QMenu()
        show_action = QAction("Show JARVIS", self)
        show_action.triggered.connect(self.show)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit)
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show()
            self.raise_()
            self.activateWindow()

    def _quit(self):
        self.assistant.stop()
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    # ------------------------------------------------------------------ #
    #  Clock
    # ------------------------------------------------------------------ #

    def _start_clock(self):
        self._clock_timer = QTimer()
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

    def _update_clock(self):
        self.lbl_clock.setText(time.strftime("%H:%M:%S"))
