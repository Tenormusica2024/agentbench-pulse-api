"""
BigCodeBench（Hard）リーダーボードクローラー。

results-hard.json を取得し、モデルごとの pass@1 スコアを Supabase に upsert する。

データ構造:
  {
    "Model-Name": {
      "link": "https://...",
      "open-data": "Full" | "NONE",
      "pass@1": {"instruct": 42.5, "complete": 38.1},
      "prompted": true,
      "moe": false,
      "size": 7.0,
      "date": "2024-05-01"
    },
    ...
  }

クロール戦略:
  - snapshot_date = 各モデルの "date" フィールド（提出日）
  - date が null の場合は今日の日付を使用
  - UNIQUE制約により再クロール時の重複は無視される
  - primary_score = pass@1["instruct"]（null の場合は pass@1["complete"]）
"""

from datetime import date

import requests

from config import BIGCODEBENCH_URL, REQUEST_TIMEOUT, USER_AGENT
from db import get_supabase


def fetch_raw() -> dict:
    """BigCodeBench results-hard.json を取得する。"""
    r = requests.get(BIGCODEBENCH_URL, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    return r.json()


def transform(raw: dict) -> list[dict]:
    """JSONをSupabase upsert用レコードリストに変換する。"""
    today = date.today().isoformat()
    records = []

    for model_name, model_data in raw.items():
        pass_at_1 = model_data.get("pass@1") or {}
        instruct  = pass_at_1.get("instruct")
        complete  = pass_at_1.get("complete")

        # instruct スコアを優先。なければ complete を使用
        primary_score = instruct if instruct is not None else complete

        # モデルの提出日を使用（なければ今日）
        snapshot_date = model_data.get("date") or today

        records.append({
            "benchmark_id":  "bigcodebench",
            "model_name":    model_name,
            "primary_score": primary_score,
            "score_details": {"instruct": instruct, "complete": complete},
            "snapshot_date": snapshot_date,
            "metadata": {
                "link":      model_data.get("link"),
                "size":      model_data.get("size"),
                "open_data": model_data.get("open-data"),
                "prompted":  model_data.get("prompted"),
                "moe":       model_data.get("moe"),
            },
        })

    return records


def upsert(records: list[dict]) -> int:
    """Supabase に upsert し、処理件数を返す。"""
    if not records:
        return 0
    sb = get_supabase()
    sb.table("benchmark_results").upsert(records, on_conflict="benchmark_id,model_name,snapshot_date").execute()
    return len(records)


def main():
    today = date.today().isoformat()
    print(f"[BigCodeBench] クロール開始: {today}")

    raw = fetch_raw()
    print(f"[BigCodeBench] モデル数: {len(raw)}")

    records = transform(raw)
    print(f"[BigCodeBench] レコード数: {len(records)}")

    inserted = upsert(records)
    print(f"[BigCodeBench] upsert完了: {inserted}件")


if __name__ == "__main__":
    main()
