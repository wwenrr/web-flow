from collections import defaultdict
from typing import Any

from src.common.helper.logger import Logger
from src.common.base.singleton import Singleton


class BinUsageStatisticsService(Singleton):
    """
    Service to analyze bin usage from packing summaries and orders data.
    Produces a list of statistics objects, sorted by usage_count desc.
    """

    def perform(self, packing_summaries: list[dict[str, Any]], orders_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(packing_summaries, list):
            packing_summaries = []
        if not isinstance(orders_data, list):
            orders_data = []

        helper = _BinUsageComputationHelper()
        order_lookup = helper.create_order_lookup(orders_data)
        bin_stats = helper.analyze_bin_usage(packing_summaries, order_lookup)
        enhanced = helper.create_enhanced_statistics(bin_stats)
        return enhanced


class _BinUsageComputationHelper:
    def create_order_lookup(self, orders_data: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        order_lookup: dict[str, dict[str, Any]] = {}
        for order in orders_data:
            if not isinstance(order, dict):
                continue
            transaction_id = order.get("transaction_id")
            if transaction_id:
                order_lookup[transaction_id] = {
                    "index": order.get("index"),
                    "products_count": len(order.get("products", []) if isinstance(order.get("products"), list) else []),
                    "total_quantity": sum(
                        (p.get("quantity", 0) or 0)
                        for p in (order.get("products") or [])
                        if isinstance(p, dict)
                    ),
                }
        return order_lookup

    def analyze_bin_usage(self, packing_summaries: list[dict[str, Any]], order_lookup: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        bin_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "name": "bin",
                "url": "",
                "length": 0.0,
                "width": 0.0,
                "height": 0.0,
                "volume": 0.0,
                "usage_count": 0,
                "orders_detail": [],
            }
        )

        for summary in packing_summaries:
            if not isinstance(summary, dict):
                continue
            order_id = summary.get("order_id")
            bin_info = summary.get("bin")
            if not isinstance(bin_info, dict):
                continue

            bin_url = bin_info.get("url") or ""
            if not bin_url:
                continue

            stats = bin_stats[bin_url]
            if not stats["length"]:
                stats.update(
                    {
                        "name": bin_info.get("name", "bin"),
                        "url": bin_url,
                        "length": bin_info.get("length", 0.0) or 0.0,
                        "width": bin_info.get("width", 0.0) or 0.0,
                        "height": bin_info.get("height", 0.0) or 0.0,
                        "volume": bin_info.get("volume", 0.0) or 0.0,
                    }
                )

            stats["usage_count"] = int(stats.get("usage_count", 0)) + 1

            order_detail: dict[str, Any] = {
                "order_id": order_id,
                "order_index": summary.get("order_index"),
                "products_count": summary.get("products_count", 0) or 0,
            }

            if order_id and order_id in order_lookup:
                order_info = order_lookup[order_id]
                order_detail.update(
                    {
                        "order_index_from_orders": order_info.get("index"),
                        "actual_products_count": order_info.get("products_count", 0) or 0,
                        "total_quantity": order_info.get("total_quantity", 0) or 0,
                    }
                )

            stats["orders_detail"].append(order_detail)

        return dict(bin_stats)

    def create_enhanced_statistics(self, bin_stats: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        logger = Logger.get_logger(__name__)

        result: list[dict[str, Any]] = []

        for _, stats in bin_stats.items():
            orders_detail = list(stats.get("orders_detail", []))
            def _coalesce_index(d: dict[str, Any]) -> int:
                a = d.get("order_index")
                if isinstance(a, int):
                    return a
                b = d.get("order_index_from_orders")
                if isinstance(b, int):
                    return b
                try:
                    return int(a) if a is not None else (int(b) if b is not None else 0)
                except Exception:
                    logger.error("BinUsageStatisticsService: error coalescing index: %s", d)
                    return 0

            sorted_orders = sorted(
                orders_detail,
                key=lambda x: (x.get("order_index") is None and x.get("order_index_from_orders") is None, _coalesce_index(x)),
            )

            total_unique_orders = len({od.get("order_id") for od in orders_detail if od.get("order_id") is not None})
            total_products_packed = sum(int(od.get("products_count", 0) or 0) for od in orders_detail)

            item: dict[str, Any] = {
                "name": stats.get("name", "bin"),
                "url": stats.get("url", ""),
                "length": stats.get("length", 0.0) or 0.0,
                "width": stats.get("width", 0.0) or 0.0,
                "height": stats.get("height", 0.0) or 0.0,
                "volume": stats.get("volume", 0.0) or 0.0,
                "usage_count": int(stats.get("usage_count", 0) or 0),
                "orders_detail": sorted_orders,
                "total_unique_orders": total_unique_orders,
                "total_products_packed": total_products_packed,
            }

            total_actual_products = 0
            total_quantity = 0
            for od in orders_detail:
                if "actual_products_count" in od:
                    total_actual_products += int(od.get("actual_products_count", 0) or 0)
                if "total_quantity" in od:
                    total_quantity += int(od.get("total_quantity", 0) or 0)

            if total_actual_products > 0:
                item["total_actual_products"] = total_actual_products
                item["total_quantity"] = total_quantity

            result.append(item)

        result.sort(key=lambda x: x.get("usage_count", 0), reverse=True)
        return result


