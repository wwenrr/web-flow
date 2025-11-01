from __future__ import annotations

from src.common.base.singleton import Singleton


class DiscordConfig(Singleton):
    """
    Discord configuration holder.
    """

    def __init__(self):
        if not hasattr(self, "_webhook_url"):
            self._webhook_url: str = (
                "https://discord.com/api/webhooks/1435461944135127200/I2mVpjLHVRK9HGEtO76gc4TKs3LBouixi5mtQR3Ph97JHW6p30v3GIgCMzRVu3XZUhCP"
            )

            self._file_webhook_url: str = (
                "https://discord.com/api/webhooks/1435516247117926532/yT49TB-TRi8qY0p_qLTgdvjcmoalaEkmajRw5qG-dLq9bv51h825KDXeNn5gWVws4M2D"
            )

    def get_file_webhook_url(self) -> str:
        return self._file_webhook_url

    def get_webhook_url(self) -> str:
        return self._webhook_url
