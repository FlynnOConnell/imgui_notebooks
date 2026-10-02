"""Notebook servers as subprocesses: start one, wait until it answers, open the notebook, stop it.

A :class:`Server` does its whole start on a thread of its own, so a frame only ever reads its
``state``, ``status`` and ``log``. The :class:`Launcher` keeps one server per jupyter root or marimo
file and stops them all when the process exits.
"""

from __future__ import annotations

import atexit
import os
import secrets
import shutil
import signal
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from collections import deque
from typing import Callable

from imgui_notebooks.commands import BACKENDS, check_command, install_command, server_command, server_url
from imgui_notebooks.model import WINDOWS, Notebook
from imgui_notebooks.remote import NO_WINDOW, detect_os, kill_command, shell_command, ssh_run, ssh_server_args

STARTING = "starting"
INSTALLING = "installing"
RUNNING = "running"
STOPPED = "stopped"
FAILED = "failed"
LIVE = (STARTING, INSTALLING, RUNNING)
LOG_LINES = 300

# the server and everything it spawns form one group, so a stop reaches the kernels too
POPEN_GROUP = (
    {"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP}
    if os.name == "nt"
    else {"start_new_session": True}
)


def free_port() -> int:
    """A port nothing on this machine is listening on right now."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def open_in_browser(url: str) -> bool:
    """The default ``on_open``: the system browser, False when this machine has none."""
    return webbrowser.open(url)


def server_key(notebook: Notebook) -> tuple:
    """What one server covers: a jupyter root or a marimo file, on one host with one python."""
    target = notebook.path if BACKENDS[notebook.backend].per_file else notebook.root
    return (notebook.backend, notebook.host.name, notebook.host.python, target)


class Server:
    """One notebook server process, here or behind an ssh tunnel, and what it has printed.

    Parameters
    ----------
    notebook : Notebook
        The first notebook to open; it fixes the backend, host and root.
    auto_install : bool
        Install the server package into the host's python when it is missing.
    start_timeout : float
        Seconds to wait for the server to answer before giving up.
    on_open : callable
        ``on_open(url)`` once the server is up; False back means it could not show it.
    """

    def __init__(self, notebook: Notebook, auto_install: bool, start_timeout: float, on_open: Callable[[str], object]):
        self.backend = notebook.backend
        self.host = notebook.host
        self.path = notebook.path
        self.root = notebook.root
        self.port = free_port()
        self.token = secrets.token_hex(16)
        self.auto_install = auto_install
        self.start_timeout = start_timeout
        self.on_open = on_open
        self.state = STARTING
        self.status = "starting"
        self.log: deque = deque(maxlen=LOG_LINES)
        self.process: subprocess.Popen | None = None
        self.pending = [notebook.path]
        self.stopping = False
        self.lock = threading.Lock()
        self.started_at = time.monotonic()

    @property
    def label(self) -> str:
        return f"{self.backend} on {self.host.label}"

    @property
    def target(self) -> str:
        """What the server serves: the root directory for jupyter, the file for marimo."""
        return self.path if BACKENDS[self.backend].per_file else self.root

    @property
    def url(self) -> str:
        """The server's front page."""
        return server_url(self.backend, self.port, self.token)

    def url_for(self, path: str) -> str:
        """The url that opens ``path`` on this server."""
        return server_url(self.backend, self.port, self.token, path, self.root)

    def last_lines(self, n: int = 5) -> str:
        with self.lock:
            return "\n".join(list(self.log)[-n:])

    def start(self) -> None:
        threading.Thread(target=self.run, name=f"imgui_notebooks {self.label}", daemon=True).start()

    def execute(self, command: list[str], timeout: float) -> subprocess.CompletedProcess:
        """Run ``command`` on the host and wait for it."""
        if self.host.local:
            return subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                creationflags=NO_WINDOW,
            )
        return ssh_run(self.host, shell_command(command, self.host.os), timeout)

    def run(self) -> None:
        """Check the environment, start the process, wait until it answers, open what was asked for."""
        backend = BACKENDS[self.backend]
        host = self.host
        try:
            if host.local and not os.path.exists(self.path):
                raise FileNotFoundError(f"{self.path} does not exist on this machine")
            if not host.os:
                self.status = f"connecting to {host.label}"
                host.os = detect_os(host)
            python = host.executable
            self.status = f"checking {backend.module} for {python} on {host.label}"
            if self.execute(check_command(python, self.backend), 120).returncode != 0:
                if not self.auto_install:
                    raise RuntimeError(f"{backend.package} is not installed for {python} on {host.label}")
                self.state = INSTALLING
                self.status = f"installing {backend.package} for {python} on {host.label}"
                use_uv = host.local and shutil.which("uv") is not None
                result = self.execute(install_command(python, self.backend, use_uv), 1800)
                if result.returncode != 0:
                    raise RuntimeError(f"installing {backend.package} failed: {(result.stdout + result.stderr).strip()[-400:]}")
                self.state = STARTING
            command = server_command(self.backend, python, self.path, self.root, self.port, self.token)
            self.status = f"starting {self.backend} on {host.label}"
            if host.local:
                self.process = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=self.root,
                    **POPEN_GROUP,
                )
            else:
                # stdin stays open: an EOF on the pty would end the remote session
                self.process = subprocess.Popen(
                    ssh_server_args(host, self.port, shell_command(command, host.os)),
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=NO_WINDOW,
                )
            threading.Thread(target=self.read_log, name=f"imgui_notebooks log {self.port}", daemon=True).start()
            ready_url = f"http://127.0.0.1:{self.port}{backend.ready_path}"
            deadline = time.monotonic() + self.start_timeout
            while True:
                if self.process.poll() is not None:
                    raise RuntimeError(f"{self.backend} exited with code {self.process.returncode}\n{self.last_lines()}")
                if time.monotonic() > deadline:
                    self.stop()
                    raise TimeoutError(f"{self.backend} did not answer within {self.start_timeout:.0f}s\n{self.last_lines()}")
                try:
                    urllib.request.urlopen(ready_url, timeout=2).close()
                    break
                except urllib.error.HTTPError:
                    break
                except (urllib.error.URLError, OSError):
                    time.sleep(0.3)
            with self.lock:
                self.state = RUNNING
                self.status = f"running, {self.url}"
                paths, self.pending = self.pending, []
            for path in paths:
                self.show(path)
        except Exception as exc:
            with self.lock:
                self.state = FAILED
                self.status = str(exc)

    def show(self, path: str) -> None:
        """Hand ``path``'s url to ``on_open``, noting on the status line when nothing could show it."""
        url = self.url_for(path)
        if self.on_open(url) is False:
            self.status = f"no browser here, copy the url: {url}"

    def open(self, path: str) -> None:
        """Open ``path`` now, or as soon as the server answers."""
        with self.lock:
            if self.state != RUNNING:
                self.pending.append(path)
                return
        self.show(path)

    def read_log(self) -> None:
        """Keep the last lines the process printed; runs until it exits."""
        for line in self.process.stdout:
            with self.lock:
                self.log.append(line.rstrip("\r\n"))
        code = self.process.wait()
        with self.lock:
            if self.state == RUNNING:
                self.state = STOPPED if self.stopping else FAILED
                self.status = "stopped" if self.stopping else f"exited with code {code}"

    def stop(self) -> None:
        """Stop the server and, over ssh, the remote process behind the tunnel."""
        self.stopping = True
        process = self.process
        if process is None or process.poll() is not None:
            with self.lock:
                self.state = STOPPED
                self.status = "stopped"
            return
        if not self.host.local:
            process.terminate()
            threading.Thread(target=self.kill_remote, daemon=True).start()
        elif self.host.os == WINDOWS:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True, creationflags=NO_WINDOW)
        else:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            try:
                process.wait(10)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        process.wait(30)
        with self.lock:
            self.state = STOPPED
            self.status = "stopped"

    def kill_remote(self) -> None:
        """Best effort: the pty already hung the remote server up, this catches one that ignored it."""
        try:
            result = ssh_run(self.host, kill_command(self.host.os, self.token), 60)
            line = f"remote stop exited with {result.returncode} {result.stderr.strip()}".strip()
        except (OSError, subprocess.TimeoutExpired) as exc:
            line = f"remote stop failed: {exc}"
        with self.lock:
            self.log.append(line)


