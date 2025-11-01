from src.workflows.base.base_work_flow import BaseWorkFlow
from src.common.helper.data_helper import DataHelper
from src.common.helper.resource_helper import ResourceHelper
from .services import BinPackagingService, BinUsageStatisticsService, DiscordFileUploadService, BinUsageCsvExportService
from src.common.helper.logger import Logger
from typing import Any
import threading

class BinPackagePipeline(BaseWorkFlow):
    MAX_ORDERS = 99999

    def execute(self, input_data: Any = None):
        logger = Logger.get_logger(__name__)

        logger.info("BinPackagePipeline: start execute")

        self._run_types_parallel(("kc", "jf", "jwl"))

        for typ in ("kc", "jf", "jwl"):
            stats = DataHelper().get_json(f"bin_usage_statistics_{typ}.json")
            sizes = ResourceHelper().get_json("sizes.json")
            csv = BinUsageCsvExportService().perform(typ, stats, sizes)
            DataHelper().write(f"bin_usage_statistics_{typ}.csv", csv)

            try:
                DiscordFileUploadService().perform(csv, f"bin_usage_statistics_{typ}.csv")
                logger.info("BinPackagePipeline: uploaded %s to Discord", f"bin_usage_statistics_{typ}.csv")
            except Exception as e:
                logger.error("BinPackagePipeline: error uploading %s: %s", f"bin_usage_statistics_{typ}.csv", e)

            logger.info("BinPackagePipeline: wrote %s to data", f"bin_usage_statistics_{typ}.csv")

        logger.info("BinPackagePipeline: end execute")

    def _process_type(self, typ: str) -> None:
        logger = Logger.get_logger(__name__)
        enc_path = f"enc/{typ}.json.enc"
        logger.info("BinPackagePipeline: processing type=%s enc_path=%s", typ, enc_path)

        json_data = ResourceHelper().get_enc_json(enc_path)
        sizes = ResourceHelper().get_json("sizes.json")
        logger.info("BinPackagePipeline: loaded data for type=%s", typ)

        packing_summary = BinPackagingService().perform_stream(json_data, sizes, max_orders=self.MAX_ORDERS)
        logger.info("BinPackagePipeline: packing_summary ready for type=%s", typ)

        bin_usage_statistics = BinUsageStatisticsService().perform(packing_summary.get("summaries"), json_data)
        logger.info("BinPackagePipeline: bin_usage_statistics ready for type=%s", typ)

        out_name = f"bin_usage_statistics_{typ}.json"
        try:
            DiscordFileUploadService().perform(bin_usage_statistics, out_name)
            DataHelper().write_json(out_name, bin_usage_statistics)

            logger.info("BinPackagePipeline: wrote %s to data", out_name)
            logger.info("BinPackagePipeline: uploaded %s to Discord", out_name)
        except Exception as e:
            logger.error("BinPackagePipeline: error uploading %s: %s", out_name, e)

    def _safe_process_type(self, typ: str) -> None:
        logger = Logger.get_logger(__name__)
        try:
            self._process_type(typ)
        except Exception as e:
            logger.error("BinPackagePipeline: error processing type %s: %s", typ, e)

    def _run_types_parallel(self, types: tuple[str, ...]) -> None:
        logger = Logger.get_logger(__name__)
        threads: list[threading.Thread] = []
        for typ in types:
            t = threading.Thread(target=self._safe_process_type, args=(typ,), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()
        logger.info("BinPackagePipeline: all types completed")