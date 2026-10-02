"""imgui_notebooks: an "Open Notebook" menu for imgui-bundle apps.

Quick start
-----------
>>> from imgui_notebooks import FolderSource, NotebookMenu, NotebookMenuConfig
>>> menu = NotebookMenu(NotebookMenuConfig(sources=[FolderSource("~/notebooks")]))
>>> # in your menu bar, or inside your File menu:
>>> menu.draw_menu()                  # doctest: +SKIP
>>> # once per frame:
>>> menu.render_window()              # doctest: +SKIP

With no host app at all:
>>> from imgui_notebooks import run_notebooks
>>> run_notebooks()                   # doctest: +SKIP
"""

from __future__ import annotations

from imgui_notebooks._assets import data_dir, default_ini_path, ensure_assets
from imgui_notebooks.commands import BACKENDS, Backend, server_command, server_url
from imgui_notebooks.model import JUPYTER, MARIMO, Host, Notebook, detect_backend
from imgui_notebooks.notebooks import NotebookMenu, NotebookMenuConfig
from imgui_notebooks.panel import Hotkey, Panel, PanelConfig
from imgui_notebooks.runner import main, run_notebooks
from imgui_notebooks.server import FAILED, INSTALLING, RUNNING, STARTING, STOPPED, Launcher, Server
from imgui_notebooks.sources import CallableSource, FolderSource, ListSource, Source, scan
from imgui_notebooks.store import Store
from imgui_notebooks.theme import Theme, to_vec4

__version__ = "0.1.0"

__all__ = [
    "NotebookMenu",
    "NotebookMenuConfig",
    "Notebook",
    "Host",
    "FolderSource",
    "ListSource",
    "CallableSource",
    "Source",
    "scan",
    "Launcher",
    "Server",
    "STARTING",
    "INSTALLING",
    "RUNNING",
    "STOPPED",
    "FAILED",
    "Store",
    "BACKENDS",
    "Backend",
    "JUPYTER",
    "MARIMO",
    "detect_backend",
    "server_command",
    "server_url",
    "run_notebooks",
    "main",
    "Panel",
    "PanelConfig",
    "Hotkey",
    "Theme",
    "to_vec4",
    "ensure_assets",
    "data_dir",
    "default_ini_path",
    "__version__",
]
