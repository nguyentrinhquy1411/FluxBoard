from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time


class AuthError(Exception):
    pass


def normalize_email(email: str) -> str:
    return email.strip().lower()


# ── Password hashing (scrypt, stdlib only) ────────────────────────────────────

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_SCRYPT_MAXMEM = 64 * 1024 * 1024  # 64 MiB


def hash_password(plain: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(
        plain.encode(),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
        maxmem=_SCRYPT_MAXMEM,
    )
    salt_b64 = base64.b64encode(salt).decode("ascii")
    dk_b64 = base64.b64encode(dk).decode("ascii")
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt_b64}${dk_b64}"


def verify_password(plain: str, stored: str) -> bool:
    try:
        parts = stored.split("$")
        if len(parts) != 6 or parts[0] != "scrypt":
            return False
        n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
        salt = base64.b64decode(parts[4])
        expected_dk = base64.b64decode(parts[5])
        actual_dk = hashlib.scrypt(
            plain.encode(),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=len(expected_dk),
            maxmem=_SCRYPT_MAXMEM,
        )
        return hmac.compare_digest(actual_dk, expected_dk)
    except Exception:
        return False


# Pre-computed dummy hash for timing equalization on login (user not found path)
DUMMY_HASH = hash_password("dummy-timing-equalization-value-" + secrets.token_hex(8))


# ── JWT (stdlib HS256) ────────────────────────────────────────────────────────

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    # Re-pad to a multiple of 4
    pad = 4 - len(s) % 4
    if pad != 4:
        s += "=" * pad
    return base64.urlsafe_b64decode(s)


def encode_token(payload: dict, secret: str, ttl_minutes: int) -> str:
    now = int(time.time())
    full_payload = {**payload, "iat": now, "exp": now + ttl_minutes * 60}
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64url_encode(json.dumps(full_payload).encode())
    signing_input = f"{header}.{body}".encode()
    sig = _b64url_encode(hmac.new(secret.encode(), signing_input, hashlib.sha256).digest())
    return f"{header}.{body}.{sig}"


def decode_token(token: str, secret: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise AuthError("malformed token")
    header, body, provided_sig = parts
    signing_input = f"{header}.{body}".encode()
    expected_sig = _b64url_encode(hmac.new(secret.encode(), signing_input, hashlib.sha256).digest())
    if not hmac.compare_digest(expected_sig, provided_sig):
        raise AuthError("invalid signature")
    try:
        payload = json.loads(_b64url_decode(body))
    except Exception:
        raise AuthError("malformed payload")
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        raise AuthError("token expired")
    return payload
