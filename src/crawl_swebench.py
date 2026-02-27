"""
SWE-bench リーダーボードクローラー。

swebench.com のHTMLに埋め込まれた JSON データ（id="leaderboard-data"）を解析し、
モデルごとのresolve rateをSupabaseに upsert する。

データ構造:
  [
    {
      "name": "Verified",
      "results": [
        {"name": "Claude Opus 4.5", "resolved": 76.8, "date": "2026-02-17", "cost": 376.95, ...},
        ...
      ]
    },
    ...  # bash-only, Multilingual, Test, Lite, Multimodal カテゴリ
  ]

クロール戦略:
  - snapshot_date = 今日（クロール日）
  - UNIQUE(benchmark_id, model_name, snapshot_date) により同日の重複は無視
  - カテゴリ="Verified" のみ primary_score として使用。
    他カテゴリは score_details に格納してAPIから参照可能にする
"""

import json
from datetime import date

import requests
from bs4 import BeautifulSoup

from config import SWEBENCH_URL, REQUEST_TIMEOUT, USER_AGENT
from db import get_supabase


# Verified カテゴリのスコアを primary_score として使用する
_PRIMARY_CATEGORY = "Verified"


def fetch_raw() -> list[dict]:
    """swebench.com からリーダーボードJSONを取得する。"""
    r = requests.get(SWEBENCH_URL, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    script = soup.find("script", id="leaderboard-data")
    if not script or not script.string:
        raise ValueError("leaderboard-data スクリプトタグが見つかりません")
    return json.loads(script.string)


def transform(raw: list[dict], today: str) -> list[dict]:
    """
    各カテゴリのresultsをフラット化し、upsert用のレコードリストに変換する。

    同一モデルが複数カテゴリに存在する場合は、
    _PRIMARY_CATEGORY のスコアを primary_score とし、
    残りを score_details["categories"] に格納する。
    """
    # model_name -> {category: entry} のマップを作る
    model_map: dict[str, dict] = {}
    for category in raw:
        cat_name = category.get("name", "Unknown")
        for entry in category.get("results", []):
            name = entry.get("name")
            if not name:
                continue
            if name not in model_map:
                model_map[name] = {}
            model_map[name][cat_name] = entry

    records = []
    for model_name, cats in model_map.items():
        # Verified カテゴリがあればそれを primary とする
        primary_entry = cats.get(_PRIMARY_CATEGORY) or next(iter(cats.values()))
        primary_score = primary_entry.get("resolved")

        # 全カテゴリのスコアを score_details に格納
        categories_detail = {
            cat: {
                "resolved": e.get("resolved"),
                "cost":     e.get("cost"),
                "date":     e.get("date"),
                "tags":     e.get("tags"),
            }
            for cat, e in cats.items()
        }

        records.append({
            "benchmark_id":   "swebench",
            "model_name":     model_name,
            "primary_score":  primary_score,
            "score_details":  {"categories": categories_detail},
            "snapshot_date":  today,
            "metadata": {
                "cost":           primary_entry.get("cost"),
                "date_submitted": primary_entry.get("date"),
                "tags":           primary_entry.get("tags"),
            },
        })

    return records


def upsert(records: list[dict]) -> int:
    """Supabase に upsert し、処理件数を返す。"""
    if not records:
        return 0
    sb = get_supabase()
    # UNIQUE制約(benchmark_id, model_name, snapshot_date) により重複は無視
    sb.table("benchmark_results").upsert(records, on_conflict="benchmark_id,model_name,snapshot_date").execute()
    return len(records)


def main():
    today = date.today().isoformat()
    print(f"[SWE-bench] クロール開始: {today}")

    raw = fetch_raw()
    print(f"[SWE-bench] カテゴリ数: {len(raw)}")

    records = transform(raw, today)
    print(f"[SWE-bench] レコード数: {len(records)}")

    inserted = upsert(records)
    print(f"[SWE-bench] upsert完了: {inserted}件")


if __name__ == "__main__":
    main()
