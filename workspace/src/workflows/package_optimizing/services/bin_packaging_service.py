from typing import Any, Iterable, Optional

from py3dbp import Packer, Bin, Item

from src.common.base.singleton import Singleton
from src.common.helper.logger import Logger


class BinPackagingService(Singleton):
    """
    Service to compute best-fit bins for orders using provided sizes.
    This service processes pure data and does not access external resources.
    """

    def perform(self, orders_list: list[Any], sizes_list: list[Any], max_orders: int | None = None) -> dict[str, Any]:
        logger = Logger.get_logger(__name__)
        if not isinstance(orders_list, list):
            orders_list = []
        if not isinstance(sizes_list, list):
            sizes_list = []

        helper = _PackingComputationHelper()
        summaries: list[dict[str, Any]] = []
        success_bins = 0

        logger.info(
            "BinPackagingService: start perform - orders=%d, sizes=%d, max_orders=%s",
            len(orders_list), len(sizes_list), str(max_orders),
        )

        limit = len(orders_list)
        if max_orders is not None:
            try:
                limit = max(0, min(int(max_orders), len(orders_list)))
            except (TypeError, ValueError):
                limit = len(orders_list)
        logger.info("BinPackagingService: processing 0/%d", limit)

        for index in range(limit):
            try:
                summary = helper.build_packing_summary_for_order(orders_list, sizes_list, index)
                summaries.append(summary)
                if isinstance(summary, dict) and summary.get("bin") is not None:
                    success_bins += 1
                    if success_bins % 100 == 0:
                        logger.info("BinPackagingService: processing %d/%d", success_bins, limit)
            except Exception:
                logger.error("BinPackagingService: failed to build summary for order index %d", index)
                continue

        logger.info(
            "BinPackagingService: done - produced %d summaries (processed=%d)",
            len(summaries), limit,
        )
        return {
            "total_orders": len(orders_list),
            "processed_orders": limit,
            "total_summaries": len(summaries),
            "summaries": summaries,
        }

    def perform_stream(self, orders_iter: Iterable[Any], sizes_list: list[Any], max_orders: Optional[int] = None) -> dict[str, Any]:
        """
        Stream processing: consume orders from an iterable/generator without loading all into memory at once.
        """
        logger = Logger.get_logger(__name__)
        if not isinstance(sizes_list, list):
            sizes_list = []

        helper = _PackingComputationHelper()
        summaries: list[dict[str, Any]] = []
        success_bins = 0

        processed = 0
        limit: Optional[int] = None
        if max_orders is not None:
            try:
                limit = max(0, int(max_orders))
            except (TypeError, ValueError):
                limit = None

        if limit is not None:
            logger.info("BinPackagingService: stream processing 0/%d", limit)
        else:
            logger.info("BinPackagingService: stream processing start (no total)")

        for order in orders_iter:
            if limit is not None and processed >= limit:
                break
            index = processed
            processed += 1
            try:
                summary = helper.build_packing_summary_for_single(order, sizes_list, index)
                summaries.append(summary)
                if isinstance(summary, dict) and summary.get("bin") is not None:
                    success_bins += 1
                    step = 100
                    if success_bins % step == 0:
                        if limit is not None:
                            logger.info("BinPackagingService: processing %d/%d", success_bins, limit)
                        else:
                            logger.info("BinPackagingService: processing %d", success_bins)
            except Exception:
                logger.error("BinPackagingService: failed to build summary for order index %d", index)
                continue

        logger.info(
            "BinPackagingService: stream done - produced %d summaries (processed=%d)",
            len(summaries), processed,
        )
        return {
            "total_orders": processed,
            "processed_orders": processed,
            "total_summaries": len(summaries),
            "summaries": summaries,
        }


