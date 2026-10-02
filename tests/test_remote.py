"""What goes over ssh, per platform. Nothing here connects anywhere."""

import base64

from imgui_notebooks.model import DARWIN, LINUX, WINDOWS, Host
from imgui_notebooks.remote import kill_command, list_command, powershell_command, shell_command, ssh_server_args


def decode(command: str) -> str:
    """The script inside a ``powershell -EncodedCommand``."""
    assert command.startswith("powershell -NoProfile -NonInteractive -EncodedCommand ")
    return base64.b64decode(command.rsplit(" ", 1)[1]).decode("utf-16-le")


def test_posix_commands_are_shlex_quoted():
    assert shell_command(["/opt/venv/bin/python", "-m", "marimo", "edit", "it's.py"], LINUX) == "/opt/venv/bin/python -m marimo edit 'it'\"'\"'s.py'"
    assert shell_command(["a", "b c"], DARWIN) == "a 'b c'"


def test_windows_commands_are_encoded_powershell():
    script = decode(shell_command(["C:\\envs\\x\\Scripts\\python.exe", "-m", "jupyterlab", "--ServerApp.root_dir=C:\\it's"], WINDOWS))
    assert script == "& 'C:\\envs\\x\\Scripts\\python.exe' '-m' 'jupyterlab' '--ServerApp.root_dir=C:\\it''s'"
    assert decode(powershell_command("Get-Date")) == "Get-Date"


def test_list_commands():
    posix = list_command("/home/u/nb", LINUX, recursive=False)
    assert "find /home/u/nb -maxdepth 1 -name '*.ipynb'" in posix
    assert "grep -l -F 'marimo.App(' /home/u/nb/*.py" in posix
    deep = list_command("/home/u/nb", LINUX, recursive=True)
    assert "-maxdepth" not in deep
    assert "grep -r -l -F --include='*.py'" in deep
    script = decode(list_command("C:\\nb", WINDOWS, recursive=True))
    assert "Get-ChildItem -LiteralPath 'C:\\nb' -File -Filter '*.ipynb' -Recurse" in script
    assert "Select-String -SimpleMatch -Pattern 'marimo.App(' -List" in script
    assert "-Recurse" not in decode(list_command("C:\\nb", WINDOWS, recursive=False))


def test_kill_commands_target_the_token():
    assert kill_command(LINUX, "abc123") == "pkill -f abc123"
    assert "'*abc123*'" in decode(kill_command(WINDOWS, "abc123"))
    assert "Stop-Process" in decode(kill_command(WINDOWS, "abc123"))


def test_ssh_server_args_forward_the_same_port():
    argv = ssh_server_args(Host("lab4", os=LINUX), 5050, "python3 -m jupyterlab")
    assert argv[0] == "ssh"
    assert "-tt" in argv
    assert argv[argv.index("-L") + 1] == "5050:127.0.0.1:5050"
    assert "BatchMode=yes" in argv
    assert "ExitOnForwardFailure=yes" in argv
    assert argv[-2:] == ["lab4", "python3 -m jupyterlab"]
