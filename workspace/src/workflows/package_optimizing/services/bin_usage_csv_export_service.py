from __future__ import annotations

import csv
import io
from typing import Any

from src.common.base.singleton import Singleton
from src.common.helper.data_helper import DataHelper


class BinUsageCsvExportService(Singleton):
    """
    Build CSV statistics by joining bin usage stats with sizes by URL.

    Input: typ in {"kc","jf","jwl"}
    Output: CSV string with columns:
      PackageId, URL, Title, Type, OuterLength [cm], OuterWidth [cm], OuterHeight [cm],
      InnerLength [cm], InnerWidth [cm], InnerHeight [cm], MaxWeight [g], EmptyWeight [g],
      Cost, Status, Order count
    """

    def perform(self, typ: str, stats: list[dict[str, Any]], sizes: list[dict[str, Any]]) -> str:

        url_to_size: dict[str, dict[str, Any]] = {}
        for s in sizes or []:
            if not isinstance(s, dict):
                continue
            url = str(s.get("url") or "").strip()
            if url:
                url_to_size[url] = s

        header = [
            "PackageId",
            "URL",
            "Title",
            "Type",
            "OuterLength [cm]",
            "OuterWidth [cm]",
            "OuterHeight [cm]",
            "InnerLength [cm]",
            "InnerWidth [cm]",
            "InnerHeight [cm]",
            "MaxWeight [g]",
            "EmptyWeight [g]",
            "Cost",
            "Status",
            "Order count",
        ]

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(header)

        for row in stats or []:
            if not isinstance(row, dict):
                continue
            url = str(row.get("url") or "").strip()
            usage_count = row.get("usage_count") or 0
            size = url_to_size.get(url) or {}

            package_id = _first_non_empty(
                size.get("packageId"), size.get("id"), size.get("sku"), size.get("code"), ""
            )
            title = _first_non_empty(size.get("title"), size.get("name"), size.get("size_cm"), "")
            typ_name = "bin"

            outer_l = _to_float_str(size.get("length"))
            outer_w = _to_float_str(size.get("width"))
            outer_h = _to_float_str(size.get("height"))

            inner_l = _to_float_str(size.get("inner_length") or size.get("innerLength"))
            inner_w = _to_float_str(size.get("inner_width") or size.get("innerWidth"))
            inner_h = _to_float_str(size.get("inner_height") or size.get("innerHeight"))

            max_weight = ""  # intentionally blank per requirement
            empty_weight = _to_float_str(size.get("empty_weight") or size.get("emptyWeight"))
            cost = ""  # intentionally blank per requirement
            status = _first_non_empty(size.get("status"), "")

            writer.writerow([
                package_id,
                url,
                title,
                typ_name,
                outer_l,
                outer_w,
                outer_h,
                inner_l,
                inner_w,
                inner_h,
                max_weight,
                empty_weight,
                cost,
                status,
                int(usage_count) if isinstance(usage_count, (int, float)) else 0,
            ])

        return buf.getvalue()


def _first_non_empty(*vals: Any) -> str:
    for v in vals:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ""


def _to_float_str(v: Any) -> str:
    if v is None:
        return ""
    try:
        f = float(v)
        s = ("{:.6f}".format(f)).rstrip("0").rstrip(".")
        return s
    except Exception:
        return ""


