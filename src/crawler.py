import aiohttp
import asyncio
from asyncio import Semaphore
import itertools
import config
import parser
from tenacity import retry,stop_after_attempt,retry_if_exception_type, wait_exponential
import seed_urls
from aiohttp_socks import ProxyConnector
from proxy import PROXY_POOL,PROXY_POOL2
import logging
import os
from storage import MySQLStorage

# 限制并发量，避免一次性开太多请求
CONCURRENT_REQUESTS = config.CONCURRENT_REQUESTS
headers = config.headers #请求头设置
#页面链接
base_url = config.base_url
#日志配置
LOG_DIR = "../log"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "crawler.log") #文件路径
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.handlers:
    '''控制台输出'''
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(console_formatter)
    '''文件输出,每次运行覆盖原日志'''
    file_handler = logging.FileHandler(LOG_FILE,mode="w",encoding="utf-8")
    file_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    )
    file_handler.setFormatter(file_formatter)

    # 添加到 logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

#连接器管理器：为每个连接器配置代理
class ProxyManager:

    def __init__(self,proxy_pool):
        self.proxy_pool = proxy_pool #代理池，用 proxy_pool[idx] = new_proxy替换
        self.connectors = []  # 存储配置了代理的连接器
        self.sessions = []  # 存储使用这些连接器的会话
        self.current_index = 0 #轮询代理会话
        self.initialized = False #标记连接器是否已经初始化过
        self.proxy_index = {} #以键值对的形式存储代理索引
        self.proxy_pool2 = PROXY_POOL2
        self._replace_lock = asyncio.Lock()

    async def init_connectors(self):
        """ 为代理池中的每个代理创建专用的连接器 """
        if self.initialized:
            return

        logger.info(f"正在创建 {len(self.proxy_pool)} 个配置了代理的连接器...")

        for a,proxy_url in enumerate(self.proxy_pool):
            try:
                """ 创建连接器并配置代理 """
                connector = ProxyConnector.from_url(
                    proxy_url,  # 这里配置代理
                    limit=5,  # 连接池大小
                    limit_per_host=3,  # 每个主机限制
                    keepalive_timeout=5,
                )

                # 创建使用该连接器的会话
                session = aiohttp.ClientSession(
                    connector=connector,
                    timeout=config.timeout,
                    headers=headers,

                )
                self.connectors.append(connector)
                self.sessions.append(session)
                self.proxy_index[proxy_url] = a #通过代理名称拿到它的索引，方便替换失效代理
                logger.info(f"✓ 创建连接器并配置代理: {proxy_url}")

            except Exception as e:
                logger.warning(f"✗ 创建代理连接器失败 {proxy_url}: {e}")
                continue

        # 如果没有代理，创建直连连接器
        if not self.connectors:
            logger.warning("没有可用代理，创建直连连接器")
            connector = aiohttp.TCPConnector(limit=28)
            session = aiohttp.ClientSession(
                connector=connector,
                timeout=config.timeout,
                headers=headers
            )
            self.connectors.append(connector)
            self.sessions.append(session)

        self.initialized = True
        logger.info(f"连接器初始化完成，共有 {len(self.connectors)} 个连接器")

    def get_session(self):
        """轮询返回 (session, idx, current_proxy)"""
        if not self.sessions:
            return None

        idx = self.current_index % len(self.sessions)
        self.current_index += 1

        session = self.sessions[idx]
        current_proxy = self.proxy_pool[idx] if idx < len(self.proxy_pool) else "直连"
        return session,idx,current_proxy

    def get_connector_count(self):
        """返回连接器数量"""
        return len(self.connectors)

    def get_proxy_info(self,index):
        """获取指定连接器配置的代理信息"""
        if index < len(self.proxy_pool):
            return self.proxy_pool[index]
        return "直连"

    async def replace_proxy(self,idx: int):
        async with self._replace_lock:
            if idx < 0 or idx >= len(self.sessions):
                logger.warning(f"无效 idx，跳过替换: idx={idx}")
                return

            if not self.proxy_pool2:
                logger.warning("备用代理池已空，无法替换")
                return

            bad_proxy = self.proxy_pool[idx]
            new_proxy = self.proxy_pool2.pop(0)

            logger.warning(f"♻️ 替换失效代理(idx={idx}): {bad_proxy} -> {new_proxy}")

            # 关闭旧资源
            try:
                await self.sessions[idx].close()
            except Exception as e:
                logger.warning(f"关闭旧 session 失败: {e}")

            try:
                await self.connectors[idx].close()
            except Exception as e:
                logger.warning(f"关闭旧 connector 失败: {e}")

            # 创建新 connector / session
            connector = ProxyConnector.from_url(
                new_proxy,
                limit=20,
                limit_per_host=12,
                keepalive_timeout=5,
            )
            session = aiohttp.ClientSession(
                connector=connector,
                timeout=config.timeout,
                headers=headers,
            )

            # 原位替换（idx 不变）
            self.proxy_pool[idx] = new_proxy
            self.connectors[idx] = connector
            self.sessions[idx] = session

    async def close_all(self):
        """关闭所有连接器和会话"""
        logger.info("正在关闭所有连接器和会话...")

        for i,session in enumerate(self.sessions):
            try:
                await session.close()
                proxy_info = self.get_proxy_info(i)
                logger.info(f"✓ 已关闭代理会话: {proxy_info}")
            except Exception as e:
                logger.warning(f"✗ 关闭会话时出错: {e}")

        for i,connector in enumerate(self.connectors):
            try:
                await connector.close()
                proxy_info = self.get_proxy_info(i)
                logger.info(f"✓ 已关闭连接器: {proxy_info}")
            except Exception as e:
                logger.warning(f"✗ 关闭连接器时出错: {e}")


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=10),  # 指数退避
    retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
)
# crawler.py