class Launcher:
    """Every server started from this process, one per jupyter root or marimo file, stopped together at exit.

    Parameters
    ----------
    auto_install : bool
        Install a missing server package into the host's python before starting.
    start_timeout : float
        Seconds a server gets to answer.
    on_open : callable | None
        ``on_open(url)`` when a notebook is ready; the system browser when None.
    """

    def __init__(self, auto_install: bool = True, start_timeout: float = 90.0, on_open: Callable[[str], object] | None = None):
        self.auto_install = auto_install
        self.start_timeout = start_timeout
        self.on_open = on_open or open_in_browser
        self.servers: dict[tuple, Server] = {}
        atexit.register(self.stop_all)

    def open(self, notebook: Notebook) -> Server:
        """Open ``notebook`` on the server that covers it, starting one when there is none."""
        if notebook.backend not in BACKENDS:
            raise ValueError(f"{notebook.path} is not a jupyter or marimo notebook")
        key = server_key(notebook)
        server = self.servers.get(key)
        if server is not None and server.state in LIVE:
            server.open(notebook.path)
            return server
        server = Server(notebook, self.auto_install, self.start_timeout, self.on_open)
        self.servers[key] = server
        server.start()
        return server

    def live(self) -> list[Server]:
        """The servers that are starting or running, oldest first."""
        return [server for server in self.servers.values() if server.state in LIVE]

    def forget(self, server: Server) -> None:
        """Drop a stopped or failed server from the list."""
        if server.state in LIVE:
            server.stop()
        self.servers = {key: s for key, s in self.servers.items() if s is not server}

    def stop_all(self) -> None:
        for server in self.live():
            server.stop()
