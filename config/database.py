from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine,AsyncConnection
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy import text


class Database():

    def __init__(self,path):
        
        self.engine: AsyncEngine = create_async_engine(
            f"sqlite+aiosqlite:///{path}",
            pool_pre_ping=True, 
            pool_recycle=1800
        )

    async def execute(self, query: str, params=None):
        async with self.engine.begin() as conn:
            return await conn.execute(text(query), params or {})

    async def fetch_one(self, query: str, params=None):
        async with self.engine.connect() as conn:
            result = await conn.execute(text(query), params or {})
            return result.mappings().first()

    async def fetch_all(self, query: str, params=None):
        async with self.engine.connect() as conn:
            result = await conn.execute(text(query), params or {})
            return list(result.mappings().all())

    async def fetch_val(self, query: str, params=None):
        async with self.engine.connect() as conn:
            result = await conn.execute(text(query), params or {})
            return result.scalar()
        
    @asynccontextmanager
    async def transaction(self):
        
        async with self.engine.begin() as conn:
            # Create a helper bound to this specific transaction connection
            class TxHelper:
                async def execute(self, q, p=None):
                    return await conn.execute(text(q), p or {})
                async def fetch_one(self, q, p=None):
                    res = await conn.execute(text(q), p or {})
                    return res.mappings().first()
                async def fetch_all(self, q, p=None):
                    res = await conn.execute(text(q), p or {})
                    return list(res.mappings().all())
                async def fetch_val(self, q, p=None):
                    res = await conn.execute(text(q), p or {})
                    return res.scalar()

            yield TxHelper()

    async def close(self):
        await self.engine.dispose()