async def scrape_fang_details(fang_url, sem, proxy_manager, db):
    async with sem:
        session_info = proxy_manager.get_session()
        if not session_info:
            logger.warning(f"✗ 没有可用会话，跳过详情页: {fang_url}")
            return None

        session, idx,current_proxy = session_info

        try:
            async with session.get(fang_url) as resp:
                if resp.status != 200:
                    logger.warning(f"✗ [{current_proxy}] 详情页状态码 {resp.status}: {fang_url}")
                    return None

                html = await resp.text()
                parsed = parser.parse_fang_detail(html)
                # ❌ 解析失败（返回 {} 或 None），直接跳过
                if not parsed:
                    logger.warning(f"✗ [{current_proxy}] 解析失败，跳过: {fang_url}")
                    return None
                # ✅ crawler 负责注入上下文 & 规范化字段键；storage 不兜底、不校验
                record = {
                    "url": fang_url,
                    "title": parsed.get("title"),
                    "price": parsed.get("price"),
                    "description": parsed.get("description"),
                }

                try:
                    await db.upsert_one(record)  # 单条立刻入库
                    logger.info(f"✓ [{current_proxy}] 入库成功: {fang_url}")
                    return record
                except Exception as e:
                    # ✅ 入库失败只影响当前任务，不能拖死整批 gather
                    logger.error(
                        "✗ 入库失败 proxy=%s url=%s err=%s record=%r",
                        current_proxy, fang_url, e, record
                    )
                    return None

        except Exception as e:
            # 这里保留你现有的：超时/代理失败/网络异常处理逻辑（需要的话在此处替换代理）
            logger.warning(f"✗ [{current_proxy}] 请求错误 {fang_url}: {e}")
            await proxy_manager.replace_proxy(idx)
            return None



@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=10),  # 指数退避
    retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
)
async def fetch_fang_urls(url,sem,proxy_manager):
    """获房产列表页链接 - 使用配置了代理的连接器"""
    async with sem:
        session_info = proxy_manager.get_session()
        if not session_info:
            logger.warning(f"✗ 没有可用的会话，跳过 {url}")
            return []

        session,idx,current_proxy = session_info

        try:
            async with session.get(url,ssl=False) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    fang_urls = parser.parse_fang_href(html)
                    logger.info(f"✓ [{current_proxy}] 成功解析页面 {url}, 找到 {len(fang_urls)} 房产链接")
                    return fang_urls
                else:
                    logger.warning(f"✗ [{current_proxy}] 页面请求失败 {url}, 状态码: {resp.status}")
                    return []
        except Exception as e:
            logger.warning(f"✗ [{current_proxy}] 页面请求错误 {url}: {e}")
            await proxy_manager.replace_proxy(idx)
            return []


async def main():
    # 创建连接器管理器
    proxy_manager = ProxyManager(PROXY_POOL)
    await proxy_manager.init_connectors()

    # ✅ MySQL 持久连接池
    db = MySQLStorage(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        db=config.MYSQL_DB,
        minsize=getattr(config, "MYSQL_POOL_MIN", 1),
        maxsize=getattr(config, "MYSQL_POOL_MAX", 10),
    )
    await db.open()

    try:
        # 获取所有列表页URL
        urls = seed_urls.generate_page_urls()
        logger.info(f"共有 {len(urls)} 个列表页需要爬取")
        logger.info(f"创建了 {proxy_manager.get_connector_count()} 个配置了代理的连接器")

        # 设置并发信号量
        sem = Semaphore(CONCURRENT_REQUESTS)

        # 1) 先抓列表页 -> 拿详情页链接
        logger.info("开始获取房产链接...")
        fang_tasks = [fetch_fang_urls(url, sem, proxy_manager) for url in urls]
        results = await asyncio.gather(*fang_tasks)

        # results 是二维 list，拍平
        flat_urls = list(itertools.chain.from_iterable(results))
        flat_urls = [u for u in flat_urls if u]  # 去掉空值
        flat_urls = list(set(flat_urls))
        logger.info(f"成功获取 {len(flat_urls)} 个详情页链接")

        # 2) 抓详情页 -> 每条立刻写入 MySQL（不再堆内存、不再一次性 storage()）
        logger.info("开始爬取详情页并逐条入库...")
        detail_tasks = [scrape_fang_details(u, sem, proxy_manager, db) for u in flat_urls]
        detail_results = await asyncio.gather(*detail_tasks)

        success_count = sum(1 for r in detail_results if r)
        logger.info(f"详情页完成：成功入库 {success_count} 条（失败/跳过 {len(detail_results) - success_count} 条）")

    finally:
        # ✅ 关闭资源（顺序：先关会话/代理，再关 DB 也可以；关键是都要关）
        await proxy_manager.close_all()
        await db.close()



if __name__ == "__main__":
    asyncio.run(main())