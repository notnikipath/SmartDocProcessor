from shared.smartdoc_common import Role, decrypt_text, encrypt_text, has_permission, sign_token, verify_token


def test_encrypt_decrypt_roundtrip() -> None:
    key = "unit-test-key"
    source = "Sensitive payload"
    cipher = encrypt_text(source, key)
    plain = decrypt_text(cipher, key)
    assert plain == source


def test_sign_and_verify_token() -> None:
    token = sign_token({"sub": "user-1", "role": "operator"}, "secret", exp_minutes=5)
    payload = verify_token(token, "secret")
    assert payload is not None
    assert payload["sub"] == "user-1"


def test_permissions() -> None:
    assert has_permission(Role.ADMIN, "pipeline:run")
    assert has_permission(Role.OPERATOR, "upload:create")
    assert not has_permission(Role.REVIEWER, "pipeline:run")
