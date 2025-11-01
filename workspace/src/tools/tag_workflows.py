from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Dict


class WorkflowTagger:
    """
    Utility to assign stable UUIDs to workflow classes discovered under src/workflows.
    It scans for files named *workflow.py and attempts to import them to find classes
    that end with "Pipeline". The result mapping is written to src/workflows/workflow_ids.json.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.src_dir = project_root / "src"
        self.workflows_dir = self.src_dir / "workflows"
        self.mapping_path = self.workflows_dir / "workflow_ids.json"

    def run(self) -> None:
        discoverer = _WorkflowDiscoveryHelper(self)
        discoverer.setup_paths()
        existing = discoverer.load_existing_mapping()
        by_target = discoverer.build_target_to_uuid_map(existing)
        discovered = discoverer.discover_workflows(by_target, existing)
        discoverer.persist_mapping(existing, discovered)


class _WorkflowDiscoveryHelper:
    """
    Helper class for discovering and tagging workflow classes.
    """

    def __init__(self, tagger: WorkflowTagger) -> None:
        self.tagger = tagger

    def setup_paths(self) -> None:
        sys.path.insert(0, str(self.tagger.project_root))
        sys.path.insert(0, str(self.tagger.src_dir))

    def load_existing_mapping(self) -> Dict[str, Dict[str, str]]:
        if not self.tagger.mapping_path.exists():
            return {}
        return json.loads(self.tagger.mapping_path.read_text(encoding="utf-8"))

    def build_target_to_uuid_map(self, existing: Dict[str, Dict[str, str]]) -> Dict[str, str]:
        return {f"{v['module']}#{v['class']}": k for k, v in existing.items()}

    def discover_workflows(
        self, by_target: Dict[str, str], existing: Dict[str, Dict[str, str]]
    ) -> Dict[str, Dict[str, str]]:
        discovered: Dict[str, Dict[str, str]] = {}
        existing_modules: set[str] = {v.get("module", "") for v in existing.values()}

        for py_file in self.tagger.workflows_dir.rglob("*workflow.py"):
            rel_module = self._get_module_path(py_file)
            print(f"[tag] scan: {py_file}")
            print(f"[tag] module: {rel_module}")
            module = self._import_module(rel_module)
            if not module:
                print(f"[tag] skip (import failed): {rel_module}")
                continue

            workflows = self._extract_pipeline_classes(module, rel_module)
            print(f"[tag] found pipelines: {[w['class'] for w in workflows]} ")
            for workflow_info in workflows:
                # Skip if module already exists (avoid duplicates by module)
                if workflow_info["module"] in existing_modules or any(
                    workflow_info["module"] == v.get("module", "") for v in discovered.values()
                ):
                    print(
                        f"[tag] skip (module already exists): {workflow_info['module']} -> {workflow_info['class']}"
                    )
                    continue
                wf_id = self._get_or_generate_uuid(workflow_info, by_target)
                if self._should_skip_existing(wf_id, existing):
                    print(f"[tag] skip existing id: {wf_id} -> {workflow_info['class']}")
                    continue
                discovered[wf_id] = workflow_info
                print(f"[tag] add id: {wf_id} -> {workflow_info['class']}")

        return discovered

    def _get_module_path(self, py_file: Path) -> str:
        relative = py_file.relative_to(self.tagger.src_dir)
        module_str = str(relative).replace("/", ".").removesuffix(".py")
        return f"src.{module_str}"

    def _import_module(self, rel_module: str) -> object | None:
        try:
            return __import__(rel_module, fromlist=["*"])
        except Exception as e:
            print(f"Warning: Failed to import {rel_module}: {e}")
            return None

    def _extract_pipeline_classes(self, module: object, rel_module: str) -> list[Dict[str, str]]:
        workflows = []
        for attr in dir(module):
            if not attr.endswith("Pipeline"):
                continue
            obj = getattr(module, attr)
            if not isinstance(obj, type):
                continue
            workflows.append({"module": rel_module, "class": attr})
        return workflows

    def _get_or_generate_uuid(self, workflow_info: Dict[str, str], by_target: Dict[str, str]) -> str:
        target_key = f"{workflow_info['module']}#{workflow_info['class']}"
        return by_target.get(target_key) or str(uuid.uuid4())

    def _should_skip_existing(self, wf_id: str, existing: Dict[str, Dict[str, str]]) -> bool:
        return wf_id in existing

    def persist_mapping(
        self, existing: Dict[str, Dict[str, str]], discovered: Dict[str, Dict[str, str]]
    ) -> None:
        merged = dict(existing)
        merged.update(discovered)
        print(f"[tag] discovered total: {len(discovered)}; existing: {len(existing)}; merged: {len(merged)}")
        self.tagger.mapping_path.parent.mkdir(parents=True, exist_ok=True)
        self.tagger.mapping_path.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[tag] wrote mapping: {self.tagger.mapping_path}")


if __name__ == "__main__":
    # Execute tagging when run as a module: `python -m src.tools.tag_workflows`
    WorkflowTagger(Path.cwd()).run()
