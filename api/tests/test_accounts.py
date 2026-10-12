import pytest

from cortex import accounts


def test_password_hash_roundtrip_and_salting():
    h1, h2 = accounts.hash_password("correct horse"), accounts.hash_password("correct horse")
    assert h1 != h2  # per-user salt
    assert accounts.verify_password("correct horse", h1)
    assert not accounts.verify_password("wrong horse", h1)
    assert not accounts.verify_password("x", "garbage")
    assert "correct horse" not in h1


def test_email_and_password_validation():
    assert accounts.normalize_email("  Alice@Example.COM ") == "alice@example.com"
    for bad in ("", "nope", "a@b", "a b@c.com", "@c.com"):
        with pytest.raises(accounts.AccountError):
            accounts.normalize_email(bad)
    with pytest.raises(accounts.AccountError):
        accounts._check_password("short")


def test_login_throttle_window():
    accounts._FAILS.clear()
    for _ in range(accounts.MAX_FAILS):
        accounts._FAILS.setdefault("e:t@x.test", []).append(__import__("time").time())
    assert accounts._throttled("e:t@x.test")
    assert not accounts._throttled("e:other@x.test")
    accounts._FAILS.clear()
