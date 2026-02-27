"""
設定定数。環境変数から読み込む。
"""

import os

SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_KEY: str = os.environ["SUPABASE_KEY"]

# クロール設定
REQUEST_TIMEOUT: int = 30
USER_AGENT: str = "AgentBench-Pulse-Crawler/0.1 (https://github.com/Tenormusica2024/agentbench-pulse-api)"

# ベンチマークデータソースURL
SWEBENCH_URL: str     = "https://www.swebench.com/"
BIGCODEBENCH_URL: str = "https://bigcode-bench.github.io/results-hard.json"
EVALPLUS_URL: str     = "https://evalplus.github.io/results.json"
