from routematrix.auth import hash_password, verify_password


def test_password_hash_round_trip():
    salt, digest = hash_password("StrongPass123")
    assert salt
    assert digest
    assert verify_password("StrongPass123", salt, digest)
    assert not verify_password("WrongPass123", salt, digest)


def test_password_minimum_length():
    try:
        hash_password("short")
    except ValueError as exc:
        assert "10 characters" in str(exc)
    else:
        raise AssertionError("Expected short password to be rejected")
