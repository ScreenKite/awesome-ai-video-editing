#!/usr/bin/env python3
"""Tiny ScreenKite CLI helper: call a tool against --project and parse JSON."""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

DEFAULT_SK = "/usr/local/bin/screenkite"


def parse_json_stdout(stdout: str):
    """ScreenKite often prefixes JSON with SwiftMCP log lines."""
    text = stdout.strip()
    if not text:
        return {}
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise json.JSONDecodeError("no JSON object in CLI stdout", text, 0)


def sk_call(
    name: str,
    payload: dict | None,
    project: str,
    sk: str = DEFAULT_SK,
) -> dict:
    cmd = [sk, "tool", "call", "--name", name, "--project", project, "--json"]
    tmp_path = None
    if payload is not None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(payload, f)
            tmp_path = f.name
        cmd.extend(["--input-file", tmp_path])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"{name} failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    try:
        data = parse_json_stdout(result.stdout)
    except json.JSONDecodeError:
        return {"raw": result.stdout}
    if isinstance(data, dict):
        return data
    return {"data": data}


def project_revision(project: str, sk: str = DEFAULT_SK) -> str:
    state = sk_call("stat", {"scope": "summary"}, project, sk=sk)
    rev = state.get("projectRevision")
    if not rev:
        raise RuntimeError(f"stat did not return projectRevision: {state}")
    return rev
