# Architecture

Internal notes for contributors to `imgui_notebooks`.

## What this is

`imgui_notebooks` is an "Open Notebook" menu for
[imgui-bundle](https://github.com/pthom/imgui_bundle) apps. Picking a notebook
starts (or reuses) a JupyterLab or marimo server, on this machine or over an
ssh tunnel, and opens the notebook in the browser. The sources the menu lists
are objects the host app supplies and may change at runtime, plus folders the
user adds from the panel. The only runtime dependency is `imgui-bundle`.

## Commands

```bash
uv venv && uv pip install -e '.[dev,servers]'   # servers = jupyterlab + marimo, for the launch tests
pytest                                           # the full suite (testpaths=tests)
pytest tests/test_server.py                      # real local launches; skip when a package is missing
pytest tests/test_headless_render.py             # the null backend; skips if it cannot init
python examples/notebook_menu.py
```

There is no configured linter/formatter. The package ships `py.typed`, so keep
type hints intact.

## Modules, in dependency order

Nothing below imports anything above it.

**1. Data and pure builders, no imgui, no processes.**

- `model.py` — `Host` (where a server runs: an ssh destination or empty for
  this machine, the python there, the platform) and `Notebook` (path, backend,
  label, group, host, root). `Notebook.__post_init__` fills backend, label and root
  from the path; backend comes from the file locally (`detect_backend` reads a `.py`
  for the `marimo.App(` marker) and from the suffix remotely, since the file is
  not here to read. `split_path` splits on either separator so a remote Windows
  path works on a mac. `Host.executable` turns a venv directory into its
  interpreter per platform.
- `commands.py` — `BACKENDS`, the registry of what each backend needs (package,
  module, one-server-per-file or per-root, the url path that answers when up),
  and the argv / url builders. Jupyter is started with `port_retries=0` so a
  taken port fails rather than silently moving. The token goes on the command
  line on purpose: it is what the remote kill matches on.
- `remote.py` — what goes over ssh. `shell_command` quotes an argv for the
  remote shell: `shlex` on posix, and on Windows a
  `powershell -EncodedCommand` (base64 UTF-16LE) so neither cmd nor pwsh as
  sshd's default shell parses anything. `list_command`, `kill_command` and
  `detect_os` are the three remote one-offs; `ssh_server_args` is the long-lived
  session: `-tt` for a pty (so the remote server gets SIGHUP when the session
  ends), `-L port:127.0.0.1:port` with the same number on both ends,
  `BatchMode=yes` so a login that would prompt fails instead of hanging,
  `ExitOnForwardFailure=yes` so a port clash is an error.

**2. Sources and servers: threads, no imgui.**

- `sources.py` — `FolderSource` (local walk, or `list_command` over ssh),
  `ListSource`, `CallableSource`, and `scan`, which is the one place a source's
  exception is caught: it becomes one message per source, shown on the panel's
  status line, and the other sources still list.
- `server.py` — `Server.run` is the whole launch on one thread: detect the
  platform if unknown, `import` check, install if allowed, `Popen`, poll the
  ready url, then hand pending paths to `on_open`. The frame only ever reads
  `state`, `status` and `log`. State changes that a second thread also reads
  happen under `lock`; `open()` either queues a path or shows it, decided under
  the same lock the `RUNNING` transition takes, so a path cannot be queued
  after the queue was drained. Process groups: `CREATE_NEW_PROCESS_GROUP` +
  `taskkill /T` on Windows, `start_new_session` + `killpg` elsewhere, so
  kernels die with the server. A remote stop terminates ssh (the pty hangs the
  server up) and then runs `kill_command` on the token as a backstop.
  `Launcher` keys servers by `(backend, host, python, root-or-file)` and registers
  `stop_all` with `atexit`.
- `store.py` — one JSON file: the folders added from the panel and the recent
  list. Guarded reads and writes, as in the sibling packages, because the
  callers are inside a frame.

**3. View and controller.**

- `theme.py`, `widgets.py`, `panel.py` — the same `Theme`, `em` / `section` /
  `popup` helpers and `Panel` / `PanelConfig` / `Hotkey` the sibling packages
  carry, copied rather than imported so this package depends on imgui-bundle
  only. `native_dialogs_available` is the check from masknmf's `files.py`: the
  Browse button is disabled where portable-file-dialogs cannot draw.
- `notebooks.py` — `NotebookMenu(Panel)`. `draw_menu` / `draw_menu_items` are
  the menu; `render` is the panel body; `render_window` also draws the
  add/open form when the window is closed, because the menu can open the form
  without the panel. `refresh` scans on a worker thread and swaps the list in
  under a lock; `is_window_appearing` inside the menu triggers it. The form is
  one popup in two modes (add a folder, open a path) with the host and python
  fields kept between uses.
- `runner.py` — `run_notebooks`, the one-shot window, and `main` for the
  `imgui-notebooks` command. The `.ini` is pinned to an absolute path, as in
  the siblings, only when the caller's params leave it unset.

## Adding a backend

A backend is a `Backend` entry in `commands.BACKENDS` plus a branch in
`server_command` and `server_url`, and an icon in `notebooks.ICONS`. The server
has to serve HTTP on `127.0.0.1:port` and answer something (any status) on
`ready_path`. A fastplotlib app served through jupyter is already covered; one
that serves itself would be a backend of its own.

## Testing notes

`tests/test_server.py` starts real JupyterLab and marimo servers from the test
interpreter: ready, opened, reused for a second notebook under the same root,
stopped, port closed. Each test skips when its package is not importable, so a
green run on a bare environment means "skipped" — check `-rs`. The remote path
is covered only by the pure builders in `tests/test_remote.py`; there is no
ssh host in CI.

Rendering runs on hello_imgui's null backend as in the siblings: the null
renderer needs `BackendFlags_.renderer_has_textures` set in `post_init`, the
`.ini` goes to the temp folder, and the tests skip if the backend cannot init.
