"""Bind an existing API token to a platform user from a trusted shell."""

import argparse
import hashlib

from sqlalchemy import or_, select

from app.core.db import SessionLocal
from app.models.governance import ApiKey


def bind_token(token: str, user_identifier: str) -> None:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    db = SessionLocal()
    try:
        key = db.scalar(select(ApiKey).where(or_(ApiKey.token_hash == token_hash, ApiKey.token == token)))
        if not key:
            raise SystemExit("API token not found")
        key.token_hash = token_hash
        key.token = None
        key.user_identifier = user_identifier
        db.commit()
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Bind an API token to a platform user")
    parser.add_argument("--token", required=True)
    parser.add_argument("--user-identifier", required=True)
    args = parser.parse_args()
    bind_token(args.token, args.user_identifier)


if __name__ == "__main__":
    main()
