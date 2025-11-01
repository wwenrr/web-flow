from playwright.sync_api import sync_playwright
from src.common.helper.data_helper import DataHelper
from src.common.helper.api_helper import ApiHelper
from src.common.constants.discord import DiscordConfig
from src.workflows.base.base_work_flow import BaseWorkFlow
import time
import threading
import json
import tempfile
import os
from pathlib import Path
from typing import Any
from .services import ProductParser
from src.common.helper.logger import Logger
from .sub_workflow.crawl_html_workflow import CrawlHtmlPipeline

class CrawlProductPipeline(BaseWorkFlow):
    """
    Crawl product pipeline for Best Carton website.
    """

    _BASE_HOST = "https://bestcarton.com"

    def execute(self):
        self.logger = Logger.get_logger(__name__)

        self.logger.info("Running CrawlHtmlPipeline...")
        CrawlHtmlPipeline().execute()
        self.logger.info("CrawlHtmlPipeline completed")

        self.logger.info("Running CrawlProductPipeline...")
        discord_thread = threading.Thread(target=self._discord_notification_loop, daemon=True)
        discord_thread.start()
        
        list_product_data_paths = DataHelper().list_subworkflow_data()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

            for product_data_path in list_product_data_paths:
                product_data = DataHelper().get_json_from_subworkflow(product_data_path)
                for product_url in product_data:
                    product_info_data_path = f"product_info_{product_url.replace('/', '_')}.json"
                    if (DataHelper().exist(product_info_data_path)):
                        self.logger.info(f"Product info already exists for {product_url}")
                        continue

                    page.goto(self._BASE_HOST + product_url)

                    try:
                        html = page.inner_html("#section_specs", timeout=3000)
                        product_info = ProductParser().perform(html, self._BASE_HOST + product_url)
                        DataHelper().write_json(product_info_data_path, product_info)
                    except Exception as e:
                        self.logger.warning(f"Element #section_specs not found for {product_url}: {type(e).__name__}")
                        continue

                    time.sleep(1)

            browser.close()

    def _get_all_product_info(self) -> list[dict[str, Any]]:
        """
        Helper method to merge all product info JSON files from data directory.
        
        Returns:
            list[dict]: List of all product info dictionaries
        """
        data_helper = DataHelper()
        data_files = data_helper.list_data()
        all_products: list[dict[str, Any]] = []
        
        for data_path in data_files:
            if not data_path.endswith('.json'):
                continue
            
            try:
                product_info = data_helper.get_json(data_path)
                # If it's a list, extend; if it's a dict, append
                if isinstance(product_info, list):
                    all_products.extend(product_info)
                elif isinstance(product_info, dict):
                    all_products.append(product_info)
            except Exception:
                # Skip files that can't be parsed
                continue
        
        return all_products

    def _discord_notification_loop(self) -> None:
        """
        Helper method to run in a separate thread, sending product info to Discord every 10 minutes.
        """
        while True:
            try:
                TIME_INTERVAL = 300
                time.sleep(TIME_INTERVAL)
                product_list = self._get_all_product_info()
                self._send_product_info_to_discord(product_list)
            except Exception as e:
                self.logger.error(f"Error in Discord notification loop: {e}")

    def _send_product_info_to_discord(self, product_list: list[dict[str, Any]]) -> None:
        """
        Helper method to send product info list to Discord as JSON file.
        
        Args:
            product_list: List of product info dictionaries
        """
        temp_file = None
        try:
            discord_config = DiscordConfig()
            webhook_url = discord_config.get_webhook_url()
            
            # Create temporary JSON file
            total_products = len(product_list)
            json_data = json.dumps(product_list, indent=2, ensure_ascii=False)
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
                f.write(json_data)
                temp_file = f.name
            
            # Send file to Discord
            self._send_file_to_discord(webhook_url, temp_file, f"📦 Product Info Update\nTotal products: {total_products}")
            self.logger.info(f"Sent product info file to Discord: {total_products} products")
        except Exception as e:
            self.logger.error(f"Failed to send product info to Discord: {e}")
        finally:
            # Clean up temporary file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception:
                    pass

    def _send_file_to_discord(self, webhook_url: str, file_path: str, content: str = "") -> None:
        """
        Helper method to send a file to Discord webhook.
        
        Args:
            webhook_url: Discord webhook URL
            file_path: Path to file to send
            content: Optional message content
        """
        try:
            import urllib.request
            import ssl
            
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            file_name = Path(file_path).name
            
            # Create multipart form data
            boundary = '----WebKitFormBoundary' + ''.join([str(i) for i in range(15)])
            body_parts = []
            
            if content:
                body_parts.append(f'--{boundary}\r\n'.encode())
                body_parts.append(f'Content-Disposition: form-data; name="content"\r\n\r\n'.encode())
                body_parts.append(f'{content}\r\n'.encode())
            
            body_parts.append(f'--{boundary}\r\n'.encode())
            body_parts.append(f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n'.encode())
            body_parts.append(f'Content-Type: application/json\r\n\r\n'.encode())
            body_parts.append(file_data)
            body_parts.append(f'\r\n--{boundary}--\r\n'.encode())
            
            body = b''.join(body_parts)
            
            req = urllib.request.Request(
                webhook_url,
                data=body,
                headers={
                    'Content-Type': f'multipart/form-data; boundary={boundary}',
                    'User-Agent': 'webflow-bot/1.0 (+playwright)',
                },
                method='POST'
            )
            
            context = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=30, context=context):
                pass
        except Exception as e:
            raise Exception(f"Failed to send file to Discord: {e}")