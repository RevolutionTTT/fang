import os
from dotenv import load_dotenv

load_dotenv()

PROXY_POOL = os.getenv("PROXY_POOL").split("|")
