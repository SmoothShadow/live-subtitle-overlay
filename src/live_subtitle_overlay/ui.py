from __future__ import annotations

from dataclasses import dataclass
import logging
import sys

from .config import UiConfig
from .models import SubtitleLine
from .settings import OverlayState


logger = logging.getLogger(__name__)
_WINDOWS_TOGGLE_HOTKEY = "Ctrl+Shift+H"


@dataclass(slots=True)
class _DragState:
    active: bool = False
    offset_x: int = 0
    offset_y: int = 0


class SubtitleWindow:
    def __init__(
        self,
        config: UiConfig,
        initial_state: OverlayState | None = None,
        on_state_changed=None,
    ) -> None:
        from PySide6.QtCore import QObject, QPoint, Qt, Signal, QTimer
        from PySide6.QtGui import QColor, QFont
        from PySide6.QtGui import QKeySequence, QShortcut
        from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

        class _Bridge(QObject):
            subtitle_changed = Signal(object)
            status_changed = Signal(str)

        self._Qt = Qt
        self._QPoint = QPoint
        self._drag = _DragState()
        self._initial_state = initial_state or OverlayState(
            width=config.width,
            height=config.height,
            show_source_text=config.show_source_text,
        )
        self._loopback_device_index = self._initial_state.loopback_device_index
        self._locked = self._initial_state.locked
        self._paused = False
        self._pause_handler = None
        self._visibility_hotkey_registered = False
        self._native_event_filter = None
        self._on_state_changed = on_state_changed or (lambda _state: None)
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
        self._window.resize(self._initial_state.width, self._initial_state.height)
        self._window.move(self._initial_state.x, self._initial_state.y)
        self._clear_timer = QTimer(self._window)
        self._clear_timer.setSingleShot(True)
        self._clear_timer.setInterval(int(config.subtitle_timeout_seconds * 1000))
        self._clear_timer.timeout.connect(self._clear_subtitle)

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
        self._source_label.setVisible(self._initial_state.show_source_text)

        self._status_label = QLabel("Listening")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._status_label.setFont(QFont("Segoe UI", pointSize=10))
        self._status_label.setStyleSheet("color: #b6b8ab;")

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(8)

        self._pause_button = QToolButton()
        self._pause_button.setText("Pause")
        self._pause_button.setEnabled(False)
        self._pause_button.clicked.connect(self.toggle_pause)

        self._source_button = QToolButton()
        self._source_button.setText("Source")
        self._source_button.clicked.connect(self.toggle_source_text)

        self._lock_button = QToolButton()
        self._lock_button.setText("Lock")
        self._lock_button.clicked.connect(self.toggle_locked)
        self._lock_button.setCheckable(True)
        self._lock_button.setChecked(self._locked)

        button_style = """
            QToolButton {
                color: #f7f4e8;
                background-color: rgba(255, 255, 255, 18);
                border: 1px solid rgba(255, 255, 255, 28);
                border-radius: 10px;
                padding: 5px 10px;
            }
            QToolButton:disabled {
                color: #818374;
            }
        """
        self._pause_button.setStyleSheet(button_style)
        self._source_button.setStyleSheet(button_style)
        self._lock_button.setStyleSheet(button_style)

        controls.addWidget(self._pause_button)
        controls.addWidget(self._source_button)
        controls.addWidget(self._lock_button)
        controls.addStretch(1)
        controls.addWidget(self._status_label)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(8)
        layout.addWidget(self._subtitle_label)
        layout.addWidget(self._source_label)
        layout.addLayout(controls)

        outer = QVBoxLayout(self._window)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(container)

        self._bridge.subtitle_changed.connect(self._apply_subtitle)
        self._bridge.status_changed.connect(self._apply_status)
        self._window.mousePressEvent = self._mouse_press_event
        self._window.mouseMoveEvent = self._mouse_move_event
        self._window.mouseReleaseEvent = self._mouse_release_event
        self._toggle_lock_shortcut = QShortcut(QKeySequence("Ctrl+Shift+L"), self._window)
        self._toggle_lock_shortcut.activated.connect(self.toggle_locked)
        self._toggle_source_shortcut = QShortcut(QKeySequence("Ctrl+Shift+T"), self._window)
        self._toggle_source_shortcut.activated.connect(self.toggle_source_text)
        self._toggle_pause_shortcut = QShortcut(QKeySequence("Ctrl+Shift+S"), self._window)
        self._toggle_pause_shortcut.activated.connect(self.toggle_pause)
        self._setup_global_visibility_hotkey()

        self.set_status("Ready")

    def show(self) -> None:
        self._window.show()

    def close(self) -> None:
        self._teardown_global_visibility_hotkey()
        self._window.close()

    def set_pause_handler(self, handler) -> None:
        self._pause_handler = handler
        self._pause_button.setEnabled(handler is not None)

    def post_subtitle(self, subtitle: SubtitleLine) -> None:
        self._bridge.subtitle_changed.emit(subtitle)

    def set_status(self, status: str) -> None:
        self._bridge.status_changed.emit(status)

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        self._pause_button.setText("Resume" if paused else "Pause")
        self._apply_status("Paused" if paused else "Listening")

    def show_message(self, text: str, source_text: str = "", *, auto_clear: bool = False) -> None:
        self._clear_timer.stop()
        self._subtitle_label.setText(text or " ")
        self._source_label.setText(source_text)
        if auto_clear:
            self._clear_timer.start()

    def _apply_subtitle(self, subtitle: SubtitleLine) -> None:
        self._subtitle_label.setText(subtitle.text or " ")
        self._source_label.setText(subtitle.source_text or "")
        self._clear_timer.start()

    def _apply_status(self, status: str) -> None:
        suffix = "Locked" if self._locked else "Drag"
        pause_text = "Resume" if self._paused else "Pause"
        parts = [
            status,
            f"Ctrl+Shift+S {pause_text}",
            f"Ctrl+Shift+L {suffix}",
            "Ctrl+Shift+T Source",
        ]
        if self._visibility_hotkey_registered:
            parts.append(f"{_WINDOWS_TOGGLE_HOTKEY} Show/Hide")
        self._status_label.setText(" | ".join(parts))

    def toggle_pause(self) -> None:
        if self._pause_handler is None:
            return
        self._paused = bool(self._pause_handler())
        self._pause_button.setText("Resume" if self._paused else "Pause")
        self._apply_status("Paused" if self._paused else "Listening")

    def toggle_locked(self) -> None:
        self._locked = not self._locked
        self._lock_button.setChecked(self._locked)
        self._apply_status("Ready")
        self._persist_state()

    def toggle_source_text(self) -> None:
        self._source_label.setVisible(not self._source_label.isVisible())
        self._apply_status("Ready")
        self._persist_state()

    def _mouse_press_event(self, event) -> None:
        if self._locked:
            return
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
        if self._locked:
            return
        if not self._drag.active:
            return
        position = event.globalPosition().toPoint()
        self._window.move(
            self._QPoint(position.x() - self._drag.offset_x, position.y() - self._drag.offset_y)
        )

    def _mouse_release_event(self, event) -> None:
        del event
        self._drag.active = False
        self._persist_state()

    def _clear_subtitle(self) -> None:
        self._subtitle_label.setText(" ")
        self._source_label.setText("")
        self._apply_status("Listening")

    def _persist_state(self) -> None:
        self._on_state_changed(
            OverlayState(
                x=self._window.x(),
                y=self._window.y(),
                width=self._window.width(),
                height=self._window.height(),
                locked=self._locked,
                show_source_text=self._source_label.isVisible(),
                loopback_device_index=self._loopback_device_index,
            )
        )

    def toggle_visibility(self) -> None:
        if self._window.isVisible():
            self._window.hide()
            return
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()
        self._apply_status("Paused" if self._paused else "Ready")

    def _setup_global_visibility_hotkey(self) -> None:
        if sys.platform != "win32":
            return

        import ctypes
        from ctypes import wintypes

        from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication

        hotkey_id = 1
        mod_control = 0x0002
        mod_shift = 0x0004
        vk_h = 0x48
        wm_hotkey = 0x0312

        user32 = ctypes.windll.user32

        class _HotkeyFilter(QAbstractNativeEventFilter):
            def __init__(self, callback) -> None:
                super().__init__()
                self._callback = callback

            def nativeEventFilter(self, event_type, message):
                if event_type not in {b"windows_generic_MSG", "windows_generic_MSG"}:
                    return False, 0
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == wm_hotkey and int(msg.wParam) == hotkey_id:
                    self._callback()
                    return True, 0
                return False, 0

        if not user32.RegisterHotKey(None, hotkey_id, mod_control | mod_shift, vk_h):
            logger.warning("Unable to register global visibility hotkey %s", _WINDOWS_TOGGLE_HOTKEY)
            return

        self._native_event_filter = _HotkeyFilter(self.toggle_visibility)
        QCoreApplication.instance().installNativeEventFilter(self._native_event_filter)
        self._visibility_hotkey_registered = True

    def _teardown_global_visibility_hotkey(self) -> None:
        if not self._visibility_hotkey_registered or sys.platform != "win32":
            return

        import ctypes

        from PySide6.QtCore import QCoreApplication

        ctypes.windll.user32.UnregisterHotKey(None, 1)
        if self._native_event_filter is not None:
            QCoreApplication.instance().removeNativeEventFilter(self._native_event_filter)
        self._native_event_filter = None
        self._visibility_hotkey_registered = False


def choose_loopback_device(devices: list[dict], selected_index: int | None = None) -> int | None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QListWidget, QListWidgetItem, QVBoxLayout

    dialog = QDialog()
    dialog.setWindowTitle("Choose Loopback Device")
    dialog.resize(760, 420)

    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel("Select the WASAPI loopback device to use for subtitle capture."))

    device_list = QListWidget(dialog)
    for device in devices:
        default_marker = " | default output" if device.get("is_default_output") else ""
        item = QListWidgetItem(
            f'[{device["index"]}] {device["name"]} | channels={device["channels"]} | '
            f'sample_rate={device["sample_rate"]}{default_marker}'
        )
        item.setData(Qt.ItemDataRole.UserRole, int(device["index"]))
        device_list.addItem(item)
        if selected_index is not None and int(device["index"]) == int(selected_index):
            device_list.setCurrentItem(item)
    if device_list.currentItem() is None and device_list.count() > 0:
        device_list.setCurrentRow(0)
    layout.addWidget(device_list)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    if dialog.exec() != int(QDialog.DialogCode.Accepted):
        return None
    current_item = device_list.currentItem()
    if current_item is None:
        return None
    return int(current_item.data(Qt.ItemDataRole.UserRole))
