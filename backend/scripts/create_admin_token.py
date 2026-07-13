"""Create one API token from a trusted local/deployment shell.

The raw token is printed once and is never exposed through HTTP.
"""

import argparse
import hashlib
import secrets

from app.core.db import SessionLocal
from app.models.governance import ApiKey


def create_token(key_name: str, user_identifier: str) -> str:
    token = secrets.token_urlsafe(32)
    db = SessionLocal()
    try:
        db.add(ApiKey(
            key_name=key_name,
            token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            user_identifier=user_identifier,
        ))
        db.commit()
        return token
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an API token")
    parser.add_argument("--key-name", default="platform-admin")
    parser.add_argument("--user-identifier", required=True)
    args = parser.parse_args()
    print(create_token(args.key_name, args.user_identifier))


if __name__ == "__main__":
    main()
