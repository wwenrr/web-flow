from __future__ import annotations

import json
import ssl
import uuid
from typing import Any

from src.common.base.singleton import Singleton
from src.common.constants.discord import DiscordConfig


class DiscordFileUploadService(Singleton):
    """
    Service to upload a JSON payload as a file to a Discord webhook.
    Uses DiscordConfig.get_file_webhook_url() to resolve the webhook URL.
    """

    def perform(
        self,
        data: Any,
        filename: str = "data.json",
        message: str | None = None,
        timeout: float = 10.0,
        content_type: str = "application/json",
    ) -> dict[str, Any]:
        webhook_url = DiscordConfig().get_file_webhook_url()
        payload_bytes = self._materialize_bytes(data, content_type)
        body, content_type = self._build_multipart(
            fields={
                # Optional text content shown with the file
                "content": message or "",
            },
            files={
                "file": (filename, payload_bytes, content_type),
            },
        )

        self._post_bytes(webhook_url, body, content_type, timeout)
        return {"ok": True, "filename": filename, "bytes": len(body)}

    def _materialize_bytes(self, data: Any, content_type: str) -> bytes:
        if isinstance(data, (bytes, bytearray)):
            return bytes(data)
        if isinstance(data, str):
            return data.encode("utf-8")
        # Default behavior for JSON
        if (content_type or "").lower().startswith("application/json"):
            text = self._serialize_json(data)
            return text.encode("utf-8")
        # Fallback: stringify
        return str(data).encode("utf-8")

    def _serialize_json(self, data: Any) -> str:
        try:
            return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception:
            # Fallback best-effort
            return json.dumps({"_raw": str(data)}, ensure_ascii=False)

    def _build_multipart(self, *, fields: dict[str, str], files: dict[str, tuple[str, bytes, str]]) -> tuple[bytes, str]:
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
        lines: list[bytes] = []

        def add_text_field(name: str, value: str) -> None:
            lines.append((f"--{boundary}\r\n").encode("utf-8"))
            lines.append((f"Content-Disposition: form-data; name=\"{name}\"\r\n\r\n").encode("utf-8"))
            lines.append((value or "").encode("utf-8"))
            lines.append(b"\r\n")

        def add_file_field(name: str, filename: str, content: bytes, content_type: str) -> None:
            lines.append((f"--{boundary}\r\n").encode("utf-8"))
            lines.append((
                f"Content-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\n"
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode("utf-8"))
            lines.append(content)
            lines.append(b"\r\n")

        for k, v in (fields or {}).items():
            add_text_field(k, v)
        for k, (fname, content, ctype) in (files or {}).items():
            add_file_field(k, fname, content, ctype)

        lines.append((f"--{boundary}--\r\n").encode("utf-8"))
        body = b"".join(lines)
        content_type = f"multipart/form-data; boundary={boundary}"
        return body, content_type

    def _post_bytes(self, url: str, body: bytes, content_type: str, timeout: float) -> None:
        try:
            import urllib.request

            headers = {
                "Content-Type": content_type,
                "User-Agent": "webflow-bot/1.0 (+playwright)",
            }
            context = ssl.create_default_context()
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout, context=context):
                pass
        except Exception:
            # Swallow errors by design to avoid breaking the workflow; caller can inspect return
            raise


