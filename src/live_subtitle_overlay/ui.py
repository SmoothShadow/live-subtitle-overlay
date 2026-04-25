from __future__ import annotations

from dataclasses import dataclass

from .config import UiConfig
from .models import SubtitleLine


@dataclass(slots=True)
class _DragState:
    active: bool = False
    offset_x: int = 0
    offset_y: int = 0


class SubtitleWindow:
    def __init__(self, config: UiConfig) -> None:
        from PySide6.QtCore import QObject, QPoint, Qt, Signal
        from PySide6.QtGui import QColor, QFont
        from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

        class _Bridge(QObject):
            subtitle_changed = Signal(object)

        self._Qt = Qt
        self._QPoint = QPoint
        self._drag = _DragState()
        self._bridge = _Bridge()
        self._window = QWidget()
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self._window.setWindowFlags(flags)
        self._window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._window.setWindowOpacity(config.opacity)
        self._window.resize(config.width, config.height)
        self._window.move(120, 780)

        container = QWidget(self._window)
        container.setObjectName("container")
        container.setStyleSheet(
            """
            QWidget#container {
                background-color: rgba(12, 12, 12, 190);
                border: 1px solid rgba(255, 255, 255, 32);
                border-radius: 18px;
            }
            QLabel {
                color: #f7f4e8;
                background: transparent;
            }
            """
        )

        self._subtitle_label = QLabel("字幕待命中")
        self._subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle_label.setWordWrap(True)
        subtitle_font = QFont("Microsoft YaHei UI", pointSize=config.font_size, weight=700)
        self._subtitle_label.setFont(subtitle_font)
        self._subtitle_label.setMinimumHeight(config.height - 54)

        self._source_label = QLabel("")
        self._source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._source_label.setWordWrap(True)
        source_font = QFont("Segoe UI", pointSize=max(11, config.font_size // 2))
        self._source_label.setFont(source_font)
        source_color = QColor("#d9dcc8")
        self._source_label.setStyleSheet(f"color: {source_color.name()};")
        self._source_label.setVisible(config.show_source_text)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(10)
        layout.addWidget(self._subtitle_label)
        layout.addWidget(self._source_label)

        outer = QVBoxLayout(self._window)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(container)

        self._bridge.subtitle_changed.connect(self._apply_subtitle)
        self._window.mousePressEvent = self._mouse_press_event
        self._window.mouseMoveEvent = self._mouse_move_event
        self._window.mouseReleaseEvent = self._mouse_release_event

    def show(self) -> None:
        self._window.show()

    def close(self) -> None:
        self._window.close()

    def post_subtitle(self, subtitle: SubtitleLine) -> None:
        self._bridge.subtitle_changed.emit(subtitle)

    def _apply_subtitle(self, subtitle: SubtitleLine) -> None:
        self._subtitle_label.setText(subtitle.text or " ")
        self._source_label.setText(subtitle.source_text or "")

    def _mouse_press_event(self, event) -> None:
        if event.button() != self._Qt.MouseButton.LeftButton:
            return
        position = event.globalPosition().toPoint()
        top_left = self._window.frameGeometry().topLeft()
        self._drag = _DragState(
            active=True,
            offset_x=position.x() - top_left.x(),
            offset_y=position.y() - top_left.y(),
        )

    def _mouse_move_event(self, event) -> None:
        if not self._drag.active:
            return
        position = event.globalPosition().toPoint()
        self._window.move(
            self._QPoint(position.x() - self._drag.offset_x, position.y() - self._drag.offset_y)
        )

    def _mouse_release_event(self, event) -> None:
        del event
        self._drag.active = False
