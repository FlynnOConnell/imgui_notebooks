"""The surface a host app wires in: visibility, a menu entry and a window of its own.

The same shape as the panels in ``imgui_debugger``, kept here so this package depends on nothing but
imgui-bundle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

from imgui_bundle import imgui

from imgui_notebooks.theme import Theme


@dataclass(frozen=True)
class Hotkey:
    """A key plus modifiers that toggles a panel, and its own menu text."""

    key: object
    ctrl: bool = False
    shift: bool = False
    alt: bool = False

    @property
    def text(self) -> str:
        parts = []
        if self.ctrl:
            parts.append("Ctrl")
        if self.shift:
            parts.append("Shift")
        if self.alt:
            parts.append("Alt")
        parts.append(imgui.get_key_name(self.key))
        return "+".join(parts)

    def pressed(self) -> bool:
        """True on the frame the combination is pressed, inside a live frame."""
        io = imgui.get_io()
        if io.key_ctrl != self.ctrl or io.key_shift != self.shift or io.key_alt != self.alt:
            return False
        return imgui.is_key_pressed(self.key)


@dataclass
class PanelConfig:
    """Window, menu and theme settings.

    Parameters
    ----------
    title : str
        Window title and default menu label.
    visible : bool
        Whether the panel starts open.
    window_id : str
        Stable imgui id suffix, so a renamed title keeps its saved layout; the class name when empty.
    window_size : tuple[int, int]
        First-use size; ``(0, 0)`` lets imgui size it to the content.
    window_pos : tuple[int, int] | None
        First-use position; imgui decides when None.
    window_flags : int
        ``imgui.WindowFlags_`` bits for the panel's own window.
    closable : bool
        Draw the close button and clear ``visible`` with it.
    shortcut : str
        Menu shortcut text; the hotkey's text when empty.
    hotkey : Hotkey | None
        Key combination that toggles the panel.
    theme : Theme
        Palette for what the panel draws itself.
    """

    title: str = "Panel"
    visible: bool = True
    window_id: str = ""
    window_size: Tuple[int, int] = (0, 0)
    window_pos: Optional[Tuple[int, int]] = None
    window_flags: int = 0
    closable: bool = True
    shortcut: str = ""
    hotkey: Optional[Hotkey] = None
    theme: Theme = field(default_factory=Theme.dark)


class Panel:
    """Base for the widget: visibility, a menu entry and its own window. Subclasses implement ``render``."""

    config_class = PanelConfig

    def __init__(self, config: Optional[PanelConfig] = None):
        self.config = config or self.config_class()
        self.visible = self.config.visible

    @property
    def title(self) -> str:
        return self.config.title

    @property
    def theme(self) -> Theme:
        return self.config.theme

    @property
    def window_id(self) -> str:
        """The full imgui window label: the title plus a stable id suffix."""
        ident = self.config.window_id or type(self).__name__
        return f"{self.config.title}##imgui_notebooks_{ident}"

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False

    def toggle(self) -> None:
        self.visible = not self.visible

    def menu_item(self, label: str = "", shortcut: str = "") -> bool:
        """A checked menu entry bound to ``visible``, inside a menu you already opened. True when clicked."""
        text = shortcut or self.config.shortcut
        if not text and self.config.hotkey is not None:
            text = self.config.hotkey.text
        clicked, self.visible = imgui.menu_item(label or self.config.title, text, self.visible)
        return clicked

    def poll_hotkey(self) -> bool:
        """Toggle the panel when its hotkey is pressed; called every frame by ``render_window``."""
        if self.config.hotkey is None or not self.config.hotkey.pressed():
            return False
        self.toggle()
        return True

    def render(self) -> None:
        """Draw the body at the current cursor, with no window around it."""
        raise NotImplementedError(f"{type(self).__name__} does not implement render()")

    def render_window(self, flags: int = 0) -> bool:
        """Draw the body in its own window, honoring ``visible``. True when the body was drawn."""
        self.poll_hotkey()
        if not self.visible:
            return False
        cfg = self.config
        if cfg.window_size and any(cfg.window_size):
            imgui.set_next_window_size(imgui.ImVec2(*cfg.window_size), imgui.Cond_.first_use_ever)
        if cfg.window_pos is not None:
            imgui.set_next_window_pos(imgui.ImVec2(*cfg.window_pos), imgui.Cond_.first_use_ever)
        expanded, opened = imgui.begin(self.window_id, True if cfg.closable else None, cfg.window_flags | flags)
        if cfg.closable and opened is not None:
            self.visible = opened
        if expanded:
            self.render()
        imgui.end()
        return expanded
