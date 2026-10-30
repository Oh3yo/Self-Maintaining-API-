from client import user_email


def test_user_email_uses_renamed_api_field(monkeypatch):
    monkeypatch.setattr(
        "client.get_user",
        lambda user_id: {
            "id": user_id,
            "email_address": "tsu@example.com",
        },
    )

    assert user_email(1) == "tsu@example.com"