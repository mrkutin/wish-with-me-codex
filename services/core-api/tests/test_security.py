from app.security import create_access_token, create_refresh_token, decode_token, verify_password, hash_password


def test_password_hashing_roundtrip():
    password = "s3cret"
    hashed = hash_password(password)
    assert verify_password(password, hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_decodes():
    token, _ = create_access_token("user-id", ["user"])
    payload = decode_token(token)
    assert payload["sub"] == "user-id"
    assert payload["type"] == "access"


def test_refresh_token_decodes():
    token, jti, _ = create_refresh_token("user-id")
    payload = decode_token(token)
    assert payload["sub"] == "user-id"
    assert payload["type"] == "refresh"
    assert payload["jti"] == jti
