# generate_proxy_env.py
from proxy_config import raw_proxies_,q_n

raw_proxies = raw_proxies_.strip().splitlines()


def to_socks5(line: str) -> str:
    host, port, user, password = line.strip().split(":")
    return f"socks5://{user}:{password}@{host}:{port}"


proxies = [to_socks5(p) for p in raw_proxies]

proxy_pool_1 = "|".join(proxies[:q_n])
proxy_pool_2 = "|".join(proxies[q_n:])

env_content = f"""PROXY_POOL={proxy_pool_1}

PROXY_POOL2={proxy_pool_2}
"""

with open(".env", "w", encoding="utf-8") as f:
    f.write(env_content)

print("✓ 已生成 .env 文件")
print("PROXY_POOL  : 10 个")
print("PROXY_POOL2 : 40 个")
