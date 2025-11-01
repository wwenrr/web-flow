import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Browser, Page

from src.common.helper.file_helper import FileHelper
from src.common.helper.logger import Logger
from src.common.helper.setting_helper import SettingHelper
from src.workflows.base.base_work_flow import BaseWorkFlow


class BaotangTruyenCrawlingPipeline(BaseWorkFlow):
    """
    Crawling pipeline for BaotangTruyen website using Playwright.
    """
    
    def execute(self):
        """
        Main entry point to run the crawling pipeline.
        """
        self.logger = Logger.get_logger(__name__)
        self.logger.info("Running BaotangTruyenCrawlingPipeline...")

        try:
            settings = SettingHelper().get_section('baotangtruyen-crawling') or {}
            
            users = settings.get('users', [])
            self.host = settings.get('host', '')
            headless = settings.get('headless', True)
            retry_count = settings.get('retry', 3)

            for user in users:
                retry = retry_count
                self.logger.info(f"Processing user: {user['email']}")

                while retry > 0:
                    try:
                        with sync_playwright() as p:
                            browser = p.chromium.launch(headless=headless)
                            context = browser.new_context()
                            page = context.new_page()
                            
                            # Visit the host
                            page.goto(self.host)
                            self._login(page, user)
                            self._mission_attend(page, context)
                            
                            browser.close()
                            break
                            
                    except Exception as e:
                        retry -= 1
                        self.logger.error(f"Error occurred in BaotangTruyenCrawlingPipeline, retrying {retry} more times: {e}")

        except Exception as e:
            self.logger.error(f"Error occurred in BaotangTruyenCrawlingPipeline: {e}")

    def _login(self, page: Page, user: dict):
        """
        Login to the website.
        
        Args:
            page: Playwright page object
            user: User credentials dictionary with 'email' and 'password'
        """
        # Click login button
        login_button = page.wait_for_selector("//button[contains(text(),'Đăng nhập')]", timeout=15000)
        login_button.click()
        self.logger.info("Login button clicked")

        # Enter email
        email_input = page.wait_for_selector("//form/div[1]/input", timeout=10000)
        email_input.fill(user['email'])
        self.logger.info("Email entered")

        # Enter password
        password_input = page.wait_for_selector("//form/div[2]/input", timeout=10000)
        password_input.fill(user['password'])
        self.logger.info("Password entered")

        # Click submit button
        submit_button = page.wait_for_selector("//form/button", timeout=20000)
        submit_button.scroll_into_view_if_needed()
        time.sleep(1)
        submit_button.click()

        self.logger.info("Login successful")
        time.sleep(5)

    def _mission_attend(self, page: Page, context):
        """
        Complete mission attendance and daily check-in.
        
        Args:
            page: Playwright page object
            context: Browser context for saving cookies
        """
        # Save cookies
        cookies = context.cookies()
        settings_path = Path(__file__).parent
        cookies_file = settings_path / "data" / "cookies.json"
        FileHelper().write_json_file(cookies_file, cookies)
        self.logger.info(f"Cookies saved to {cookies_file}")

        # Spin mission
        try:
            page.goto(f"{self.host}/user/missions")
            page.wait_for_load_state("networkidle")
            page.wait_for_selector("#root", timeout=20000)
            spin_button = page.wait_for_selector(
                r"#root > div > div > div > div > div > div.rounded.p-4.bg-\[\#EBEBEB\] > div.flex.justify-between.border-b.pb-4.border-\[\#0C1121\].items-center.gap-\[30px\] > div.md\:w-\[140px\].w-\[80px\].text-center > button",
                timeout=20000
            )
            spin_button.click()
            time.sleep(2)

            confirm_button = page.wait_for_selector(
                "xpath=//html/body/div[2]/div/div[2]/div/div[1]/div/div[2]/div/div/div[3]/button",
                timeout=10000
            )
            confirm_button.click()
            time.sleep(2)
            self.logger.info("Spinning completed successfully")
        except Exception as e:
            self.logger.error(f"Fail spinning mission: {e}")

        # Daily mission
        try:
            page.goto(f"{self.host}/user/missions")
            page.wait_for_load_state("networkidle")
            page.wait_for_selector("#root", timeout=20000)
            daily_button = page.wait_for_selector(
                r"#root > div > div > div > div > div > div.rounded.p-4.bg-\[\#EBEBEB\] > div.flex.justify-between.border-b.py-4.border-\[\#0C1121\].items-center.gap-\[30px\] > div.md\:w-\[140px\].w-\[80px\].flex.justify-center > button",
                timeout=20000
            )
            daily_button.click()
            time.sleep(2)
            self.logger.info("Daily mission completed successfully")
        except Exception as e:
            self.logger.error(f"Fail daily mission: {e}")

