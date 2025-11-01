from __future__ import annotations

import json
import ssl
from typing import Any, Dict, Optional

from src.common.base.singleton import Singleton


class ApiHelper(Singleton):
    """
    Helper class to perform simple HTTP requests without external deps.
    Designed for lightweight JSON POST use cases (e.g., webhooks).
    """

    def post_json(
        self,
        url: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 5.0,
    ) -> None:
        try:
            import urllib.request

            if isinstance(payload, dict) and isinstance(payload.get("content"), str):
                content = payload["content"]
                if len(content) > 1800:
                    payload["content"] = content[:1800] + "\n...(truncated)"

            body = json.dumps(payload).encode("utf-8")
            req_headers = {
                "Content-Type": "application/json",
                "User-Agent": "webflow-bot/1.0 (+playwright)",
            }
            if headers:
                req_headers.update(headers)

            context = ssl.create_default_context()

            req = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout, context=context):  
                pass
        except Exception as e:
            pass


