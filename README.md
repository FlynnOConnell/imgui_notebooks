<h1 align="center">imgui_notebooks</h1>

<p align="center">
<a href="https://pypi.org/project/imgui_notebooks/"><img src="https://img.shields.io/pypi/v/imgui_notebooks.svg" alt="PyPI version"></a>
<a href="https://pypi.org/project/imgui_notebooks/"><img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python 3.10+"></a>
<a href="LICENSE"><img src="https://img.shields.io/pypi/l/imgui_notebooks.svg" alt="License: MIT"></a>
</p>

<samp>
<p align="center">
An <b>Open Notebook</b> menu for imgui-bundle apps
<br>
<br>
<a href="#install">install</a> ·
<a href="#add-it-to-your-app">add it to your app</a> ·
<a href="#sources">sources</a> ·
<a href="#other-machines">other machines</a> ·
<a href="#environments">environments</a> ·
<a href="#examples">examples</a> ·
<a href="#configuration-reference">configuration</a> ·
<a href="https://github.com/FlynnOConnell/imgui_notebooks/issues">issues</a>
</p>
</samp>

## About

A menu entry per notebook. Picking one starts the server it needs (JupyterLab
for `.ipynb`, marimo for a `.py` that builds a marimo app), waits until it
answers, and opens the notebook in the browser. Notebooks in one folder share a
server, a second pick is instant, and every server stops when the app exits.

Where the notebooks come from is yours and can change while the app runs: a
folder here, a folder on a machine you can ssh to (the port is forwarded for
you), a list, or a function. Which python runs the server is yours too; when it
lacks jupyterlab or marimo, it gets it installed.

