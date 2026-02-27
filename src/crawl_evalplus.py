"""
EvalPlus（HumanEval+/MBPP+）リーダーボードクローラー。

results.json を取得し、モデルごとの pass@1 スコアを Supabase に upsert する。

データ構造:
  {
    "Model-Name": {
      "link": "https://...",
      "open-data": "NONE" | "Full",
      "pass@1": {"humaneval": 89.0, "humaneval+": 79.3, "mbpp": 89.7, "mbpp+": 74.6},
      "prompted": true,
      "size": null
    },
    ...
  }

クロール戦略:
  - snapshot_date = 今日のクロール日（EvalPlus データに日付フィールドなし）
  - UNIQUE制約により同日の再クロールは重複なし
  - primary_score = pass@1["humaneval+"]（より厳密なプラス版を採用）
"""

from datetime import date

import requests

from config import EVALPLUS_URL, REQUEST_TIMEOUT, USER_AGENT
from db import get_supabase


def fetch_raw() -> dict:
    """EvalPlus results.json を取得する。"""
    r = requests.get(EVALPLUS_URL, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    return r.json()


def transform(raw: dict) -> list[dict]:
    """JSONをSupabase upsert用レコードリストに変換する。"""
    today = date.today().isoformat()
    records = []

    for model_name, model_data in raw.items():
        pass_at_1 = model_data.get("pass@1") or {}

        humaneval_plus = pass_at_1.get("humaneval+")
        humaneval      = pass_at_1.get("humaneval")
        mbpp_plus      = pass_at_1.get("mbpp+")
        mbpp           = pass_at_1.get("mbpp")

        # humaneval+ を primary とする（より厳密な評価指標）
        primary_score = humaneval_plus

        records.append({
            "benchmark_id":  "evalplus",
            "model_name":    model_name,
            "primary_score": primary_score,
            "score_details": {
                "humaneval":  humaneval,
                "humaneval+": humaneval_plus,
                "mbpp":       mbpp,
                "mbpp+":      mbpp_plus,
            },
            "snapshot_date": today,
            "metadata": {
                "link":      model_data.get("link"),
                "size":      model_data.get("size"),
                "open_data": model_data.get("open-data"),
                "prompted":  model_data.get("prompted"),
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
    print(f"[EvalPlus] クロール開始: {today}")

    raw = fetch_raw()
    print(f"[EvalPlus] モデル数: {len(raw)}")

    records = transform(raw)
    print(f"[EvalPlus] レコード数: {len(records)}")

    inserted = upsert(records)
    print(f"[EvalPlus] upsert完了: {inserted}件")


if __name__ == "__main__":
    main()
