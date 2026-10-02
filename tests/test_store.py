"""The JSON state file: folders added from the panel and the recent list."""

from imgui_notebooks.model import Host, Notebook
from imgui_notebooks.sources import FolderSource
from imgui_notebooks.store import Store


def test_missing_file_is_empty(tmp_path):
    store = Store(tmp_path / "state.json")
    assert store.read() == {}
    assert store.sources() == []
    assert store.recent() == []


def test_sources_round_trip(tmp_path):
    store = Store(tmp_path / "cfg" / "state.json")
    sources = [FolderSource("/srv/nb", Host("box", "/opt/venv", "linux"), "lab", True), FolderSource(str(tmp_path))]
    assert store.set_sources(sources)
    loaded = store.sources()
    assert [s.dir for s in loaded] == ["/srv/nb", str(tmp_path)]
    assert loaded[0].host.name == "box"
    assert loaded[0].host.python == "/opt/venv"
    assert loaded[0].recursive is True
    assert loaded[1].host.local


def test_recent_is_newest_first_and_capped(tmp_path):
    store = Store(tmp_path / "state.json")
    first = Notebook("/nb/a.ipynb", host=Host("box", os="linux"))
    second = Notebook("/nb/b.py", host=Host("box", os="linux"))
    store.record(first, max_recent=2)
    store.record(second, max_recent=2)
    store.record(first, max_recent=2)
    recent = store.recent()
    assert [n.path for n in recent] == ["/nb/a.ipynb", "/nb/b.py"]
    assert recent[0].backend == "jupyter"
    assert recent[0].host.name == "box"
    store.record(Notebook("/nb/c.ipynb", host=Host("box", os="linux")), max_recent=2)
    assert [n.path for n in store.recent()] == ["/nb/c.ipynb", "/nb/a.ipynb"]


def test_bad_json_reads_as_empty(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{not json")
    assert Store(path).read() == {}
