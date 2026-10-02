"""Where notebooks come from: a folder here or over ssh, a fixed list, or a function of your own."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol, Sequence

from imgui_notebooks.model import Host, Notebook, detect_backend, split_path
from imgui_notebooks.remote import detect_os, list_command, ssh_run

SKIP_DIRS = ("__pycache__", "node_modules")


class Source(Protocol):
    """Anything with a ``label`` and a ``notebooks()`` that lists what it holds right now."""

    label: str

    def notebooks(self) -> list[Notebook]: ...


@dataclass
class FolderSource:
    """Every notebook in a directory on this machine or on ``host``.

    ``.ipynb`` files and ``.py`` files holding a marimo app count; checkpoint and hidden directories
    do not. The folder is the jupyter root, so its notebooks share one server.
    """

    dir: str
    host: Host = field(default_factory=Host)
    label: str = ""
    recursive: bool = False

    def __post_init__(self):
        self.dir = str(self.dir).strip().strip('"')
        if not self.label:
            self.label = split_path(self.dir)[1] or self.dir

    def notebooks(self) -> list[Notebook]:
        if self.host.local:
            root = Path(self.dir)
            if not root.is_dir():
                raise FileNotFoundError(f"{self.dir} is not a directory on this machine")
            paths = []
            for candidate in sorted(root.rglob("*") if self.recursive else root.iterdir()):
                parents = candidate.relative_to(root).parts[:-1]
                if any(part.startswith(".") or part in SKIP_DIRS for part in parents):
                    continue
                if candidate.is_file() and detect_backend(str(candidate)):
                    paths.append(str(candidate))
        else:
            if not self.host.os:
                self.host.os = detect_os(self.host)
            result = ssh_run(self.host, list_command(self.dir, self.host.os, self.recursive), 60)
            if result.returncode == 255:
                raise ConnectionError(f"ssh {self.host.name}: {result.stderr.strip() or 'connection failed'}")
            paths = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return [Notebook(path, group=self.label, host=self.host, root=self.dir) for path in paths]


@dataclass
class ListSource:
    """A fixed list of notebooks."""

    items: Sequence[Notebook]
    label: str = ""

    def notebooks(self) -> list[Notebook]:
        return list(self.items)


@dataclass
class CallableSource:
    """Whatever ``fn()`` returns when the menu refreshes, for lists that change while the app runs."""

    fn: Callable[[], Sequence[Notebook]]
    label: str = ""

    def notebooks(self) -> list[Notebook]:
        return list(self.fn())


def scan(sources: Sequence[Source]) -> tuple[list[Notebook], list[str]]:
    """Every notebook from every source, and one message per source that failed."""
    notebooks: list[Notebook] = []
    errors: list[str] = []
    for source in sources:
        try:
            found = source.notebooks()
        except Exception as exc:
            errors.append(f"{source.label or type(source).__name__}: {exc}")
            continue
        for notebook in found:
            if not notebook.group:
                notebook.group = source.label
        notebooks.extend(found)
    return notebooks, errors
