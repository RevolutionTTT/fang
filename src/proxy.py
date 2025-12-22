import os
from dotenv import load_dotenv

load_dotenv()

PROXY_POOL = os.getenv("PROXY_POOL").split("|")
PROXY_POOL2 = os.getenv("PROXY_POOL2").split("|")