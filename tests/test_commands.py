"""Command lines and urls, the same on every platform."""

import pytest

from imgui_notebooks.commands import BACKENDS, check_command, install_command, relative_path, server_command, server_url


def test_jupyter_command_is_headless_and_pinned_to_the_port():
    argv = server_command("jupyter", "py", "C:/nb/a.ipynb", "C:/nb", 1234, "tok")
    assert argv[:3] == ["py", "-m", "jupyterlab"]
    assert "--no-browser" in argv
    assert "--ServerApp.port=1234" in argv
    assert "--ServerApp.port_retries=0" in argv
    assert "--ServerApp.root_dir=C:/nb" in argv
    assert "--IdentityProvider.token=tok" in argv


def test_marimo_command_edits_the_file_headless():
    argv = server_command("marimo", "/opt/venv/bin/python", "/nb/app.py", "/nb", 4321, "tok")
    assert argv[:5] == ["/opt/venv/bin/python", "-m", "marimo", "edit", "/nb/app.py"]
    assert "--headless" in argv
    assert argv[argv.index("--port") + 1] == "4321"
    assert argv[argv.index("--token-password") + 1] == "tok"
    assert argv[argv.index("--host") + 1] == "127.0.0.1"


def test_unknown_backend_raises():
    with pytest.raises(ValueError):
        server_command("quarto", "py", "a", "b", 1, "t")
    with pytest.raises(ValueError):
        server_url("quarto", 1, "t")


def test_relative_path_crosses_separators():
    assert relative_path("C:\\nb\\sub\\a.ipynb", "C:/nb") == "sub/a.ipynb"
    assert relative_path("/nb/a.ipynb", "/nb/") == "a.ipynb"
    with pytest.raises(ValueError):
        relative_path("/other/a.ipynb", "/nb")


def test_urls():
    assert server_url("jupyter", 1234, "tok") == "http://127.0.0.1:1234/lab?token=tok"
    assert server_url("jupyter", 1234, "tok", "C:\\nb\\a b.ipynb", "C:/nb") == "http://127.0.0.1:1234/lab/tree/a%20b.ipynb?token=tok"
    assert server_url("marimo", 1234, "tok", "/nb/app.py", "/nb") == "http://127.0.0.1:1234/?access_token=tok"


def test_check_and_install_commands():
    assert check_command("py", "jupyter") == ["py", "-c", "import jupyterlab"]
    assert check_command("py", "marimo") == ["py", "-c", "import marimo"]
    assert install_command("py", "jupyter", use_uv=False) == ["py", "-m", "pip", "install", "jupyterlab"]
    assert install_command("py", "marimo", use_uv=True) == ["uv", "pip", "install", "--python", "py", "marimo"]


def test_backends_registry():
    assert BACKENDS["jupyter"].per_file is False
    assert BACKENDS["marimo"].per_file is True
    assert BACKENDS["jupyter"].ready_path == "/api"
