import jwt

from app.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_round_trip() -> None:
    hashed = hash_password("ValidPass123!")
    assert hashed != "ValidPass123!"
    assert verify_password("ValidPass123!", hashed)
    assert not verify_password("wrong-password", hashed)


def test_access_token_round_trip() -> None:
    token = create_access_token("080826001")
    assert decode_access_token(token) == "080826001"


def test_invalid_access_token() -> None:
    try:
        decode_access_token("not-a-token")
    except jwt.InvalidTokenError:
        pass
    else:
        raise AssertionError("Invalid token must be rejected")
