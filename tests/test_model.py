"""Hosts, notebooks and backend detection: pure, no imgui context."""

import sys

from imgui_notebooks.model import DARWIN, JUPYTER, LINUX, MARIMO, WINDOWS, Host, Notebook, detect_backend, backend_of_name, local_os, split_path


def test_split_path_handles_both_separators():
    assert split_path("C:\\nb\\a.ipynb") == ("C:/nb", "a.ipynb")
    assert split_path("/home/u/nb/a.py") == ("/home/u/nb", "a.py")
    assert split_path("/a.py") == ("/", "a.py")
    assert split_path("a.py") == ("", "a.py")


def test_backend_of_name():
    assert backend_of_name("a.IPYNB") == JUPYTER
    assert backend_of_name("a.py") == MARIMO
    assert backend_of_name("a.txt") == ""


def test_detect_backend_reads_marimo_marker(tmp_path):
    (tmp_path / "nb.ipynb").write_text("{}")
    (tmp_path / "app.py").write_text("import marimo\napp = marimo.App()\n")
    (tmp_path / "plain.py").write_text("print('hi')\n")
    assert detect_backend(str(tmp_path / "nb.ipynb")) == JUPYTER
    assert detect_backend(str(tmp_path / "app.py")) == MARIMO
    assert detect_backend(str(tmp_path / "plain.py")) == ""
    assert detect_backend(str(tmp_path / "x.txt")) == ""


def test_local_host_defaults():
    host = Host()
    assert host.local
    assert host.os == local_os()
    assert host.executable == sys.executable
    assert host.label == "this machine"


def test_remote_host_python_resolution():
    assert Host("lab4", os=LINUX).executable == "python3"
    assert Host("lab4", os=WINDOWS).executable == "python"
    assert Host("lab4", "/opt/venv", os=LINUX).executable == "/opt/venv/bin/python"
    assert Host("lab4", "/opt/venv/", os=DARWIN).executable == "/opt/venv/bin/python"
    assert Host("lab4", "C:\\envs\\x", os=WINDOWS).executable == "C:\\envs\\x\\Scripts\\python.exe"
    assert Host("lab4", "C:\\envs\\x\\Scripts\\python.exe", os=WINDOWS).executable == "C:\\envs\\x\\Scripts\\python.exe"
    assert Host("lab4", "/usr/bin/python3.12", os=LINUX).executable == "/usr/bin/python3.12"
    assert Host(" lab4 ", os=LINUX).name == "lab4"
    assert not Host("lab4", os=LINUX).local


def test_notebook_fills_backend_label_and_root(tmp_path):
    path = tmp_path / "nb.ipynb"
    path.write_text("{}")
    notebook = Notebook(str(path))
    assert notebook.backend == JUPYTER
    assert notebook.label == "nb.ipynb"
    assert notebook.root == str(tmp_path).replace("\\", "/")


def test_remote_notebook_uses_the_suffix():
    notebook = Notebook("C:\\nb\\app.py", host=Host("box", os=WINDOWS))
    assert notebook.backend == MARIMO
    assert notebook.root == "C:/nb"
    assert Notebook('"/srv/nb/a.ipynb"', host=Host("box", os=LINUX)).path == "/srv/nb/a.ipynb"
