"""The small imgui helpers the panel is drawn with."""

from __future__ import annotations

import os
import shutil
import sys

from imgui_bundle import imgui

from imgui_notebooks.theme import Theme, to_vec4

DEFAULT_THEME = Theme.dark()


def native_dialogs_available() -> bool:
    """Whether a file dialog can appear where this process runs: always on Windows and macOS, on Linux with a display and a helper portable-file-dialogs can shell out to."""
    if sys.platform in ("win32", "darwin"):
        return True
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return False
    return any(shutil.which(name) for name in ("zenity", "matedialog", "qarma", "kdialog"))


NATIVE_DIALOGS = native_dialogs_available()


def em(x: float = 1.0) -> float:
    """``x`` font heights in pixels; only valid inside a frame."""
    return imgui.get_font_size() * x


def section(title: str, theme: Theme = DEFAULT_THEME) -> None:
    """An accent heading with a rule under it."""
    imgui.dummy(imgui.ImVec2(0, em(0.3)))
    imgui.text_colored(to_vec4(theme.accent), title)
    imgui.separator()
    imgui.dummy(imgui.ImVec2(0, em(0.2)))


def help_mark(text: str) -> None:
    """A dim ``(?)`` after the last item, with ``text`` as its tooltip."""
    imgui.same_line(0, em(0.3))
    imgui.text_disabled("(?)")
    if imgui.is_item_hovered():
        imgui.set_tooltip(text)


def tooltip(text: str) -> None:
    """``text`` as the tooltip of the last item, disabled or not."""
    if text and imgui.is_item_hovered(imgui.HoveredFlags_.allow_when_disabled):
        imgui.set_tooltip(text)


def popup(title: str, is_open: bool, theme: Theme = DEFAULT_THEME) -> tuple[bool, bool]:
    """Begin a centered, auto-sized, closable window with an opaque background.

    Returns ``(draw_contents, still_open)``; call ``imgui.end()`` either way.
    """
    imgui.set_next_window_pos(imgui.get_main_viewport().get_center(), imgui.Cond_.appearing, pivot=imgui.ImVec2(0.5, 0.5))
    imgui.push_style_var(imgui.StyleVar_.window_rounding, theme.rounding)
    imgui.push_style_var(imgui.StyleVar_.window_padding, imgui.ImVec2(em(1.0), em(0.8)))
    background = imgui.get_style().color_(imgui.Col_.window_bg)
    imgui.push_style_color(imgui.Col_.window_bg, imgui.ImVec4(background.x, background.y, background.z, 1.0))
    opened, is_open = imgui.begin(
        f"{title}###{title}",
        is_open,
        flags=imgui.WindowFlags_.no_saved_settings | imgui.WindowFlags_.always_auto_resize,
    )
    imgui.pop_style_color()
    imgui.pop_style_var(2)
    return opened, is_open


def danger_button(label: str, theme: Theme = DEFAULT_THEME) -> bool:
    """A button in the danger colors, for stop and remove."""
    imgui.push_style_color(imgui.Col_.button, to_vec4(theme.danger))
    imgui.push_style_color(imgui.Col_.button_hovered, to_vec4(theme.danger_hover))
    imgui.push_style_color(imgui.Col_.button_active, to_vec4(theme.danger_hover))
    clicked = imgui.small_button(label)
    imgui.pop_style_color(3)
    return clicked
