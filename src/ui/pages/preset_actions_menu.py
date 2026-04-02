from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QEvent, QEventLoop, QObject, QPoint, Qt
from PyQt6.QtGui import QAction, QCursor
from PyQt6.QtWidgets import QApplication, QMenu, QWidget


class _RoundMenuLifecycleFilter(QObject):
    """Closes the floating menu when the owner window loses focus or hides."""

    def __init__(self, menu: QWidget, owner_window: QWidget | None, on_close: Callable[[], None]) -> None:
        super().__init__(menu)
        self._menu = menu
        self._owner_window = owner_window
        self._on_close = on_close

    def eventFilter(self, obj, event):  # noqa: N802 (Qt override)
        event_type = event.type()

        if obj is self._menu and event_type in (QEvent.Type.Hide, QEvent.Type.Close):
            self._on_close()
            return False

        if obj is self._owner_window and event_type in (
            QEvent.Type.Hide,
            QEvent.Type.Close,
            QEvent.Type.WindowDeactivate,
        ):
            self._on_close()
            return False

        return super().eventFilter(obj, event)


def _exec_round_menu(menu: QWidget, pos: QPoint, *, owner: QWidget | None) -> QAction | None:
    """Waits for fluent menu selection because RoundMenu.exec() returns immediately."""

    chosen_action: dict[str, QAction | None] = {"value": None}
    finished = {"value": False}
    loop = QEventLoop(menu)

    def _finish(action: QAction | None = None) -> None:
        if action is not None and chosen_action["value"] is None:
            chosen_action["value"] = action
        if finished["value"]:
            return
        finished["value"] = True
        try:
            menu.hide()
        except Exception:
            pass
        if loop.isRunning():
            loop.quit()

    owner_window = owner.window() if owner is not None else None
    lifecycle_filter = _RoundMenuLifecycleFilter(menu, owner_window, on_close=_finish)
    menu.installEventFilter(lifecycle_filter)
    if owner_window is not None and owner_window is not menu:
        owner_window.installEventFilter(lifecycle_filter)

    app = QApplication.instance()
    state_handler = None
    if app is not None:
        def _on_app_state_changed(state) -> None:
            if state != Qt.ApplicationState.ApplicationActive:
                _finish()

        state_handler = _on_app_state_changed
        app.applicationStateChanged.connect(state_handler)

    for action in menu.actions():
        try:
            action.triggered.connect(lambda _checked=False, action=action: _finish(action))
        except Exception:
            pass

    try:
        menu.exec(pos)
        if not finished["value"] and menu.isVisible():
            loop.exec()
    finally:
        try:
            menu.removeEventFilter(lifecycle_filter)
        except Exception:
            pass
        if owner_window is not None and owner_window is not menu:
            try:
                owner_window.removeEventFilter(lifecycle_filter)
            except Exception:
                pass
        if app is not None and state_handler is not None:
            try:
                app.applicationStateChanged.disconnect(state_handler)
            except Exception:
                pass

    return chosen_action["value"]


def show_preset_actions_menu(
    parent: QWidget,
    *,
    global_pos: QPoint | None,
    is_builtin: bool,
    labels: dict[str, str],
    make_menu_action: Callable[..., QAction],
    icon_resolver: Callable[[str], object | None],
    round_menu_cls=None,
) -> str | None:
    """Show shared preset actions menu and return chosen action key."""

    action_specs = [
        ("open", "VIEW"),
        ("rating", "FAVORITE"),
        ("move_up", "UP"),
        ("move_down", "DOWN"),
        ("rename", "RENAME"),
        ("duplicate", "COPY"),
        ("export", "SHARE"),
        ("reset", "SYNC"),
        ("delete", "DELETE"),
    ]

    def _create_action(menu, key: str) -> QAction:
        return make_menu_action(
            labels[key],
            icon=icon_resolver(action_specs_map[key]),
            parent=menu,
        )

    action_specs_map = {key: icon_name for key, icon_name in action_specs}
    action_order = ["open", "rating", "move_up", "move_down", "duplicate", "export", "reset"]
    if not is_builtin:
        action_order.insert(4, "rename")
        action_order.append("delete")

    if round_menu_cls is not None:
        menu = round_menu_cls(parent=parent)
        action_map: dict[QAction, str] = {}
        for key in action_order:
            action = _create_action(menu, key)
            menu.addAction(action)
            action_map[action] = key
        chosen = _exec_round_menu(menu, global_pos or QCursor.pos(), owner=parent)
        return action_map.get(chosen)

    menu = QMenu(parent)
    action_map = {menu.addAction(labels[key]): key for key in action_order}
    chosen = menu.exec(global_pos or QCursor.pos())
    return action_map.get(chosen)
