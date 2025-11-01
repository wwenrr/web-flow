#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional
import json


def load_workflow_mapping(project_root: Path) -> dict[str, dict[str, str]]:
    mapping_path = project_root / "src" / "workflows" / "workflow_ids.json"
    if not mapping_path.exists():
        raise FileNotFoundError(f"Mapping file not found: {mapping_path}")
    return json.loads(mapping_path.read_text(encoding="utf-8"))


def resolve_workflow_root(project_root: Path, module_name: str) -> Path:
    # Convert module to file path under workspace/src and return its parent directory
    # Example: src.workflows.login_bao_tang_truyen_tranh.login_workflow ->
    #   <root>/src/workflows/login_bao_tang_truyen_tranh/login_workflow.py (parent dir is the workflow root)
    parts = module_name.split(".")
    if parts and parts[0] == "src":
        parts = parts[1:]
    rel = Path(*parts)
    if not (module_name.startswith("src.workflows.")):
        raise ValueError(f"Unsupported module namespace: {module_name}")
    module_file = project_root / "src" / rel.with_suffix(".py")
    if not module_file.exists():
        # Try package directory module (e.g., __init__.py removed); resolve closest existing parent
        probe = module_file
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        if not probe.exists():
            raise FileNotFoundError(f"Cannot resolve module path for {module_name} at {module_file}")
        base = probe
    else:
        base = module_file

    # Store under the module's directory (exact workflow package folder)
    return base.parent


def find_local_resources_dir(workflow_root: Path, override: Optional[Path]) -> Path:
    if override:
        d = override
        if not d.exists() or not d.is_dir():
            raise FileNotFoundError(f"Provided resource dir not found: {d}")
        return d

    # Search for local_resources under workflow_root recursively
    candidates = []
    for p in workflow_root.rglob("local_resources"):
        if p.is_dir():
            candidates.append(p)
    if not candidates:
        raise FileNotFoundError(f"No local_resources directory found under {workflow_root}")
    # Prefer shortest path (closest to root)
    candidates.sort(key=lambda x: len(x.parts))
    return candidates[0]


def iter_files_recursive(root: Path):
    for p in root.rglob("*"):
        if p.is_file():
            yield p


def get_encryption_key(cli_key: Optional[str]) -> str:
    if cli_key:
        return cli_key
    env_key = os.environ.get("LOCAL_ENCRYPTION_KEY")
    if not env_key:
        raise RuntimeError(
            "Encryption key not provided. Set $LOCAL_ENCRYPTION_KEY or pass --key."
        )
    return env_key


def openssl_encrypt_file(src: Path, dst: Path, key: str) -> None:
    dst_tmp = dst.with_suffix(dst.suffix + ".tmp")
    cmd = [
        "openssl",
        "enc",
        "-aes-256-cbc",
        "-salt",
        "-pbkdf2",
        "-in",
        str(src),
        "-out",
        str(dst_tmp),
        "-pass",
        f"pass:{key}",
    ]
    subprocess.run(cmd, check=True)
    dst_tmp.replace(dst)


def main() -> None:
    parser = argparse.ArgumentParser(description="Encrypt local resources for a workflow")
    parser.add_argument("--workflow-id", required=True, dest="workflow_id")
    parser.add_argument("--resource-dir", dest="resource_dir", default=None, help="Override local_resources directory path")
    parser.add_argument("--key", dest="key", default=None, help="Encryption key; if omitted, uses $LOCAL_ENCRYPTION_KEY")
    args = parser.parse_args()

    # Resolve project root (repo root). This file lives at <root>/src/tools/...
    # parents[0]=tools, [1]=src, [2]=<root>
    project_root = Path(__file__).resolve().parents[2]
    mapping = load_workflow_mapping(project_root)
    info = mapping.get(args.workflow_id)
    if not info:
        print(f"Unknown workflow id: {args.workflow_id}", file=sys.stderr)
        sys.exit(1)

    module_name = info.get("module")
    if not module_name:
        print(f"Invalid mapping entry for {args.workflow_id}", file=sys.stderr)
        sys.exit(1)

    workflow_root = resolve_workflow_root(project_root, module_name)
    resource_dir = find_local_resources_dir(workflow_root, Path(args.resource_dir) if args.resource_dir else None)

    # Output directory: <workflow_root>/data/enc (store inside workflow's data directory)
    output_root = workflow_root / "resources" / "enc"
    output_root.mkdir(parents=True, exist_ok=True)

    key = get_encryption_key(args.key)

    total = 0
    skipped = 0
    for item in iter_files_recursive(resource_dir):
        # Flatten: write directly into <workflow_root>/data without subdirectories
        dst_dir = output_root
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / (item.name + ".enc")
        if dst.exists():
            skipped += 1
            continue
        openssl_encrypt_file(item, dst, key)
        total += 1

    print("=== Encrypt Local Resources ===")
    print(f"Workflow ID : {args.workflow_id}")
    print(f"Module      : {module_name}")
    print(f"Workflow dir: {workflow_root}")
    print(f"Resources   : {resource_dir}")
    print(f"Output dir  : {output_root}")
    print(f"Key        : {key}")
    print(f"Encrypted   : {total} file(s); skipped (already .enc): {skipped}")


if __name__ == "__main__":
    main()


