"""Colors and rounding for what the widget draws itself."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Tuple

from imgui_bundle import imgui

Color = Tuple[float, float, float, float]


def to_vec4(color) -> imgui.ImVec4:
    """Coerce an ``(r, g, b[, a])`` tuple (or an ImVec4) to ``imgui.ImVec4``."""
    if isinstance(color, imgui.ImVec4):
        return color
    r, g, b = color[:3]
    return imgui.ImVec4(r, g, b, color[3] if len(color) > 3 else 1.0)


@dataclass(frozen=True)
class Theme:
    """Palette, one ``(r, g, b, a)`` float tuple per role, plus the rounding knobs."""

    bg: Color = (0.11, 0.11, 0.12, 1.0)
    text: Color = (0.90, 0.90, 0.92, 1.0)
    text_dim: Color = (0.62, 0.62, 0.65, 1.0)
    accent: Color = (0.40, 0.68, 1.00, 1.0)
    border: Color = (0.35, 0.35, 0.37, 0.7)
    ok: Color = (0.40, 0.90, 0.40, 1.0)
    warn: Color = (1.00, 0.80, 0.20, 1.0)
    error: Color = (1.00, 0.40, 0.40, 1.0)
    danger: Color = (0.75, 0.15, 0.15, 0.8)
    danger_hover: Color = (0.90, 0.20, 0.20, 1.0)
    rounding: float = 6.0
    frame_rounding: float = 4.0

    @staticmethod
    def dark() -> "Theme":
        return Theme()

    @staticmethod
    def light() -> "Theme":
        return Theme(
            bg=(0.94, 0.94, 0.95, 1.0),
            text=(0.10, 0.10, 0.12, 1.0),
            text_dim=(0.42, 0.42, 0.46, 1.0),
            accent=(0.10, 0.45, 0.80, 1.0),
            border=(0.70, 0.70, 0.74, 0.9),
            ok=(0.10, 0.55, 0.15, 1.0),
            warn=(0.70, 0.45, 0.00, 1.0),
            error=(0.75, 0.15, 0.15, 1.0),
        )

    def replace(self, **changes) -> "Theme":
        """A copy with the given fields overridden."""
        return replace(self, **changes)
