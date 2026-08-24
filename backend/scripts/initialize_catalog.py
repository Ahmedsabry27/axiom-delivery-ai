from __future__ import annotations

import asyncio

from app.database.session import SessionLocal
from app.tool_discovery.indexing import index_tools
from app.tool_sdk.service import sync_catalog


async def main() -> None:
    with SessionLocal() as database:
        sync_catalog(database)
        await index_tools(database, "default", batch_size=500)


if __name__ == "__main__":
    asyncio.run(main())
