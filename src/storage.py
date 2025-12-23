# storage.py
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
import aiomysql
logger = logging.getLogger(__name__)

class MySQLStorage:
    """
    用法：
        db = MySQLStorage(host, port, user, password, db, minsize=1, maxsize=10)
        await db.open()
        await db.upsert_one(item)   # item 必须包含 SQL 里用到的键，否则直接抛异常
        await db.close()
    """

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        db: str,
        minsize: int = 1,
        maxsize: int = 10,
        autocommit: bool = True,
        charset: str = "utf8mb4",
    ):
        self._cfg = dict(
            host=host,
            port=port,
            user=user,
            password=password,
            db=db,
            minsize=minsize,
            maxsize=maxsize,
            autocommit=autocommit,
            charset=charset,
        )
        self.pool: Optional[aiomysql.Pool] = None

        # 固定表结构时用固定 SQL（推荐：更安全、可控）
        self._upsert_sql = """
        INSERT INTO fang_listing (url, title, price, description)
        VALUES (%(url)s, %(title)s, %(price)s, %(description)s)
        ON DUPLICATE KEY UPDATE
          title=VALUES(title),
          price=VALUES(price),
          description=VALUES(description),
          updated_at=CURRENT_TIMESTAMP
        """

    async def open(self) -> None:
        if self.pool is not None:
            return
        self.pool = await aiomysql.create_pool(**self._cfg)

    async def close(self) -> None:
        if self.pool is None:
            return
        self.pool.close()
        await self.pool.wait_closed()
        self.pool = None

    def _require_pool(self) -> aiomysql.Pool:
        if self.pool is None:
            raise RuntimeError("MySQLStorage not opened. Call await db.open() first.")
        return self.pool

    # storage.py
    async def upsert_one(self,item: Dict[str,Any]) -> bool:
        """
        去重写入：
        - 已存在：直接跳过，返回 False
        - 不存在：执行 upsert，返回 True
        """
        pool = self._require_pool()
        url = item["url"]

        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                # ① 查重
                await cur.execute(
                    "SELECT 1 FROM fang_listing WHERE url=%s LIMIT 1",
                    (url,)
                )
                if await cur.fetchone():
                    return False

                # ② 不存在才写
                await cur.execute(self._upsert_sql,item)
                return True

    async def upsert_many(self, items: list[Dict[str, Any]], chunk_size: int = 200) -> int:
        """
        批量写入（可选，用于提吞吐）
        同样：不兜底，items 中任意 dict 缺字段就抛异常。
        """
        if not items:
            return 0

        pool = self._require_pool()
        total = 0

        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                for i in range(0, len(items), chunk_size):
                    chunk = items[i : i + chunk_size]
                    await cur.executemany(self._upsert_sql, chunk)
                    total += len(chunk)

        return total
