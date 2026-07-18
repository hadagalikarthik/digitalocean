import secrets
import string

ALPHABET = string.ascii_letters + string.digits


def generate_code(length: int = 7) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def is_valid_alias(alias: str) -> bool:
    if not 3 <= len(alias) <= 32:
        return False
    return all(ch.isalnum() or ch in "_-" for ch in alias)
