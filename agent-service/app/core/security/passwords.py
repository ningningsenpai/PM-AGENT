"""密码哈希与校验。"""
from __future__ import annotations

from functools import lru_cache

from pwdlib import PasswordHash


class PasswordManager:
    def __init__(self) -> None:
        self._password_hash = PasswordHash.recommended()

    def hash(self, password: str) -> str:
        return self._password_hash.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        return self._password_hash.verify(password, password_hash)


@lru_cache
def get_password_manager() -> PasswordManager:
    return PasswordManager()
