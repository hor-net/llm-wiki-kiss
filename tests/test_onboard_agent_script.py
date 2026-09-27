"""Test della generazione di Agent Skills personalizzate."""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIGURE = ROOT / "scripts" / "configure.sh"
ONBOARD = ROOT / "scripts" / "onboard-agent.sh"


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


def _configure_local(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    config = tmp_path / ".wiki-kiss.env"
    wiki = tmp_path / "customer-wiki"
    environment = _environment(config)
    subprocess.run(
        [str(CONFIGURE), "--root", str(wiki), "--https", "off", "--no-apply"],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return config, wiki, environment


def test_onboarding_generates_protected_local_skill(tmp_path: Path) -> None:
    _config, wiki, environment = _configure_local(tmp_path)
    target = tmp_path / "skills"
    result = subprocess.run(
        [
            str(ONBOARD),
            "--name",
            "customer-knowledge",
            "--label",
            "Customer Knowledge",
            "--mode",
            "local",
            "--target",
            str(target),
        ],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    skill = target / "customer-knowledge"
    connection_path = skill / "references" / "connection.json"
    mcp_path = skill / "references" / "mcp-config.json"
    assert (skill / "SKILL.md").is_file()
    assert connection_path.is_file()
    assert stat.S_IMODE(connection_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(skill.stat().st_mode) == 0o700

    connection = json.loads(connection_path.read_text(encoding="utf-8"))
    assert connection["mode"] == "local"
    assert connection["wiki_root"] == str(wiki.resolve())
    assert len(connection["bearer_token"]) == 64
    assert connection["mcp_url"] is None

    mcp = json.loads(mcp_path.read_text(encoding="utf-8"))["mcpServers"]
    assert mcp["customer-knowledge"]["args"][-1] == str(wiki.resolve())
    assert "SKILL_PATH=" in result.stdout

    # La sostituzione richiede consenso esplicito.
    duplicate = subprocess.run(
        [str(ONBOARD), "--name", "customer-knowledge", "--target", str(target)],
        env=environment,
        capture_output=True,
        text=True,
    )
    assert duplicate.returncode == 1
    assert "--force" in duplicate.stderr


def test_onboarding_auto_uses_https_url_and_token(tmp_path: Path) -> None:
    config = tmp_path / ".wiki-kiss.env"
    wiki = tmp_path / "wiki"
    certificate = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    certificate.write_text("certificate", encoding="utf-8")
    key.write_text("key", encoding="utf-8")
    environment = _environment(config)
    subprocess.run(
        [
            str(CONFIGURE),
            "--root",
            str(wiki),
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
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    target = tmp_path / "skills"
    subprocess.run(
        [str(ONBOARD), "--name", "remote-wiki", "--target", str(target)],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    skill = target / "remote-wiki"
    connection = json.loads(
        (skill / "references" / "connection.json").read_text(encoding="utf-8")
    )
    mcp = json.loads(
        (skill / "references" / "mcp-config.json").read_text(encoding="utf-8")
    )["mcpServers"]["remote-wiki"]

    assert connection["mode"] == "https"
    assert connection["mcp_url"] == "https://wiki.example.com/mcp"
    assert mcp["url"] == "https://wiki.example.com/mcp"
    assert mcp["headers"]["Authorization"] == f"Bearer {connection['bearer_token']}"
