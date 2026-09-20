import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.auth import create_access_token, decode_access_token, hash_password, verify_password
from app.core.config import Settings
from app.schemas.auth import DeleteAccountRequest, RegisterRequest, UpdateProfileRequest


def test_password_hash_is_salted_and_verifiable() -> None:
    first = hash_password("correct-horse-battery-staple")
    second = hash_password("correct-horse-battery-staple")

    assert first != second
    assert "correct-horse-battery-staple" not in first
    assert verify_password("correct-horse-battery-staple", first)
    assert not verify_password("wrong-password", first)


def test_access_token_round_trip_and_tampering_rejection() -> None:
    settings = Settings(app_access_token_secret="unit-test-token-secret")
    token, expires_at = create_access_token("d10553ec-3434-48b5-bf7f-c5419a0b9540", settings)

    claims = decode_access_token(token, settings)
    assert claims["sub"] == "d10553ec-3434-48b5-bf7f-c5419a0b9540"
    assert claims["exp"] == int(expires_at.timestamp())

    with pytest.raises(HTTPException) as error:
        decode_access_token(f"{token[:-1]}x", settings)
    assert error.value.status_code == 401


def test_email_is_normalized_without_optional_email_validator_dependency() -> None:
    payload = RegisterRequest(email="  USER@Example.COM ", password="password123")
    assert payload.email == "user@example.com"

    with pytest.raises(ValidationError):
        RegisterRequest(email="not-an-email", password="password123")


def test_profile_update_distinguishes_omitted_fields_from_explicit_clear() -> None:
    name_only = UpdateProfileRequest.model_validate({"displayName": "  小明  "})
    clear_avatar = UpdateProfileRequest.model_validate({"avatarUrl": ""})

    assert name_only.display_name == "小明"
    assert "display_name" in name_only.model_fields_set
    assert "avatar_url" not in name_only.model_fields_set
    assert clear_avatar.avatar_url is None
    assert "avatar_url" in clear_avatar.model_fields_set


def test_account_deletion_requires_exact_confirmation() -> None:
    payload = DeleteAccountRequest(password="password123", confirmation="DELETE")
    assert payload.confirmation == "DELETE"

    with pytest.raises(ValidationError):
        DeleteAccountRequest(password="password123", confirmation="delete")
