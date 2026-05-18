"""
JARVIS Overlay HUD
Transparent, always-on-top smart overlay widget.
Shows current AI status, recent response, and quick info.
"""

import time
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QPoint
from PyQt6.QtGui import QPainter, QColor, QFont, QMouseEvent

from core.config import Config


class OverlayHUD(QWidget):
    """
    Frameless, click-through transparent overlay.
    Sits in the corner of the screen showing JARVIS status.
    Drag it to reposition.
    """

    def __init__(self, assistant, config: Config):
        super().__init__()
        self.assistant = assistant
        self.config = config
        self._drag_pos: QPoint | None = None
        self._fade_timer = QTimer()
        self._message_timer = QTimer()

        self._setup_window()
        self._setup_ui()
        self._connect_signals()
        self._position_overlay()

        self._pulse_timer = QTimer()
        self._pulse_timer.timeout.connect(self._pulse)
        self._pulse_timer.start(1500)
        self._pulse_state = True

    # ------------------------------------------------------------------ #
    #  Setup
    # ------------------------------------------------------------------ #

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedWidth(320)
        self.setMinimumHeight(80)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        # Header row
        header_row = QHBoxLayout()
        header_row.setSpacing(6)

        self.dot = QLabel("◉")
        self.dot.setStyleSheet("color: #00FFB2; font-size: 10px;")
        header_row.addWidget(self.dot)

        self.lbl_title = QLabel("J·A·R·V·I·S")
        self.lbl_title.setStyleSheet(
            "color: #00FFB2; font-family: 'JetBrains Mono', monospace; "
            "font-size: 11px; letter-spacing: 3px; font-weight: bold;"
        )
        header_row.addWidget(self.lbl_title)
        header_row.addStretch()

        self.lbl_time = QLabel()
        self.lbl_time.setStyleSheet(
            "color: #2A4A3A; font-family: 'JetBrains Mono', monospace; font-size: 10px;"
        )
        header_row.addWidget(self.lbl_time)
        layout.addLayout(header_row)

        # Status
        self.lbl_status = QLabel("Initializing…")
        self.lbl_status.setStyleSheet(
            "color: #3A6A5A; font-family: 'JetBrains Mono', monospace; font-size: 10px;"
        )
        layout.addWidget(self.lbl_status)

        # Message
        self.lbl_message = QLabel("")
        self.lbl_message.setWordWrap(True)
        self.lbl_message.setStyleSheet(
            "color: #8ABAA0; font-family: 'JetBrains Mono', monospace; "
            "font-size: 11px; line-height: 1.4; margin-top: 4px;"
        )
        self.lbl_message.setMaximumWidth(290)
        layout.addWidget(self.lbl_message)

        # Clock timer
        self._clock_timer = QTimer()
        self._clock_timer.timeout.connect(self._update_time)
        self._clock_timer.start(1000)
        self._update_time()

        # Auto-fade message after 8s
        self._message_timer.setSingleShot(True)
        self._message_timer.timeout.connect(self._clear_message)

    def _position_overlay(self):
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        pos = self.config.ui.overlay_position

        margin = 20
        if "right" in pos:
            x = screen.width() - self.width() - margin
        else:
            x = margin

        if "bottom" in pos:
            y = screen.height() - 200 - margin
        else:
            y = margin

        self.move(x, y)

    def _connect_signals(self):
        self.assistant.status_changed.connect(self._on_status)
        self.assistant.overlay_message.connect(self._on_message)
        self.assistant.thinking_changed.connect(self._on_thinking)
        self.assistant.listening_changed.connect(self._on_listening)

    # ------------------------------------------------------------------ #
    #  Paint
    # ------------------------------------------------------------------ #

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        bg = QColor(8, 12, 10)
        bg.setAlpha(int(self.config.ui.overlay_opacity * 255))
        painter.setBrush(bg)
        painter.setPen(QColor(0, 255, 178, 60))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)

        # Top accent line
        painter.setPen(QColor(0, 255, 178, 180))
        painter.drawLine(14, 1, self.width() - 14, 1)

    # ------------------------------------------------------------------ #
    #  Slots
    # ------------------------------------------------------------------ #

    @pyqtSlot(str)
    def _on_status(self, text: str):
        self.lbl_status.setText(f"▸ {text}")
        self.adjustSize()

    @pyqtSlot(str)
    def _on_message(self, text: str):
        self.lbl_message.setText(text)
        self.adjustSize()
        self._message_timer.start(8000)

    @pyqtSlot(bool)
    def _on_thinking(self, active: bool):
        if active:
            self.lbl_status.setStyleSheet(
                "color: #00FFB2; font-family: 'JetBrains Mono', monospace; font-size: 10px;"
            )
        else:
            self.lbl_status.setStyleSheet(
                "color: #3A6A5A; font-family: 'JetBrains Mono', monospace; font-size: 10px;"
            )

    @pyqtSlot(bool)
    def _on_listening(self, active: bool):
        if active:
            self.dot.setStyleSheet("color: #00C8FF; font-size: 10px;")
        else:
            self.dot.setStyleSheet("color: #00FFB2; font-size: 10px;")

    def _clear_message(self):
        self.lbl_message.setText("")
        self.adjustSize()

    def _update_time(self):
        self.lbl_time.setText(time.strftime("%H:%M"))

    def _pulse(self):
        self._pulse_state = not self._pulse_state
        alpha = "ff" if self._pulse_state else "66"
        self.dot.setStyleSheet(f"color: #00FFB2{alpha}; font-size: 10px;")

    # ------------------------------------------------------------------ #
    #  Drag to reposition
    # ------------------------------------------------------------------ #

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None