class _PackingComputationHelper:
    def build_bins_from_sizes(
        self,
        sizes: list[Any],
        *,
        name_key: str = "size_cm",
        length_key: str = "length",
        width_key: str = "width",
        height_key: str = "height",
        url_key: str = "url",
        max_weight: float = 100000.0,
    ) -> list[Bin]:
        logger = Logger.get_logger(__name__)

        bins: list[Bin] = []
        for s in sizes:
            if not isinstance(s, dict):
                continue
            name = str(s.get(name_key)) if s.get(name_key) is not None else "bin"
            l = s.get(length_key)
            w = s.get(width_key)
            h = s.get(height_key)
            url = s.get(url_key)
            if l is None or w is None or h is None:
                continue
            try:
                fl = float(l)
                fw = float(w)
                fh = float(h)
                if not (fl > 0 and fw > 0 and fh > 0):
                    logger.error("BinPackagingService: invalid bin size: %s", s)
                    continue
                b = Bin(name=name, width=fw, height=fh, depth=fl, max_weight=float(max_weight))
                setattr(b, "url", url)
            except Exception:
                continue
            bins.append(b)
        return bins

    def build_items_from_order(
        self,
        order: Any,
        *,
        title_key: str = "title",
        id_key: str = "id",
        length_key: str = "length",
        width_key: str = "width",
        height_key: str = "height",
        weight_key: str = "weight",
        quantity_key: str = "quantity",
        length_unit_key: str = "length_unit",
        weight_unit_key: str = "weight_unit",
    ) -> list[Item]:
        items: list[Item] = []
        if not order or not isinstance(order, dict):
            return items
        products = order.get("products") or []
        for p in products:
            if not isinstance(p, dict):
                continue
            name = str(p.get(title_key) or p.get(id_key) or "item")

            l = p.get(length_key)
            w = p.get(width_key)
            h = p.get(height_key)
            weight = p.get(weight_key)
            quantity = p.get(quantity_key)

            if l is None or w is None or h is None or weight is None:
                continue
            try:
                l = float(l)
                w = float(w)
                h = float(h)
                weight = float(weight)
                quantity = int(quantity) if quantity is not None else 1
            except (TypeError, ValueError):
                continue

            if not (l > 0 and w > 0 and h > 0 and weight >= 0):
                continue

            l_unit = str(p.get(length_unit_key) or "cm").lower()
            if l_unit in {"mm"}:
                l, w, h = l / 10.0, w / 10.0, h / 10.0
            elif l_unit in {"m", "meter", "metre"}:
                l, w, h = l * 100.0, w * 100.0, h * 100.0

            w_unit = str(p.get(weight_unit_key) or "g").lower()
            if w_unit in {"kg"}:
                weight = weight * 1000.0
            elif w_unit in {"mg"}:
                weight = weight / 1000.0

            try:
                for _ in range(max(1, quantity)):
                    items.append(Item(name=name, width=w, height=h, depth=l, weight=weight))
            except Exception:
                continue

        return items

    def find_single_bin_that_fits_all_items(self, orders_list: list[Any], sizes_list: list[Any], index: int) -> Any:
        if index < 0 or index >= len(orders_list):
            return None
        items = self.build_items_from_order(orders_list[index])
        if not items:
            return None
        candidate_bins = self.build_bins_from_sizes(sizes_list)
        candidate_bins.sort(key=lambda b: float(getattr(b, "width", 0)) * float(getattr(b, "height", 0)) * float(getattr(b, "depth", 0)))
        for candidate in candidate_bins:
            packer = Packer()
            packer.add_bin(candidate)
            for it in items:
                packer.add_item(it)
            try:
                packer.pack()
            except Exception:
                continue
            packed_bin = packer.bins[0] if getattr(packer, "bins", None) else None
            if not packed_bin:
                continue
            fitted = list(getattr(packed_bin, "items", []))
            if len(fitted) == len(items):
                return packed_bin
        return None

    def find_single_bin_for_items(self, items: list[Item], sizes_list: list[Any]) -> Any:
        if not items:
            return None
        candidate_bins = self.build_bins_from_sizes(sizes_list)
        candidate_bins.sort(key=lambda b: float(getattr(b, "width", 0)) * float(getattr(b, "height", 0)) * float(getattr(b, "depth", 0)))
        for candidate in candidate_bins:
            packer = Packer()
            packer.add_bin(candidate)
            for it in items:
                packer.add_item(it)
            try:
                packer.pack()
            except Exception:
                continue
            packed_bin = packer.bins[0] if getattr(packer, "bins", None) else None
            if not packed_bin:
                continue
            fitted = list(getattr(packed_bin, "items", []))
            if len(fitted) == len(items):
                return packed_bin
        return None

    def build_packing_summary_for_order(self, orders_list: list[Any], sizes_list: list[Any], index: int) -> dict[str, Any]:
        if index < 0 or index >= len(orders_list):
            raise ValueError("Order index is out of range")

        order = orders_list[index]
        _ = self.build_items_from_order(order)

        best_bin = self.find_single_bin_that_fits_all_items(orders_list, sizes_list, index)

        products = order.get("products") or [] if isinstance(order, dict) else []

        bin_info = None
        if best_bin is not None:
            bw = float(getattr(best_bin, "width", 0))
            bh = float(getattr(best_bin, "height", 0))
            bd = float(getattr(best_bin, "depth", 0))
            bin_url = getattr(best_bin, "url", None)
            bin_info = {
                "name": str(getattr(best_bin, "name", "bin")),
                "length": bd,
                "width": bw,
                "height": bh,
                "volume": bd * bw * bh,
                "fitted_items": len(getattr(best_bin, "items", [])),
                "url": bin_url,
            }

        summary = {
            "order_index": index,
            "order_id": order.get("transaction_id") if isinstance(order, dict) else None,
            "products_count": len(products),
            "bin": bin_info,
        }
        return summary

    def build_packing_summary_for_single(self, order: Any, sizes_list: list[Any], index: int) -> dict[str, Any]:
        _ = self.build_items_from_order(order)
        items = self.build_items_from_order(order)
        best_bin = self.find_single_bin_for_items(items, sizes_list)

        products = order.get("products") or [] if isinstance(order, dict) else []

        bin_info = None
        if best_bin is not None:
            bw = float(getattr(best_bin, "width", 0))
            bh = float(getattr(best_bin, "height", 0))
            bd = float(getattr(best_bin, "depth", 0))
            bin_url = getattr(best_bin, "url", None)
            bin_info = {
                "name": str(getattr(best_bin, "name", "bin")),
                "length": bd,
                "width": bw,
                "height": bh,
                "volume": bd * bw * bh,
                "fitted_items": len(getattr(best_bin, "items", [])),
                "url": bin_url,
            }

        summary = {
            "order_index": index,
            "order_id": order.get("transaction_id") if isinstance(order, dict) else None,
            "products_count": len(products),
            "bin": bin_info,
        }
        return summary


