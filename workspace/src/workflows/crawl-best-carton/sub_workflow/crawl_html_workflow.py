import time
from src.workflows.base.base_work_flow import BaseWorkFlow
from src.common.helper.logger import Logger
from src.common.helper.resource_helper import ResourceHelper
from .services import BoxUrlTracker, SiteMapParser
from src.common.helper.data_helper import DataHelper


class CrawlHtmlPipeline(BaseWorkFlow):
    """
    Crawl HTML pipeline for Best Carton website.
    """

    HOST = "https://bestcarton.com"
    MAX_PAGE = 4
    
    def execute(self):
        from playwright.sync_api import sync_playwright

        self.logger = Logger.get_logger(__name__)
        self.logger.info("Running CrawlHtmlPipeline...")

        html_content = ResourceHelper().get("site-map.html")
        parser = SiteMapParser()
        base_category_urls = parser.perform(html_content)[1:]
        category_urls = list(base_category_urls)  
        for page in range(2, self.MAX_PAGE + 1):
            category_urls.extend([category_url + f"?page={page}" for category_url in base_category_urls])

        self.logger.info(f"Found {len(category_urls)} category URLs")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()

            for category_url in category_urls:
                box_urls_data_path = f"box_urls_{category_url.replace('/', '_')}.json"

                if (DataHelper().exist(box_urls_data_path)):
                    self.logger.info(f"Box URLs already exist for {category_url}")
                    continue

                page.goto(self.HOST + category_url)

                try:
                    html = page.inner_html("#resultBox", timeout=3000)
                    box_urls = BoxUrlTracker().perform(html)
                except Exception as e:
                    self.logger.warning(f"Element #resultBox not found for {category_url}: {type(e).__name__}")
                    continue

                DataHelper().write_json(box_urls_data_path, box_urls)

                self.logger.info(f"Crawling {self.HOST + category_url}")
                time.sleep(1)

            browser.close()
        pass