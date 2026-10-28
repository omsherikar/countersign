import json

from tests.conftest import API_ROOT


def _cmd() -> list[str]:
    lines = (API_ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines()
    cmd = next(line for line in lines if line.startswith("CMD "))
    return json.loads(cmd.removeprefix("CMD "))


def test_keep_alive_outlasts_the_web_proxy():
    # uvicorn closes idle connections after 5 s by default; the Next.js proxy reuses
    # sockets for longer and then sees "socket hang up".
    cmd = _cmd()
    assert cmd[:2] == ["uvicorn", "app.main:app"]
    assert "--timeout-keep-alive" in cmd
    assert int(cmd[cmd.index("--timeout-keep-alive") + 1]) == 75
