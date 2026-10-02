"""Command lines and urls for each notebook backend, the same on every platform."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

from imgui_notebooks.model import JUPYTER, MARIMO


@dataclass(frozen=True)
class Backend:
    """One way of serving notebooks: jupyter or marimo.

    Parameters
    ----------
    package : str
        What pip installs.
    module : str
        What must import for the server to run.
    per_file : bool
        One server per notebook, as marimo, rather than one per directory, as jupyter.
    ready_path : str
        Url path that answers once the server is up.
    """

    name: str
    package: str
    module: str
    per_file: bool
    ready_path: str


BACKENDS = {
    JUPYTER: Backend(JUPYTER, "jupyterlab", "jupyterlab", False, "/api"),
    MARIMO: Backend(MARIMO, "marimo", "marimo", True, "/health"),
}


def relative_path(path: str, root: str) -> str:
    """``path`` relative to ``root`` with forward slashes, whatever platform wrote them."""
    normalized = path.replace("\\", "/")
    prefix = root.replace("\\", "/").rstrip("/") + "/"
    if not normalized.startswith(prefix):
        raise ValueError(f"{path} is not under {root}")
    return normalized[len(prefix) :]


def server_command(backend: str, python: str, path: str, root: str, port: int, token: str) -> list[str]:
    """The argv that serves ``path`` on ``127.0.0.1:port`` behind ``token``, without opening a browser."""
    if backend == JUPYTER:
        return [
            python,
            "-m",
            "jupyterlab",
            "--no-browser",
            "--ServerApp.ip=127.0.0.1",
            f"--ServerApp.port={port}",
            "--ServerApp.port_retries=0",
            f"--ServerApp.root_dir={root}",
            f"--IdentityProvider.token={token}",
        ]
    if backend == MARIMO:
        return [
            python,
            "-m",
            "marimo",
            "edit",
            path,
            "--headless",
            "--no-sandbox",
            "--skip-update-check",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--token-password",
            token,
        ]
    raise ValueError(f"unknown notebook backend {backend!r}")


def server_url(backend: str, port: int, token: str, path: str = "", root: str = "") -> str:
    """The url that opens ``path`` on a server started by :func:`server_command`; the server's front page when ``path`` is empty."""
    if backend == JUPYTER:
        if not path:
            return f"http://127.0.0.1:{port}/lab?token={token}"
        return f"http://127.0.0.1:{port}/lab/tree/{quote(relative_path(path, root))}?token={token}"
    if backend == MARIMO:
        return f"http://127.0.0.1:{port}/?access_token={token}"
    raise ValueError(f"unknown notebook backend {backend!r}")


def check_command(python: str, backend: str) -> list[str]:
    """Exits 0 when ``python`` can run servers of ``backend``."""
    return [python, "-c", f"import {BACKENDS[backend].module}"]


def install_command(python: str, backend: str, use_uv: bool) -> list[str]:
    """Installs what ``backend`` needs into ``python``'s environment, through uv when it is on this machine."""
    package = BACKENDS[backend].package
    if use_uv:
        return ["uv", "pip", "install", "--python", python, package]
    return [python, "-m", "pip", "install", package]
