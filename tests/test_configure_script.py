"""Test dello script di configurazione locale."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "configure.sh"


def _environment(config: Path) -> dict[str, str]:
    environment = os.environ.copy()
    for name in (
        "WIKI_ROOT",
        "WIKI_MCP_TOKEN",
        "WIKI_HTTPS_ENABLED",
        "WIKI_HTTP_HOST",
        "WIKI_HTTP_PORT",
        "WIKI_MCP_URL",
        "WIKI_TLS_CERT",
        "WIKI_TLS_KEY",
    ):
        environment.pop(name, None)
    environment["WIKI_CONFIG_FILE"] = str(config)
    environment["NO_COLOR"] = "1"
    return environment


def _source_value(config: Path, name: str) -> str:
    result = subprocess.run(
        ["bash", "-c", f'source "$1"; printf %s "${{{name}}}"', "bash", str(config)],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_configure_selects_root_and_generates_token(tmp_path: Path) -> None:
    config = tmp_path / "config" / ".wiki-kiss.env"
    wiki = tmp_path / "private-wiki"
    result = subprocess.run(
        [str(SCRIPT), "--root", str(wiki), "--https", "off", "--no-apply"],
        env=_environment(config),
        check=True,
        capture_output=True,
        text=True,
    )

    assert wiki.is_dir()
    assert stat.S_IMODE(wiki.stat().st_mode) == 0o700
    assert config.is_file()
    assert stat.S_IMODE(config.stat().st_mode) == 0o600
    assert _source_value(config, "WIKI_ROOT") == str(wiki.resolve())
    token = _source_value(config, "WIKI_MCP_TOKEN")
    assert len(token) == 64
    assert f"WIKI_MCP_TOKEN={token}" in result.stdout
    assert _source_value(config, "WIKI_HTTPS_ENABLED") == "0"


def test_show_and_rotate_token(tmp_path: Path) -> None:
    config = tmp_path / ".wiki-kiss.env"
    environment = _environment(config)
    subprocess.run(
        [str(SCRIPT), "--root", str(tmp_path / "wiki"), "--no-apply"],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    first = _source_value(config, "WIKI_MCP_TOKEN")

    subprocess.run(
        [str(SCRIPT), "--rotate-token", "--no-apply"],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    second = _source_value(config, "WIKI_MCP_TOKEN")
    assert second != first

    shown = subprocess.run(
        [str(SCRIPT), "--show-token"],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    assert shown.stdout.strip().endswith(second)


def test_https_configuration_saves_public_url(tmp_path: Path) -> None:
    config = tmp_path / ".wiki-kiss.env"
    certificate = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    certificate.write_text("test certificate", encoding="utf-8")
    key.write_text("test key", encoding="utf-8")
    subprocess.run(
        [
            str(SCRIPT),
            "--root",
            str(tmp_path / "wiki"),
            "--https",
            "on",
            "--host",
            "0.0.0.0",
            "--url",
            "https://wiki.example.com/mcp",
            "--cert",
            str(certificate),
            "--key",
            str(key),
            "--no-apply",
        ],
        env=_environment(config),
        check=True,
        capture_output=True,
        text=True,
    )
    assert _source_value(config, "WIKI_HTTPS_ENABLED") == "1"
    assert _source_value(config, "WIKI_MCP_URL") == "https://wiki.example.com/mcp"


def test_https_requires_certificate_and_key(tmp_path: Path) -> None:
    config = tmp_path / ".wiki-kiss.env"
    result = subprocess.run(
        [
            str(SCRIPT),
            "--root",
            str(tmp_path / "wiki"),
            "--https",
            "on",
            "--no-apply",
        ],
        env=_environment(config),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "servono --cert e --key" in result.stderr
    assert not config.exists()
