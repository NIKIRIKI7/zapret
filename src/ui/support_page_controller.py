from __future__ import annotations

import webbrowser
from dataclasses import dataclass

from log import log


@dataclass(slots=True)
class SupportActionResult:
    ok: bool
    message: str


class SupportPageController:
    TELEGRAM_SUPPORT_DOMAIN = "zaprethelp"
    DISCORD_URL = "https://discord.gg/kkcBDG2uws"

    @staticmethod
    def open_support_discussions() -> SupportActionResult:
        from config.urls import SUPPORT_DISCUSSIONS_URL

        try:
            webbrowser.open(SUPPORT_DISCUSSIONS_URL)
            log(f"Открыта поддержка GitHub Discussions: {SUPPORT_DISCUSSIONS_URL}", "INFO")
            return SupportActionResult(True, SUPPORT_DISCUSSIONS_URL)
        except Exception as e:
            return SupportActionResult(False, str(e))

    @classmethod
    def open_telegram_support(cls) -> SupportActionResult:
        try:
            from config.telegram_links import open_telegram_link

            open_telegram_link(cls.TELEGRAM_SUPPORT_DOMAIN)
            log(f"Открыт Telegram: {cls.TELEGRAM_SUPPORT_DOMAIN}", "INFO")
            return SupportActionResult(True, cls.TELEGRAM_SUPPORT_DOMAIN)
        except Exception as e:
            return SupportActionResult(False, str(e))

    @classmethod
    def open_discord(cls) -> SupportActionResult:
        try:
            webbrowser.open(cls.DISCORD_URL)
            log(f"Открыт Discord: {cls.DISCORD_URL}", "INFO")
            return SupportActionResult(True, cls.DISCORD_URL)
        except Exception as e:
            return SupportActionResult(False, str(e))
