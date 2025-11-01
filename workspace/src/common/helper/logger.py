import logging
from pathlib import Path
from typing import Optional
from src.common.helper.api_helper import ApiHelper
from src.common.constants.discord import DiscordConfig


class Logger:
    """
    Logger helper class to manage logging configuration.
    """
    
    _loggers: dict[str, logging.Logger] = {}
    _discord_webhook_url: Optional[str] = None
    
    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """
        Get or create a logger instance for the given name.
        
        Args:
            name: Logger name (typically __name__)
            
        Returns:
            logging.Logger: Logger instance
        """
        if name not in Logger._loggers:
            logger = logging.getLogger(name)
            
            if not logger.handlers:
                logger.setLevel(logging.INFO)
                
                console_handler = logging.StreamHandler()
                console_handler.setLevel(logging.INFO)
                formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                console_handler.setFormatter(formatter)
                logger.addHandler(console_handler)
                
                webhook = Logger._discord_webhook_url or DiscordConfig().get_webhook_url()
                if webhook:
                    discord_handler = _DiscordWebhookHandler(webhook, level=logging.INFO)
                    discord_handler.setFormatter(formatter)
                    logger.addHandler(discord_handler)

            Logger._loggers[name] = logger
        
        return Logger._loggers[name]


class _DiscordWebhookHandler(logging.Handler):
    """
    Logging handler to forward records to a Discord webhook.
    Uses ApiHelper to send JSON POST without external dependencies.
    """

    def __init__(self, webhook_url: str, level: int = logging.ERROR) -> None:
        super().__init__(level)
        self.webhook_url = webhook_url

    def emit(self, record: logging.LogRecord) -> None:
        try:
            content = self.format(record)
            payload = {"content": f"[{record.levelname}] {record.name}: {content}"}
            ApiHelper().post_json(self.webhook_url, payload, timeout=5)
        except Exception:
            pass

