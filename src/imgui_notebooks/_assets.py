"""Per-user paths and icon-font resolution."""

from __future__ import annotations

import os
from pathlib import Path

ICON_FONT = "fonts/Font_Awesome_6_Free-Solid-900.otf"


def data_dir() -> Path:
    """The per-user directory everything here writes to, created on first use.

    ``~/.imgui_notebooks`` by default; the ``IMGUI_NOTEBOOKS_HOME`` env var overrides it.
    """
    base = os.environ.get("IMGUI_NOTEBOOKS_HOME")
    directory = Path(base) if base else Path.home() / ".imgui_notebooks"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def default_ini_path(name: str = "notebooks") -> str:
    """Absolute path for hello_imgui's window-layout ``.ini``."""
    return str(data_dir() / f"{name}.ini")


def ensure_assets(assets_folder: str | None = None) -> None:
    """Make sure hello_imgui can resolve the FontAwesome icon font.

    ``assets_folder`` becomes *the* assets folder when given. Otherwise a host app's working
    configuration is left alone: ``<data dir>/assets`` (if present) and imgui-bundle's own assets
    are only added as search paths when the font does not already resolve.
    """
    from imgui_bundle import hello_imgui

    if assets_folder:
        hello_imgui.set_assets_folder(str(assets_folder))
        return
    if hello_imgui.asset_exists(ICON_FONT):
        return
    user = data_dir() / "assets"
    if user.is_dir():
        hello_imgui.add_assets_search_path(str(user))
        if hello_imgui.asset_exists(ICON_FONT):
            return
    import imgui_bundle

    bundled = Path(imgui_bundle.__file__).parent / "assets"
    if bundled.is_dir():
        hello_imgui.add_assets_search_path(str(bundled))
