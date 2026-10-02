"""An "Open Notebook" submenu inside a host app's File menu, with sources that change while it runs.

Three sources: the example folder, a list the app builds itself, and a function the menu calls on
every refresh, so whatever it returns is what the menu shows. Run it with
``python examples/notebook_menu.py``.
"""

import time
from pathlib import Path

from imgui_bundle import hello_imgui, imgui, immapp

from imgui_notebooks import CallableSource, FolderSource, Hotkey, ListSource, Notebook, NotebookMenu, NotebookMenuConfig

HERE = Path(__file__).parent
STARTED = time.time()


def recent_notebooks() -> list:
    """Whatever this returns is the "changed recently" submenu: here, the examples touched since the app started."""
    return [Notebook(str(path), root=str(HERE / "notebooks")) for path in (HERE / "notebooks").iterdir() if path.stat().st_mtime >= STARTED]


class App:
    """A host app with its own File menu."""

    def __init__(self):
        self.threshold = 0.4
        self.menu = NotebookMenu(
            NotebookMenuConfig(
                sources=[
                    FolderSource(HERE / "notebooks", label="examples"),
                    ListSource([Notebook(str(HERE / "notebooks" / "hello.ipynb"), label="the jupyter one")], label="picked by the app"),
                    CallableSource(recent_notebooks, label="changed recently"),
                ],
                hotkey=Hotkey(imgui.Key.n, ctrl=True),
            )
        )

    def draw_menu(self) -> None:
        if imgui.begin_menu("File"):
            if imgui.menu_item_simple("Open File", "Ctrl+O"):
                pass
            imgui.separator()
            self.menu.draw_menu()
            imgui.end_menu()

    def draw(self) -> None:
        imgui.text("app content")
        _, self.threshold = imgui.slider_float("threshold", self.threshold, 0.0, 1.0)
        self.menu.render_window()


APP = App()

if __name__ == "__main__":
    params = hello_imgui.RunnerParams()
    params.app_window_params.window_title = "notebook_menu"
    params.app_window_params.window_geometry.size = (1000, 700)
    params.imgui_window_params.show_menu_bar = True
    params.callbacks.show_menus = APP.draw_menu
    params.callbacks.show_gui = APP.draw
    immapp.run(runner_params=params)
