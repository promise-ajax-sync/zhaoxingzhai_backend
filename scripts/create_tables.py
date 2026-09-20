import asyncio

from sqlalchemy import inspect

from app.core.database import create_engine
from app.models import Base


async def main() -> None:
    engine = create_engine()
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            tables = await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).get_table_names()
            )
        expected = set(Base.metadata.tables)
        missing = expected.difference(tables)
        if missing:
            raise RuntimeError(f"建表后仍缺少数据表：{sorted(missing)}")
        print("database-ready: " + ", ".join(sorted(expected)))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
