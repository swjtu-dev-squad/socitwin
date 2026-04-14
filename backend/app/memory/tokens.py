from __future__ import annotations

import math
from typing import Any

from camel.utils import BaseTokenCounter


class HeuristicUnicodeTokenCounter(BaseTokenCounter):
    _MESSAGE_OVERHEAD = 4

    def count_tokens_from_messages(self, messages: list[dict[str, Any]]) -> int:
        total = 0
        for message in messages:
            total += self._MESSAGE_OVERHEAD
            total += self._estimate_value(message)
        return total

    def encode(self, text: str) -> list[int]:
        return [ord(char) for char in text]

    def decode(self, token_ids: list[int]) -> str:
        return "".join(chr(token_id) for token_id in token_ids)

    def _estimate_value(self, value: Any) -> int:
        if value is None:
            return 0
        if isinstance(value, str):
            return self._estimate_text_tokens(value)
        if isinstance(value, dict):
            return sum(
                self._estimate_text_tokens(str(key)) + self._estimate_value(item)
                for key, item in value.items()
            )
        if isinstance(value, (list, tuple)):
            return sum(self._estimate_value(item) for item in value)
        return self._estimate_text_tokens(str(value))

    def _estimate_text_tokens(self, text: str) -> int:
        if not text:
            return 0

        ascii_chars = 0
        cjk_chars = 0
        other_unicode_chars = 0

        for char in text:
            code_point = ord(char)
            if code_point < 128:
                ascii_chars += 1
            elif self._is_cjk_like(code_point):
                cjk_chars += 1
            else:
                other_unicode_chars += 1

        return math.ceil(ascii_chars / 3) + cjk_chars + other_unicode_chars * 2

    def _is_cjk_like(self, code_point: int) -> bool:
        return (
            0x3040 <= code_point <= 0x30FF
            or 0x3400 <= code_point <= 0x4DBF
            or 0x4E00 <= code_point <= 0x9FFF
            or 0xAC00 <= code_point <= 0xD7AF
        )
