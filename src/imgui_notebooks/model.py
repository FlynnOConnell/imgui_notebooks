"""Hosts and notebooks: the data every other module shares. Nothing here touches imgui or a process."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

JUPYTER = "jupyter"
MARIMO = "marimo"
MARIMO_MARKER = "marimo.App("

WINDOWS = "windows"
LINUX = "linux"
DARWIN = "darwin"


def local_os() -> str:
    """This machine's platform: ``windows``, ``darwin`` or ``linux``."""
    if sys.platform == "win32":
        return WINDOWS
    if sys.platform == "darwin":
        return DARWIN
    return LINUX


def split_path(path: str) -> tuple[str, str]:
    """``(directory, name)`` of a path written for any platform, so a remote Windows path splits on a mac too."""
    normalized = path.replace("\\", "/").rstrip("/")
    head, sep, name = normalized.rpartition("/")
    if not sep:
        return "", name
    return head or "/", name


def backend_of_name(name: str) -> str:
    """The backend a file name suggests: ``.ipynb`` is jupyter, ``.py`` is marimo, anything else is ``""``."""
    lower = name.lower()
    if lower.endswith(".ipynb"):
        return JUPYTER
    if lower.endswith(".py"):
        return MARIMO
    return ""


def detect_backend(path: str) -> str:
    """The backend of a file on this machine: jupyter for ``.ipynb``, marimo for a ``.py`` that builds a marimo app, else ``""``."""
    backend = backend_of_name(path)
    if backend != MARIMO:
        return backend
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return MARIMO if MARIMO_MARKER in text else ""


@dataclass
class Host:
    """Where a server runs.

    Parameters
    ----------
    name : str
        Empty for this machine, else an ssh destination: an alias from ``~/.ssh/config`` or ``user@machine``.
        Key-based login has to work without a prompt; run ``ssh name`` once in a terminal if it does not.
    python : str
        The interpreter that runs the server there: a python executable, a virtualenv directory, or empty for
        this process's interpreter locally and ``python3`` (``python`` on Windows) remotely.
    os : str
        ``windows``, ``linux`` or ``darwin``; filled in for this machine, detected over ssh when left empty.
    """

    name: str = ""
    python: str = ""
    os: str = ""

    def __post_init__(self):
        self.name = self.name.strip()
        self.python = self.python.strip()
        if self.local and not self.os:
            self.os = local_os()

    @property
    def local(self) -> bool:
        return self.name == ""

    @property
    def label(self) -> str:
        return self.name or "this machine"

    @property
    def executable(self) -> str:
        """The python that runs servers on this host, resolved from ``python``."""
        if not self.python:
            if self.local:
                return sys.executable
            return "python" if self.os == WINDOWS else "python3"
        name = split_path(self.python)[1].lower()
        if name.startswith("python") or name.endswith(".exe"):
            return self.python
        if self.os == WINDOWS:
            return self.python.rstrip("/\\") + "\\Scripts\\python.exe"
        return self.python.rstrip("/") + "/bin/python"


@dataclass
class Notebook:
    """One notebook the menu can open.

    Parameters
    ----------
    path : str
        The file, as the host that serves it sees it.
    backend : str
        ``jupyter`` or ``marimo``; read from the file (locally) or its suffix (remotely) when empty.
    label : str
        Menu text; the file name when empty.
    group : str
        Submenu the entry is listed under; the source's label when empty.
    host : Host
        The machine that serves it.
    root : str
        The directory a jupyter server serves; the notebook's own directory when empty. Notebooks that
        share a root share one server.
    """

    path: str
    backend: str = ""
    label: str = ""
    group: str = ""
    host: Host = field(default_factory=Host)
    root: str = ""

    def __post_init__(self):
        self.path = str(self.path).strip().strip('"')
        directory, name = split_path(self.path)
        if not self.backend:
            self.backend = detect_backend(self.path) if self.host.local else backend_of_name(name)
        if not self.label:
            self.label = name
        if not self.root:
            self.root = directory
