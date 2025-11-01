from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Callable, Optional, Type

from src.common.base.singleton import Singleton


class WorkflowRegistry(Singleton):
    """
    Singleton registry for resolving workflow ids to workflow classes.
    Mapping file: src/workflows/workflow_ids.json with items:
      { "<uuid>": {"module": "src.workflows.pkg.module", "class": "ClassName"}, ... }
    """

    def __init__(self) -> None:
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True
        self._mapping_path: Path = Path(__file__).with_name("workflow_ids.json")
        self._cache: dict[str, dict[str, str]] = {}
        self._load_mapping()

    def _load_mapping(self) -> None:
        if self._mapping_path.exists():
            with open(self._mapping_path, "r", encoding="utf-8") as f:
                self._cache = json.load(f)
        else:
            self._cache = {}

    def get_workflow_class(self, workflow_id: str) -> Optional[Type]:
        info = self._cache.get(workflow_id)
        if not info:
            return None
        module_name = info.get("module")
        class_name = info.get("class")
        if not module_name or not class_name:
            return None
        module = importlib.import_module(module_name)
        return getattr(module, class_name, None)

    def list_workflows(self) -> dict[str, dict[str, str]]:
        return dict(self._cache)


