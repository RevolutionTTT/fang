# 限制并发量，避免一次性开太多请求
import aiohttp
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
CONCURRENT_REQUESTS = 10
base_url = 'https://esf.fang.com'
timeout = aiohttp.ClientTimeout(total=60,
                                sock_connect=60,  # socket连接超时
                                sock_read=60  # socket读取超时
                                )
# =========================
# MySQL 配置（新增）
# =========================
# storage 层只读这些变量，不做任何兜底

MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "password")
MYSQL_DB = os.getenv("MYSQL_DB", "fang_data")

# MySQL 连接池
MYSQL_POOL_MIN = int(os.getenv("MYSQL_POOL_MIN", "1"))
MYSQL_POOL_MAX = int(os.getenv("MYSQL_POOL_MAX", "10"))
headers = {
    "authority": "esf.fang.com",
    "method": "GET",
    "path": "/",
    "scheme": "https",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "zh-CN,zh;q=0.9",
    "cache-control": "max-age=0",
    "cookie": (
        "global_cookie=05vb0grx22gx8fxeqw3bx9kmo20mj6l1qgw; "
        "otherid=5b1aa8d6b57666aba9013b2b082328b7; "
        "csrfToken=WM2h-xx_TyPh3pWsXpU-VUJd; "
        "unique_cookie=U_8pozhhcz0aomfejmhhtqrophm2omjfhbdm2*2; "
        "g_sourcepage=esf_fy%5Elb_pc; "
        "city=www"
    ),
    "dnt": "1",
    "priority": "u=0, i",
    "referer": "https://www1.fang.com/",
    "sec-ch-ua": "\"Brave\";v=\"143\", \"Chromium\";v=\"143\", \"Not A(Brand\";v=\"24\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-site",
    "sec-fetch-user": "?1",
    "sec-gpc": "1",
    "upgrade-insecure-requests": "1",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/143.0.0.0 Safari/537.36"
    ),
}





