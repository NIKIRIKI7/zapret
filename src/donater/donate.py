# donater/donate.py
"""
Тестовый helper для проверки подписанных ответов Premium backend.

Вся рабочая бизнес-логика живёт в `donater/service.py` и `donater/storage.py`.
Этот модуль оставлен только как тонкая точка для `_verify_signed_response`,
чтобы тесты могли патчить `TRUSTED_PUBLIC_KEYS_B64` без прямого захода в crypto.
"""

from __future__ import annotations

from typing import Dict, Optional

from . import crypto as _crypto
from .crypto import TRUSTED_PUBLIC_KEYS_B64


def _verify_signed_response(resp: Dict, *, expected_device_id: str, expected_nonce: Optional[str] = None) -> Optional[Dict]:
    # Important for tests: allow patching donater.donate.TRUSTED_PUBLIC_KEYS_B64 at runtime.
    return _crypto.verify_signed_response(
        resp,
        expected_device_id=expected_device_id,
        expected_nonce=expected_nonce,
        trusted_public_keys_b64=TRUSTED_PUBLIC_KEYS_B64,
    )
