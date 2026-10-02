"""The panel in a window of its own, listing the notebooks shipped beside this file.

Run it with ``python examples/notebooks_minimal.py``.
"""

from pathlib import Path

from imgui_notebooks import FolderSource, NotebookMenuConfig, run_notebooks

CONFIG = NotebookMenuConfig(
    sources=[FolderSource(Path(__file__).parent / "notebooks", label="examples")],
    visible=True,
)

if __name__ == "__main__":
    run_notebooks(CONFIG)
