"""The widget: an "Open Notebook" menu for a host app's menu bar, and the panel behind it.

The menu lists every notebook the sources hold, grouped by source; picking one starts or reuses the
server for it and opens it in the browser. The panel shows the same list, the servers with their
urls and logs, and the sources, with a form to add a folder or open one path.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

from imgui_bundle import icons_fontawesome_6 as fa
from imgui_bundle import imgui
from imgui_bundle import portable_file_dialogs as pfd

from imgui_notebooks.commands import BACKENDS
from imgui_notebooks.model import JUPYTER, MARIMO, Host, Notebook
from imgui_notebooks.panel import Panel, PanelConfig
from imgui_notebooks.server import FAILED, INSTALLING, LIVE, RUNNING, STARTING, STOPPED, Launcher, Server
from imgui_notebooks.sources import FolderSource, scan
from imgui_notebooks.store import Store
from imgui_notebooks.theme import to_vec4
from imgui_notebooks.widgets import NATIVE_DIALOGS, danger_button, em, help_mark, popup, section, tooltip

ICONS = {JUPYTER: fa.ICON_FA_BOOK, MARIMO: fa.ICON_FA_FLASK}
STATE_ROLES = {STARTING: "warn", INSTALLING: "warn", RUNNING: "ok", STOPPED: "text_dim", FAILED: "error"}
NOTEBOOK_FILTERS = ["Notebooks", "*.ipynb *.py", "All files", "*"]
FORM_ADD = "add"
FORM_OPEN = "open"


@dataclass
class NotebookMenuConfig(PanelConfig):
    """What the menu lists and how notebooks are opened.

    Parameters
    ----------
    menu_label : str
        The menu's label: a submenu inside your File menu, or a top-level menu of its own.
    manage_label : str
        The entry that opens the panel.
    sources : list
        The app's sources: ``FolderSource``, ``ListSource``, ``CallableSource`` or anything with a
        ``label`` and a ``notebooks()``. The list is read again on every refresh, so it can change.
    store : Store | None
        Keeps the folders added from the panel and the recent list between runs; None keeps nothing.
    auto_install : bool
        Install jupyterlab or marimo into a host's python when it is missing there.
    start_timeout : float
        Seconds a server gets to answer before the launch is reported as failed.
    on_open : callable | None
        ``on_open(url)`` when a notebook is ready; the system browser when None.
    refresh_on_open : bool
        Read the sources again each time the menu opens.
    show_on_open : bool
        Show the panel when a notebook is opened, so the launch can be watched.
    max_recent : int
        How many recently opened notebooks the Recent submenu keeps.

    Every :class:`~imgui_notebooks.panel.PanelConfig` field is also accepted.
    """

    title: str = "Notebooks"
    visible: bool = False
    window_size: tuple = (780, 600)
    menu_label: str = "Open Notebook"
    manage_label: str = "Manage notebooks..."
    sources: list = field(default_factory=list)
    store: Optional[Store] = field(default_factory=Store)
    auto_install: bool = True
    start_timeout: float = 90.0
    on_open: Optional[Callable[[str], object]] = None
    refresh_on_open: bool = True
    show_on_open: bool = True
    max_recent: int = 8


class NotebookMenu(Panel):
    """An "Open Notebook" menu and the Notebooks panel behind it.

    Two calls wire it into a host app: ``menu.draw_menu()`` inside the menu bar (or inside the File
    menu, where it becomes a submenu) and ``menu.render_window()`` once per frame.
    """

    config_class = NotebookMenuConfig

    def __init__(self, config: Optional[NotebookMenuConfig] = None):
        super().__init__(config or NotebookMenuConfig())
        cfg = self.config
        self.launcher = Launcher(cfg.auto_install, cfg.start_timeout, cfg.on_open)
        self.user_sources: list[FolderSource] = cfg.store.sources() if cfg.store is not None else []
        self.recent: list[Notebook] = cfg.store.recent() if cfg.store is not None else []
        self.status = ""
        self._notebooks: list[Notebook] = []
        self._errors: list[str] = []
        self._scanning = False
        self._lock = threading.Lock()
        self._form: Optional[str] = None
        self._form_path = ""
        self._form_host = ""
        self._form_python = ""
        self._form_recursive = False
        self._form_error = ""
        self._dialog = None
        self.refresh()

    @property
    def sources(self) -> list:
        """The app's sources followed by the folders added from the panel."""
        return [*self.config.sources, *self.user_sources]

    @property
    def scanning(self) -> bool:
        return self._scanning

    @property
    def errors(self) -> list[str]:
        """One message per source the last refresh could not read."""
        with self._lock:
            return list(self._errors)

    def notebooks(self) -> list[Notebook]:
        """Every notebook the last refresh found."""
        with self._lock:
            return list(self._notebooks)

    def refresh(self) -> None:
        """Read every source again on a worker thread; the list swaps in when it is done."""
        if self._scanning:
            return
        self._scanning = True
        threading.Thread(target=self._scan, name="imgui_notebooks scan", daemon=True).start()

    def _scan(self) -> None:
        notebooks, errors = scan(self.sources)
        with self._lock:
            self._notebooks = notebooks
            self._errors = errors
        self._scanning = False

    def add_folder(self, directory: str, host: Optional[Host] = None, recursive: bool = False, label: str = "") -> FolderSource:
        """Add a folder source, keep it in the store, and refresh."""
        source = FolderSource(directory, host or Host(), label, recursive)
        self.user_sources.append(source)
        if self.config.store is not None:
            self.config.store.set_sources(self.user_sources)
        self.refresh()
        return source

    def remove_source(self, source) -> None:
        """Drop a source added from the panel."""
        self.user_sources = [s for s in self.user_sources if s is not source]
        if self.config.store is not None:
            self.config.store.set_sources(self.user_sources)
        self.refresh()

    def open(self, notebook: Notebook) -> Server:
        """Open ``notebook``: start or reuse its server, then show it in the browser."""
        server = self.launcher.open(notebook)
        self.status = f"opening {notebook.label} on {notebook.host.label}"
        kept = [n for n in self.recent if (n.path, n.host.name) != (notebook.path, notebook.host.name)]
        self.recent = [notebook, *kept][: self.config.max_recent]
        if self.config.store is not None:
            self.config.store.record(notebook, self.config.max_recent)
        if self.config.show_on_open:
            self.show()
        return server

    def open_path(self, path: str, host: Optional[Host] = None) -> Optional[Server]:
        """Open one notebook by path, here or on ``host``; None, with the reason on the status line, when it cannot be."""
        host = host or Host()
        path = path.strip().strip('"')
        if host.local and not os.path.isfile(path):
            self.status = f"{path} does not exist on this machine"
            return None
        notebook = Notebook(path, host=host)
        if notebook.backend not in BACKENDS:
            self.status = f"{path} is not a jupyter or marimo notebook"
            return None
        return self.open(notebook)

    def show_form(self, mode: str, path: str = "") -> None:
        """Open the add-folder (``"add"``) or open-path (``"open"``) form."""
        self._form = mode
        self._form_path = path
        self._form_error = ""

    def draw_menu(self) -> None:
        """The menu named ``menu_label``: top-level in a menu bar, a submenu inside an open menu."""
        if not imgui.begin_menu(self.config.menu_label):
            return
        if imgui.is_window_appearing() and self.config.refresh_on_open:
            self.refresh()
        self.draw_menu_items()
        imgui.end_menu()

    def draw_menu_items(self) -> None:
        """The menu's entries, inside a menu you already opened."""
        notebooks = self.notebooks()
        groups: dict[str, list[Notebook]] = {}
        for notebook in notebooks:
            groups.setdefault(notebook.group, []).append(notebook)
        if not notebooks:
            imgui.menu_item_simple("scanning..." if self._scanning else "no notebooks found", enabled=False)
        for group, items in groups.items():
            if len(groups) == 1 or not group:
                for notebook in items:
                    self._draw_entry(notebook)
            elif imgui.begin_menu(group):
                for notebook in items:
                    self._draw_entry(notebook)
                imgui.end_menu()
        if self.recent:
            imgui.separator()
            if imgui.begin_menu("Recent"):
                for notebook in self.recent:
                    self._draw_entry(notebook)
                imgui.end_menu()
        imgui.separator()
        if imgui.menu_item_simple("Open path..."):
            self.show_form(FORM_OPEN)
        if imgui.menu_item_simple("Add folder..."):
            self.show_form(FORM_ADD)
        self.menu_item(self.config.manage_label)

    def _draw_entry(self, notebook: Notebook) -> None:
        label = f"{ICONS.get(notebook.backend, '')}  {notebook.label}##{notebook.host.name}:{notebook.path}"
        if imgui.menu_item_simple(label, notebook.host.name or notebook.backend):
            self.open(notebook)
        tooltip(notebook.path)

    def render(self) -> None:
        """The panel body: the toolbar, the notebooks, the servers, the sources, and the form when it is up."""
        self._poll_dialog()
        self._draw_toolbar()
        self._draw_notebooks()
        self._draw_servers()
        self._draw_sources()
        self._draw_form()

    def render_window(self, flags: int = 0) -> bool:
        """The panel in its own window; the form still draws when the window is closed, since the menu opens it."""
        shown = super().render_window(flags)
        if not shown:
            self._poll_dialog()
            self._draw_form()
        return shown

    def _poll_dialog(self) -> None:
        if self._dialog is None or not self._dialog.ready(0):
            return
        result = self._dialog.result()
        self._dialog = None
        if result:
            self._form_path = result[0] if isinstance(result, list) else result

    def _draw_toolbar(self) -> None:
        theme = self.theme
        imgui.begin_disabled(self._scanning)
        if imgui.button(f"{fa.ICON_FA_ARROWS_ROTATE}  refresh"):
            self.refresh()
        imgui.end_disabled()
        tooltip("read every source again")
        imgui.same_line(0, em(0.4))
        if imgui.button(f"{fa.ICON_FA_FOLDER_PLUS}  add folder"):
            self.show_form(FORM_ADD)
        tooltip("list every notebook in a folder, here or on a machine you can ssh to")
        imgui.same_line(0, em(0.4))
        if imgui.button(f"{fa.ICON_FA_FILE}  open path"):
            self.show_form(FORM_OPEN)
        tooltip("open one notebook by its path")
        imgui.same_line(0, em(1.0))
        busy = self._scanning or any(server.state in (STARTING, INSTALLING) for server in self.launcher.servers.values())
        if busy:
            # a negative fraction is imgui's indeterminate bar
            imgui.progress_bar(-1.0 * imgui.get_time(), imgui.ImVec2(em(5), em(0.9)), "")
            imgui.same_line(0, em(0.6))
        errors = self.errors
        if errors:
            color, text = theme.error, errors[0]
        elif self._scanning:
            color, text = theme.warn, f"scanning {len(self.sources)} sources"
        elif self.status:
            color, text = theme.text_dim, self.status
        else:
            color, text = theme.text_dim, f"{len(self.notebooks())} notebooks from {len(self.sources)} sources"
        imgui.align_text_to_frame_padding()
        imgui.text_colored(to_vec4(color), text)

    def _draw_notebooks(self) -> None:
        theme = self.theme
        notebooks = self.notebooks()
        section(f"Notebooks ({len(notebooks)})", theme)
        if not notebooks:
            imgui.text_disabled("none found: add a folder, or give the app sources")
            return
        flags = (
            imgui.TableFlags_.row_bg
            | imgui.TableFlags_.borders_inner_h
            | imgui.TableFlags_.scroll_y
            | imgui.TableFlags_.sizing_stretch_prop
        )
        height = min(em(1.7) * (len(notebooks) + 1), em(12))
        if not imgui.begin_table("##notebooks", 5, flags, imgui.ImVec2(0, height)):
            return
        imgui.table_setup_scroll_freeze(0, 1)
        imgui.table_setup_column("backend", imgui.TableColumnFlags_.width_fixed, em(6))
        imgui.table_setup_column("notebook", imgui.TableColumnFlags_.width_stretch, 2.0)
        imgui.table_setup_column("host", imgui.TableColumnFlags_.width_fixed, em(7))
        imgui.table_setup_column("path", imgui.TableColumnFlags_.width_stretch, 3.0)
        imgui.table_setup_column("##open", imgui.TableColumnFlags_.width_fixed, em(2.5))
        imgui.table_headers_row()
        clipper = imgui.ListClipper()
        clipper.begin(len(notebooks))
        while clipper.step():
            for i in range(clipper.display_start, clipper.display_end):
                notebook = notebooks[i]
                imgui.push_id(i)
                imgui.table_next_row()
                imgui.table_next_column()
                imgui.text_colored(to_vec4(theme.accent), f"{ICONS.get(notebook.backend, '')} {notebook.backend}")
                imgui.table_next_column()
                flags = imgui.SelectableFlags_.span_all_columns | imgui.SelectableFlags_.allow_overlap
                if imgui.selectable(notebook.label, False, flags)[0] and imgui.is_mouse_double_clicked(0):
                    self.open(notebook)
                tooltip(f"{notebook.path}\ndouble-click to open")
                imgui.table_next_column()
                imgui.text_disabled(notebook.host.label)
                imgui.table_next_column()
                imgui.text_disabled(notebook.path)
                imgui.table_next_column()
                if imgui.small_button(fa.ICON_FA_PLAY):
                    self.open(notebook)
                tooltip("open")
                imgui.pop_id()
        imgui.end_table()

    def _draw_servers(self) -> None:
        theme = self.theme
        servers = list(self.launcher.servers.values())
        section(f"Servers ({len(self.launcher.live())} live)", theme)
        if not servers:
            imgui.text_disabled("none started yet")
            return
        for i, server in enumerate(servers):
            imgui.push_id(1000 + i)
            imgui.text_colored(to_vec4(theme.accent), f"{ICONS.get(server.backend, '')} {server.label}")
            imgui.same_line(0, em(0.6))
            imgui.text_disabled(server.target)
            imgui.same_line(0, em(0.8))
            if server.state in LIVE:
                if danger_button(f"{fa.ICON_FA_STOP} stop", theme):
                    server.stop()
            elif imgui.small_button("clear"):
                self.launcher.forget(server)
            if server.state == RUNNING:
                imgui.same_line(0, em(0.4))
                if imgui.small_button(f"{fa.ICON_FA_COPY} copy url"):
                    imgui.set_clipboard_text(server.url)
                imgui.same_line(0, em(0.4))
                if imgui.small_button(f"{fa.ICON_FA_GLOBE} open"):
                    self.launcher.on_open(server.url)
            imgui.push_text_wrap_pos(0.0)
            imgui.text_colored(to_vec4(getattr(theme, STATE_ROLES[server.state])), f"{server.state}: {server.status}")
            imgui.pop_text_wrap_pos()
            if imgui.tree_node("log"):
                with server.lock:
                    lines = list(server.log)
                imgui.begin_child("##log", imgui.ImVec2(0, em(8)), imgui.ChildFlags_.borders)
                for line in lines:
                    imgui.text_unformatted(line)
                if imgui.get_scroll_y() >= imgui.get_scroll_max_y():
                    imgui.set_scroll_here_y(1.0)
                imgui.end_child()
                imgui.tree_pop()
            imgui.pop_id()

    def _draw_sources(self) -> None:
        theme = self.theme
        section(f"Sources ({len(self.sources)})", theme)
        for i, source in enumerate(self.sources):
            imgui.push_id(2000 + i)
            host = getattr(source, "host", None)
            detail = getattr(source, "dir", type(source).__name__)
            if getattr(source, "recursive", False):
                detail += "  (with subfolders)"
            imgui.text(source.label or type(source).__name__)
            imgui.same_line(0, em(0.6))
            imgui.text_disabled(f"{host.label if host is not None else 'app'}  ·  {detail}")
            imgui.same_line(0, em(0.8))
            if source in self.user_sources:
                if danger_button(f"{fa.ICON_FA_XMARK} remove", theme):
                    self.remove_source(source)
            else:
                imgui.text_disabled("(from the app)")
            imgui.pop_id()

    def _draw_form(self) -> None:
        if self._form is None:
            return
        theme = self.theme
        adding = self._form == FORM_ADD
        opened, keep = popup("Add a notebook folder" if adding else "Open a notebook", True, theme)
        if not keep:
            self._form = None
        if opened:
            imgui.text_disabled("a folder whose notebooks the menu lists" if adding else "one .ipynb, or a .py holding a marimo app")
            imgui.set_next_item_width(em(28))
            entered, self._form_path = imgui.input_text_with_hint(
                "##path", "path as that machine sees it", self._form_path, imgui.InputTextFlags_.enter_returns_true
            )
            if imgui.is_window_appearing():
                imgui.set_keyboard_focus_here(-1)
            imgui.same_line(0, em(0.4))
            local = not self._form_host.strip()
            imgui.begin_disabled(not (local and NATIVE_DIALOGS) or self._dialog is not None)
            if imgui.button("browse"):
                start = self._form_path.strip().strip('"') or os.getcwd()
                if adding:
                    self._dialog = pfd.select_folder("Add a notebook folder", start)
                else:
                    self._dialog = pfd.open_file("Open a notebook", start, NOTEBOOK_FILTERS, pfd.opt.none)
            imgui.end_disabled()
            tooltip("pick it in a file dialog on this machine" if local else "the dialog would open here; type the path on the other machine")
            imgui.set_next_item_width(em(12))
            _, self._form_host = imgui.input_text_with_hint("host", "this machine", self._form_host)
            help_mark("empty for this machine; else an alias from ~/.ssh/config or user@machine, with key login set up")
            imgui.set_next_item_width(em(28))
            _, self._form_python = imgui.input_text_with_hint("python", "that machine's default python", self._form_python)
            help_mark("a python executable or a virtualenv directory there; jupyterlab or marimo is installed into it when missing")
            if adding:
                _, self._form_recursive = imgui.checkbox("include subfolders", self._form_recursive)
            imgui.dummy(imgui.ImVec2(0, em(0.3)))
            if imgui.button("add" if adding else "open", imgui.ImVec2(em(6), 0)) or entered:
                path = self._form_path.strip().strip('"')
                host = Host(self._form_host, self._form_python)
                if not path:
                    self._form_error = "type a path"
                elif adding and host.local and not os.path.isdir(path):
                    self._form_error = f"{path} is not a directory on this machine"
                elif adding:
                    self.add_folder(path, host, self._form_recursive)
                    self.status = f"added {path} on {host.label}"
                    self._form = None
                elif self.open_path(path, host) is None:
                    self._form_error = self.status
                else:
                    self._form = None
            imgui.same_line(0, em(0.5))
            if imgui.button("cancel", imgui.ImVec2(em(6), 0)):
                self._form = None
            if self._form_error:
                imgui.push_text_wrap_pos(em(42))
                imgui.text_colored(to_vec4(theme.error), self._form_error)
                imgui.pop_text_wrap_pos()
        imgui.end()
