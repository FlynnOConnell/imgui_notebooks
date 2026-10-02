"""Real servers on this machine: started, answered, reused, stopped. Each test skips when its server package is missing."""

import shutil
import time
import urllib.request
from pathlib import Path

import pytest

from imgui_notebooks.model import Notebook
from imgui_notebooks.server import FAILED, RUNNING, STOPPED, Launcher, Server, free_port, server_key

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "notebooks"


def wait_for(server: Server, timeout: float = 150.0) -> None:
    deadline = time.monotonic() + timeout
    while server.state not in (RUNNING, FAILED, STOPPED) and time.monotonic() < deadline:
        time.sleep(0.2)


def test_free_port_is_free():
    port = free_port()
    assert 1024 < port < 65536


def test_server_key_shares_a_jupyter_root_but_not_a_marimo_file(tmp_path):
    (tmp_path / "a.ipynb").write_text("{}")
    (tmp_path / "b.ipynb").write_text("{}")
    (tmp_path / "x.py").write_text("import marimo\napp = marimo.App()\n")
    (tmp_path / "y.py").write_text("import marimo\napp = marimo.App()\n")
    assert server_key(Notebook(str(tmp_path / "a.ipynb"))) == server_key(Notebook(str(tmp_path / "b.ipynb")))
    assert server_key(Notebook(str(tmp_path / "x.py"))) != server_key(Notebook(str(tmp_path / "y.py")))


def test_missing_notebook_fails_without_starting_anything(tmp_path):
    urls = []
    launcher = Launcher(auto_install=False, start_timeout=10, on_open=urls.append)
    server = launcher.open(Notebook(str(tmp_path / "ghost.ipynb")))
    wait_for(server, 10)
    assert server.state == FAILED
    assert "does not exist" in server.status
    assert server.process is None
    assert urls == []
    assert launcher.live() == []


def test_jupyter_starts_opens_reuses_and_stops(tmp_path):
    pytest.importorskip("jupyterlab")
    shutil.copy(EXAMPLES / "hello.ipynb", tmp_path / "hello.ipynb")
    shutil.copy(EXAMPLES / "hello.ipynb", tmp_path / "second.ipynb")
    urls = []
    launcher = Launcher(auto_install=False, start_timeout=150, on_open=urls.append)
    server = launcher.open(Notebook(str(tmp_path / "hello.ipynb")))
    wait_for(server)
    assert server.state == RUNNING, server.status
    assert urls == [f"http://127.0.0.1:{server.port}/lab/tree/hello.ipynb?token={server.token}"]
    with urllib.request.urlopen(f"http://127.0.0.1:{server.port}/api", timeout=5) as response:
        assert response.status == 200
    assert launcher.open(Notebook(str(tmp_path / "second.ipynb"))) is server
    assert urls[1].endswith(f"/lab/tree/second.ipynb?token={server.token}")
    assert launcher.live() == [server]
    server.stop()
    assert server.state == STOPPED
    assert server.process.poll() is not None
    assert launcher.live() == []
    with pytest.raises(OSError):
        urllib.request.urlopen(f"http://127.0.0.1:{server.port}/api", timeout=2)


def test_marimo_starts_and_stops(tmp_path):
    pytest.importorskip("marimo")
    shutil.copy(EXAMPLES / "hello_marimo.py", tmp_path / "hello_marimo.py")
    urls = []
    launcher = Launcher(auto_install=False, start_timeout=150, on_open=urls.append)
    server = launcher.open(Notebook(str(tmp_path / "hello_marimo.py")))
    wait_for(server)
    assert server.state == RUNNING, server.status
    assert urls == [f"http://127.0.0.1:{server.port}/?access_token={server.token}"]
    with urllib.request.urlopen(f"http://127.0.0.1:{server.port}/health", timeout=5) as response:
        assert response.status == 200
    launcher.stop_all()
    assert server.state == STOPPED
    assert server.process.poll() is not None


def test_a_dead_server_is_replaced_on_the_next_open(tmp_path):
    pytest.importorskip("marimo")
    shutil.copy(EXAMPLES / "hello_marimo.py", tmp_path / "hello_marimo.py")
    launcher = Launcher(auto_install=False, start_timeout=150, on_open=lambda url: True)
    notebook = Notebook(str(tmp_path / "hello_marimo.py"))
    first = launcher.open(notebook)
    wait_for(first)
    assert first.state == RUNNING, first.status
    first.stop()
    second = launcher.open(notebook)
    assert second is not first
    wait_for(second)
    assert second.state == RUNNING, second.status
    launcher.forget(second)
    assert second.state == STOPPED
    assert launcher.servers == {}
