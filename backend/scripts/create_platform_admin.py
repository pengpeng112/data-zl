"""Backward-compatible entrypoint; prefer create_local_admin.

    python -m scripts.create_local_admin
    python -m scripts.create_platform_admin
"""

from __future__ import annotations

from scripts.create_local_admin import create_local_admin, main

# Re-export for callers that import create_platform_admin.create_token flow
create_platform_admin = create_local_admin

if __name__ == "__main__":
    main()