Built like [imgui_data_loader](https://github.com/FlynnOConnell/imgui_data_loader)
and [imgui_debugger](https://github.com/FlynnOConnell/imgui_debugger): one
dependency, a config dataclass, a panel with `visible` / `menu_item` /
`render` / `render_window`.

## Install

```bash
pip install imgui_notebooks
```

The only dependency is `imgui-bundle`. The servers live in whatever python
runs them; to have both in this one:

```bash
pip install 'imgui_notebooks[servers]'
```

## Add it to your app

Two calls, in an app that already has a menu bar:

```python
from imgui_bundle import imgui
from imgui_notebooks import FolderSource, NotebookMenu, NotebookMenuConfig

menu = NotebookMenu(NotebookMenuConfig(sources=[FolderSource("~/notebooks")]))

def draw_menus():                 # params.callbacks.show_menus
    if imgui.begin_menu("File"):
        menu.draw_menu()          # "Open Notebook ▸", one entry per notebook
        imgui.end_menu()

def draw():                       # params.callbacks.show_gui
    ...
    menu.render_window()          # the Notebooks panel, when it is open
```

`draw_menu()` draws a menu named `menu_label`: a submenu inside your File
menu, or a top-level menu if you call it from the menu bar. `draw_menu_items()`
draws only the entries. The menu ends with Recent, Open path, Add folder and
Manage notebooks, which opens the panel (also `menu.show()` or the `hotkey`).

With no host app:

```python
from imgui_notebooks import run_notebooks
run_notebooks()
```

```bash
imgui-notebooks ~/notebooks ~/demos --recursive
imgui-notebooks /srv/notebooks --host lab4 --python /opt/venv
```

## Sources

A source is anything with a `label` and a `notebooks()` returning `Notebook`s.
Every source is read again when the menu opens, when Refresh is pressed, or on
`menu.refresh()`; `config.sources` is a plain list, so append to it or swap it
out and the menu follows.

| source | lists |
|--------|-------|
| `FolderSource(dir, host=, label=, recursive=)` | every `.ipynb` and marimo `.py` in a folder, here or on `host`; checkpoints and hidden folders skipped; the folder is the jupyter root |
| `ListSource(items, label=)` | a fixed list of `Notebook`s |
| `CallableSource(fn, label=)` | whatever `fn()` returns, on every refresh |

Entries group by `Notebook.group`, the source's label by default: one group is
flat, more are submenus. Folders added from the panel are kept in the `Store`
and come back next run.

```python
Notebook(path, backend="", label="", group="", host=Host(), root="")
```

`backend` is read from the file locally (`.ipynb`, or `marimo.App(` in a
`.py`) and from the suffix remotely. `root` is the directory a jupyter server
serves; the notebook's own when empty.

## Other machines

```python
Host(name="lab4", python="/opt/venv")
```

`name` is an ssh destination: an alias from `~/.ssh/config` or `user@machine`.
Key login has to work without a prompt (`BatchMode=yes`); run `ssh lab4` once
in a terminal if it does not. The rest is automatic: the platform is detected,
the folder is listed there, the server starts there on its loopback, and the
ssh session that runs it forwards the port to the same port here, so the url
is always `127.0.0.1`. Stop ends the session (the pty hangs the server up) and
sends a `pkill` / `Stop-Process` for the token only that server carries.
Windows hosts get every command as `powershell -EncodedCommand`, whatever
sshd's default shell is.

## Environments

`Host.python` is a python executable, a virtualenv directory, or empty for
this interpreter locally and `python3` (`python` on Windows) remotely. Before a
server starts, `python -c "import jupyterlab"` (or `marimo`) runs there; when
it fails and `auto_install` is on, the package is installed into that
environment (`uv pip install --python` when uv is on this machine, else
`python -m pip install`). `auto_install=False` reports instead.

## Examples

See all examples in [`examples/`](examples/).

| name | file | what it shows |
|------|------|---------------|
| notebooks_minimal | [`notebooks_minimal.py`](examples/notebooks_minimal.py) | the panel alone, over the notebooks in `examples/notebooks/` |
| notebook_menu | [`notebook_menu.py`](examples/notebook_menu.py) | the submenu inside a host app's File menu, fed by a folder, a list and a function |

## Configuration reference

### `NotebookMenuConfig`

| field | default | purpose |
|-------|---------|---------|
| `menu_label` | `"Open Notebook"` | the menu's label |
| `manage_label` | `"Manage notebooks..."` | the entry that opens the panel |
| `sources` | `[]` | the app's sources, read again on every refresh |
| `store` | `Store()` | keeps folders added from the panel and the recent list; `None` keeps nothing |
| `auto_install` | `True` | install jupyterlab / marimo into a host's python when missing |
| `start_timeout` | `90.0` | seconds a server gets to answer |
| `on_open` | `None` | `on_open(url)` when a notebook is ready; the system browser when None; return `False` if it could not be shown |
| `refresh_on_open` | `True` | read the sources again each time the menu opens |
| `show_on_open` | `True` | show the panel when a notebook is opened |
| `max_recent` | `8` | entries in the Recent submenu |
| `title`, `visible`, `window_size`, `hotkey`, `theme`, … | | every `PanelConfig` field |

### `Launcher` and `Server`

`menu.launcher` holds every server started from the process and works on its
own:

```python
from imgui_notebooks import Host, Launcher, Notebook
launcher = Launcher(on_open=print)
server = launcher.open(Notebook("/srv/nb/analysis.ipynb", host=Host("lab4")))
server.state, server.status, server.url, server.log, server.stop()
```

`state` is `starting`, `installing`, `running`, `stopped` or `failed`;
`status` says what it is doing or why it failed; `log` holds the last lines
printed. `Launcher.open` reuses a live server that covers the notebook (same
jupyter root, or the same marimo file, on the same host and python) and
replaces a dead one. `stop_all` runs at interpreter exit.

## Files on disk

Everything the library writes lives under `~/.imgui_notebooks/` (override with
the `IMGUI_NOTEBOOKS_HOME` env var):

| path | written by | purpose |
|------|-----------|---------|
| `state.json` | `Store` | folders added from the panel, the recent list |
| `notebooks.ini` | `run_notebooks` | hello_imgui window layout; an embedding app's own `ini_filename` always wins |
| `assets/` | you (optional) | user assets folder, searched for the icon font when it cannot be resolved |

Embedded use with `store=None` writes nothing.

## Notes

- Servers bind to `127.0.0.1` with a random token, here and on remote hosts.
- A remote server that never answers (wrong python, a login that prompts)
  shows as `failed` with ssh's message on the status line and in the log.
- Draw callbacks run inside an active imgui frame; the launch runs on a thread,
  so a frame never waits on ssh, pip or a server.
- On a machine with no browser the status line carries the url to paste.

## License

MIT
