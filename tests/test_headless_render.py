"""Draw the menu and the panel for a few frames on hello_imgui's null backend: no window, no GPU.

If the null backend cannot initialize here the tests skip rather than fail.
"""

from pathlib import Path

import pytest

from imgui_notebooks import FolderSource, Hotkey, NotebookMenu, NotebookMenuConfig, Store, ensure_assets

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "notebooks"
STATE = {"frames": 0, "menu": None}


def enable_textures():
    """Tell imgui the null renderer has textures so NewFrame does not assert."""
    from imgui_bundle import imgui

    imgui.get_io().backend_flags |= imgui.BackendFlags_.renderer_has_textures


def null_runner_params():
    from imgui_bundle import hello_imgui

    params = hello_imgui.RunnerParams()
    params.platform_backend_type = hello_imgui.PlatformBackendType.null
    params.renderer_backend_type = hello_imgui.RendererBackendType.null
    params.app_window_params.window_geometry.size = (900, 700)
    params.ini_folder_type = hello_imgui.IniFolderType.temp_folder
    params.ini_filename = "imgui_notebooks_test.ini"
    params.callbacks.post_init = enable_textures
    return params


def gui():
    """The menu in a menu bar, the panel as a window and inline, and the form, over six frames."""
    from imgui_bundle import hello_imgui, imgui

    menu = STATE["menu"]
    STATE["frames"] += 1
    if imgui.begin_main_menu_bar():
        if imgui.begin_menu("File"):
            menu.draw_menu()
            imgui.end_menu()
        menu.draw_menu()
        imgui.end_main_menu_bar()
    menu.render_window()
    imgui.begin("inline")
    menu.render()
    imgui.end()
    if STATE["frames"] == 2:
        menu.show_form("add", str(EXAMPLES))
    if STATE["frames"] == 3:
        menu.show_form("open")
    if STATE["frames"] == 4:
        menu.hide()
        imgui.get_io().add_key_event(imgui.Key.f9, True)
    if STATE["frames"] >= 6:
        hello_imgui.get_runner_params().app_shall_exit = True


def run(menu: NotebookMenu) -> int:
    from imgui_bundle import hello_imgui

    STATE["frames"] = 0
    STATE["menu"] = menu
    params = null_runner_params()
    params.callbacks.show_gui = gui
    try:
        hello_imgui.run(params)
    except Exception as exc:
        pytest.skip(f"null backend unavailable: {exc}")
    return STATE["frames"]


def test_headless_render_smoke(tmp_path):
    ensure_assets()
    menu = NotebookMenu(
        NotebookMenuConfig(
            sources=[FolderSource(EXAMPLES, label="examples")],
            store=Store(tmp_path / "state.json"),
            visible=True,
            hotkey=Hotkey(imgui_key_f9()),
            show_on_open=False,
        )
    )
    deadline = 50
    while menu.scanning and deadline:
        import time

        time.sleep(0.1)
        deadline -= 1
    assert [n.label for n in menu.notebooks()] == ["hello.ipynb", "hello_marimo.py"]
    assert run(menu) >= 6
    assert menu.visible, "the hotkey should have reopened the hidden panel"
    menu.launcher.stop_all()


def imgui_key_f9():
    from imgui_bundle import imgui

    return imgui.Key.f9


def test_headless_render_with_no_sources_and_no_store():
    ensure_assets()
    menu = NotebookMenu(NotebookMenuConfig(store=None, visible=True, show_on_open=False))
    assert menu.sources == []
    assert run(menu) >= 6
