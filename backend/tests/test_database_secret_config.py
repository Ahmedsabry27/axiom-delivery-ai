import json

from app.database.config import database_url


class FakeSecretsManager:
    def get_secret_value(self, *, SecretId):
        assert SecretId == "test-secret"
        return {
            "SecretString": json.dumps(
                {
                    "username": "db-user",
                    "password": "p@ss:/word",
                    "dbname": "application",
                }
            )
        }


def test_database_url_resolves_aws_secret_without_logging(monkeypatch):
    monkeypatch.setenv("DATABASE_SECRET_ARN", "test-secret")
    monkeypatch.setenv("DATABASE_HOST", "db.example.test")
    monkeypatch.setenv("DATABASE_PORT", "5432")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(
        "app.database.config.boto3.client", lambda *args, **kwargs: FakeSecretsManager()
    )
    result = database_url()

    assert result.startswith("postgresql+psycopg://db-user:")
    assert "db.example.test:5432/application" in result
    assert "sslmode=require" in result
    assert "p@ss:/word" not in result
