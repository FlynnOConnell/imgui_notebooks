"""One-shot harness and the ``imgui-notebooks`` command: the panel in a window of its own."""

from __future__ import annotations

import argparse
import os
from typing import Optional

from imgui_notebooks._assets import default_ini_path, ensure_assets
from imgui_notebooks.model import Host
from imgui_notebooks.notebooks import NotebookMenu, NotebookMenuConfig
from imgui_notebooks.sources import FolderSource
from imgui_notebooks.theme import to_vec4


def run_notebooks(config: Optional[NotebookMenuConfig] = None, runner_params=None) -> NotebookMenu:
    """Show the panel in its own OS window, blocking until it is closed; every server is stopped on the way out.

    Parameters
    ----------
    config : NotebookMenuConfig | None
        Sources and behavior.
    runner_params : hello_imgui.RunnerParams | None
        Your own params, e.g. a null backend for a headless test. Title, size and ``.ini`` are filled in only when unset.
    """
    from imgui_bundle import hello_imgui, immapp

    cfg = config or NotebookMenuConfig()
    ensure_assets()
    menu = NotebookMenu(cfg)
    params = runner_params if runner_params is not None else hello_imgui.RunnerParams()
    params.app_window_params.window_title = cfg.title
    params.app_window_params.window_geometry.size = tuple(cfg.window_size)
    params.app_window_params.window_geometry.size_auto = False
    params.imgui_window_params.default_imgui_window_type = hello_imgui.DefaultImGuiWindowType.provide_full_screen_window
    params.imgui_window_params.show_menu_bar = True
    params.imgui_window_params.background_color = to_vec4(cfg.theme.bg)
    # hello_imgui resolves a relative ini against the cwd; pin it absolute
    if not params.ini_filename:
        ini = default_ini_path()
        params.ini_filename = ini
        params.ini_folder_type = hello_imgui.IniFolderType.absolute_path
        os.makedirs(os.path.dirname(ini), exist_ok=True)
    params.callbacks.show_menus = menu.draw_menu
    params.callbacks.show_gui = menu.render
    params.callbacks.before_exit = menu.launcher.stop_all
    immapp.run(runner_params=params, add_ons_params=immapp.AddOnsParams())
    return menu


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="imgui-notebooks", description="Open jupyter and marimo notebooks from an imgui window.")
    parser.add_argument("folders", nargs="*", help="folders whose notebooks are listed")
    parser.add_argument("--host", default="", help="ssh destination the folders are on; this machine when omitted")
    parser.add_argument("--python", default="", help="python executable or virtualenv directory on that machine")
    parser.add_argument("--recursive", action="store_true", help="include subfolders")
    args = parser.parse_args(argv)
    host = Host(args.host, args.python)
    sources = [FolderSource(folder, host, recursive=args.recursive) for folder in args.folders]
    run_notebooks(NotebookMenuConfig(sources=sources, visible=True))
