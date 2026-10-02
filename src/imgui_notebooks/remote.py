"""Another machine over ssh: one-off commands, the port-forwarded server, and what differs per platform.

Windows hosts get every command as a ``powershell -EncodedCommand``, so neither cmd nor pwsh as the
sshd default shell gets to parse it. Posix hosts get ``shlex`` quoting.
"""

from __future__ import annotations

import base64
import os
import shlex
import subprocess

from imgui_notebooks.model import DARWIN, LINUX, MARIMO_MARKER, WINDOWS, Host

NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
SSH_OPTIONS = ("-o", "BatchMode=yes", "-o", "ServerAliveInterval=30")


def powershell_command(script: str) -> str:
    """``script`` as a powershell invocation no remote shell has to quote."""
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return f"powershell -NoProfile -NonInteractive -EncodedCommand {encoded}"


def powershell_literal(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def shell_command(args: list[str], os_name: str) -> str:
    """``args`` as one command line for a host of ``os_name``."""
    if os_name != WINDOWS:
        return shlex.join(args)
    return powershell_command("& " + " ".join(powershell_literal(arg) for arg in args))


def list_command(directory: str, os_name: str, recursive: bool) -> str:
    """Prints the ``.ipynb`` files and the marimo ``.py`` files under ``directory``, one path per line."""
    if os_name == WINDOWS:
        recurse = " -Recurse" if recursive else ""
        folder = powershell_literal(directory)
        return powershell_command(
            f"Get-ChildItem -LiteralPath {folder} -File -Filter '*.ipynb'{recurse}"
            " | Where-Object { $_.FullName -notlike '*\\.ipynb_checkpoints\\*' }"
            " | ForEach-Object { $_.FullName }; "
            f"Get-ChildItem -LiteralPath {folder} -File -Filter '*.py'{recurse}"
            " | Select-String -SimpleMatch -Pattern " + powershell_literal(MARIMO_MARKER) + " -List"
            " | ForEach-Object { $_.Path }"
        )
    folder = shlex.quote(directory)
    marker = shlex.quote(MARIMO_MARKER)
    depth = "" if recursive else " -maxdepth 1"
    notebooks = f"find {folder}{depth} -name '*.ipynb' -not -path '*/.ipynb_checkpoints/*'"
    if recursive:
        apps = f"grep -r -l -F --include='*.py' {marker} {folder}"
    else:
        apps = f"grep -l -F {marker} {folder}/*.py"
    return f"{notebooks}; {apps} 2>/dev/null; true"


def kill_command(os_name: str, token: str) -> str:
    """Stops every process on the host whose command line carries ``token``, which only our server's does."""
    if os_name == WINDOWS:
        return powershell_command(
            "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "
            + powershell_literal(f"*{token}*")
            + " } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
        )
    return f"pkill -f {shlex.quote(token)}"


def ssh_server_args(host: Host, port: int, command: str) -> list[str]:
    """The argv that runs ``command`` on ``host`` with the host's ``port`` forwarded to the same port here.

    The pty (``-tt``) is what makes the remote server die with the ssh session.
    """
    return [
        "ssh",
        "-tt",
        *SSH_OPTIONS,
        "-o",
        "ExitOnForwardFailure=yes",
        "-L",
        f"{port}:127.0.0.1:{port}",
        host.name,
        command,
    ]


def ssh_run(host: Host, command: str, timeout: float) -> subprocess.CompletedProcess:
    """Run ``command`` on ``host`` and wait for it. Exit code 255 is ssh itself failing."""
    return subprocess.run(
        ["ssh", *SSH_OPTIONS, host.name, command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=NO_WINDOW,
    )


def detect_os(host: Host) -> str:
    """The platform of ``host``, from what ``uname`` says there; a host without one is Windows."""
    result = ssh_run(host, "uname -s", 30)
    if result.returncode == 255:
        raise ConnectionError(f"ssh {host.name}: {result.stderr.strip() or 'connection failed'}")
    name = result.stdout.strip().lower()
    if name.startswith("linux"):
        return LINUX
    if name.startswith("darwin"):
        return DARWIN
    return WINDOWS
