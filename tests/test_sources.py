"""Folder scanning, fixed lists, callables, and how a failing source is reported."""

from imgui_notebooks.model import Host, Notebook
from imgui_notebooks.sources import CallableSource, FolderSource, ListSource, scan


def make_tree(root):
    (root / "a.ipynb").write_text("{}")
    (root / "app.py").write_text("import marimo\napp = marimo.App()\n")
    (root / "plain.py").write_text("x = 1\n")
    (root / "notes.txt").write_text("")
    (root / ".ipynb_checkpoints").mkdir()
    (root / ".ipynb_checkpoints" / "a-checkpoint.ipynb").write_text("{}")
    (root / "sub").mkdir()
    (root / "sub" / "b.ipynb").write_text("{}")
    (root / "sub" / "__pycache__").mkdir()
    (root / "sub" / "__pycache__" / "c.ipynb").write_text("{}")


def test_folder_source_lists_notebooks_only(tmp_path):
    make_tree(tmp_path)
    source = FolderSource(tmp_path)
    assert source.label == tmp_path.name
    found = source.notebooks()
    assert [n.label for n in found] == ["a.ipynb", "app.py"]
    assert {n.backend for n in found} == {"jupyter", "marimo"}
    assert all(n.group == tmp_path.name and n.root == str(tmp_path) for n in found)


def test_folder_source_recursive_skips_checkpoints_and_caches(tmp_path):
    make_tree(tmp_path)
    found = FolderSource(tmp_path, label="deep", recursive=True).notebooks()
    assert [n.label for n in found] == ["a.ipynb", "app.py", "b.ipynb"]
    assert found[-1].root == str(tmp_path)


def test_scan_reports_a_missing_folder_and_keeps_going(tmp_path):
    make_tree(tmp_path)
    notebooks, errors = scan([FolderSource(tmp_path / "nope", label="gone"), FolderSource(tmp_path)])
    assert len(notebooks) == 2
    assert len(errors) == 1
    assert errors[0].startswith("gone:")


def test_list_and_callable_sources_take_the_source_label_as_group(tmp_path):
    (tmp_path / "a.ipynb").write_text("{}")
    item = Notebook(str(tmp_path / "a.ipynb"))
    notebooks, errors = scan([ListSource([item], label="fixed"), CallableSource(lambda: [Notebook(str(tmp_path / "a.ipynb"), group="mine")], label="dynamic")])
    assert errors == []
    assert [n.group for n in notebooks] == ["fixed", "mine"]


def test_folder_source_on_a_remote_host_carries_the_host():
    source = FolderSource("/srv/nb", Host("box", "/opt/venv"), recursive=True)
    assert source.host.name == "box"
    assert source.label == "nb"
