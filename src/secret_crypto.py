"""Small envelope-encryption helper for credentials persisted in D1/SQLite."""

from cryptography.fernet import Fernet, InvalidToken


class SecretConfigurationError(RuntimeError):
    pass


def _cipher(key: str | None) -> Fernet:
    if not key:
        raise SecretConfigurationError(
            "SECRET_ENCRYPTION_KEY must be configured before storing secrets")
    try:
        return Fernet(key.encode("ascii"))
    except Exception as exc:  # noqa: BLE001
        raise SecretConfigurationError(
            "SECRET_ENCRYPTION_KEY must be a valid Fernet key") from exc


def encrypt(value: str, key: str | None) -> str:
    return "f1:" + _cipher(key).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(value: str, key: str | None) -> str:
    # Legacy plaintext values are rejected in production rather than silently
    # perpetuating them. A migration can re-encrypt them with the key.
    if not value.startswith("f1:"):
        raise SecretConfigurationError("legacy plaintext secret requires migration")
    try:
        return _cipher(key).decrypt(value[3:].encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise SecretConfigurationError("stored secret could not be decrypted") from exc
