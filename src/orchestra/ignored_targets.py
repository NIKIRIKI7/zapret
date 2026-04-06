"""
Единый контракт игнорируемых целей оркестратора.

Сейчас сюда входят только relay/служебные хосты отдельного Telegram Proxy
модуля. Это намеренно узкое правило: обычный Telegram Web не выключаем.
"""

from __future__ import annotations

try:
    from telegram_proxy.telegram_hosts import TELEGRAM_DOMAINS as TELEGRAM_PROXY_DOMAINS
except Exception:
    TELEGRAM_PROXY_DOMAINS = [
        "zws4.web.telegram.org",
        "vesta.web.telegram.org",
        "vesta-1.web.telegram.org",
        "venus-1.web.telegram.org",
        "telegram.me",
        "telegram.dog",
        "telegram.space",
        "telesco.pe",
        "tg.dev",
        "telegram.org",
        "t.me",
        "api.telegram.org",
        "td.telegram.org",
        "venus.web.telegram.org",
        "web.telegram.org",
        "kws2-1.web.telegram.org",
        "kws2.web.telegram.org",
        "kws4-1.web.telegram.org",
        "kws4.web.telegram.org",
        "zws2-1.web.telegram.org",
        "zws2.web.telegram.org",
        "zws4-1.web.telegram.org",
    ]


ORCHESTRA_IGNORED_EXACT_DOMAINS: tuple[str, ...] = tuple(
    sorted(
        {
            normalized
            for domain in TELEGRAM_PROXY_DOMAINS
            for normalized in [str(domain).strip().lower().rstrip(".")]
            if normalized and ".web.telegram.org" in normalized
        }
    )
)

_ORCHESTRA_IGNORED_DOMAIN_SET = set(ORCHESTRA_IGNORED_EXACT_DOMAINS)


def get_orchestra_ignored_exact_domains() -> tuple[str, ...]:
    """Возвращает канонический список точных доменов, игнорируемых оркестратором."""
    return ORCHESTRA_IGNORED_EXACT_DOMAINS


def is_orchestra_ignored_target(hostname: str) -> bool:
    """
    Проверяет, должен ли оркестратор полностью игнорировать этот хост.

    Важно:
    - правило точечное и работает только по relay/служебным доменам proxy-модуля;
    - мы сознательно НЕ игнорируем абстрактные ярлыки вроде "TELEGRAM",
      чтобы не отключить другие Telegram-профили оркестратора по ошибке.
    """
    normalized = str(hostname or "").strip().lower().rstrip(".")
    if not normalized:
        return False
    return normalized in _ORCHESTRA_IGNORED_DOMAIN_SET
