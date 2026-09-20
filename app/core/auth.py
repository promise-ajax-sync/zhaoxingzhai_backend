import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, Request

from app.core.config import Settings


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    work_factor, block_size, parallelism = 16384, 8, 1
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=work_factor,
        r=block_size,
        p=parallelism,
        dklen=32,
    )
    return "$".join(
        [
            "scrypt",
            str(work_factor),
            str(block_size),
            str(parallelism),
            _b64url(salt),
            _b64url(digest),
        ]
    )


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, n, r, p, salt, expected = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_b64url_decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=32,
        )
        return hmac.compare_digest(_b64url(digest), expected)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str, settings: Settings) -> tuple[str, datetime]:
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.app_access_token_minutes)
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url(
        json.dumps(
            {
                "sub": user_id,
                "type": "access",
                "iss": "zhaoxingzhai",
                "iat": int(now.timestamp()),
                "exp": int(expires_at.timestamp()),
            },
            separators=(",", ":"),
        ).encode()
    )
    signing_input = f"{header}.{payload}"
    signature = _b64url(
        hmac.new(
            settings.app_access_token_secret.encode(),
            signing_input.encode(),
            hashlib.sha256,
        ).digest()
    )
    return f"{signing_input}.{signature}", expires_at


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        header, payload, signature = token.split(".", 2)
        signing_input = f"{header}.{payload}"
        expected = _b64url(
            hmac.new(
                settings.app_access_token_secret.encode(),
                signing_input.encode(),
                hashlib.sha256,
            ).digest()
        )
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        claims = json.loads(_b64url_decode(payload))
        if (
            claims.get("type") != "access"
            or claims.get("iss") != "zhaoxingzhai"
            or int(claims["exp"]) <= int(datetime.now(UTC).timestamp())
            or not claims.get("sub")
        ):
            raise ValueError
        return claims
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=401, detail="登录凭证无效或已过期") from error


def bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("authorization", "").strip()
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def refresh_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
