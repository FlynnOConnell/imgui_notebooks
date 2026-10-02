"""The folders added from the panel and the notebooks opened last, as one JSON file."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from imgui_notebooks._assets import data_dir
from imgui_notebooks.model import Host, Notebook
from imgui_notebooks.sources import FolderSource


class Store:
    """A JSON file under the data directory, read and written whole.

    Every read and write is guarded: a missing or half-written file is an empty state, never an
    exception inside a frame. The directory is created on the first write.
    """

    def __init__(self, path: str | Path | None = None):
        self._path = path

    @property
    def path(self) -> Path:
        return Path(self._path) if self._path else data_dir() / "state.json"

    def read(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def write(self, state: dict) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(state, indent=2), encoding="utf-8")
            return True
        except OSError:
            return False

    def sources(self) -> list[FolderSource]:
        """The folders added from the panel."""
        sources = []
        for item in self.read().get("sources", []):
            host = Host(**item.get("host", {}))
            sources.append(FolderSource(item["dir"], host, item.get("label", ""), item.get("recursive", False)))
        return sources

    def set_sources(self, sources: list[FolderSource]) -> bool:
        state = self.read()
        state["sources"] = [asdict(source) for source in sources]
        return self.write(state)

    def recent(self) -> list[Notebook]:
        """The notebooks opened last, newest first."""
        return [
            Notebook(item["path"], item["backend"], item["label"], item.get("group", ""), Host(**item["host"]), item["root"])
            for item in self.read().get("recent", [])
        ]

    def record(self, notebook: Notebook, max_recent: int = 8) -> bool:
        """Put ``notebook`` at the top of the recent list."""
        state = self.read()
        recent = [item for item in state.get("recent", []) if (item["path"], item["host"]["name"]) != (notebook.path, notebook.host.name)]
        state["recent"] = [asdict(notebook), *recent][:max_recent]
        return self.write(state)
