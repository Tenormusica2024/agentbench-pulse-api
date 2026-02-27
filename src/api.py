"""
AgentBench Pulse API
FastAPI アプリケーション。Supabase からベンチマーク集約データを提供する。

エンドポイント:
  GET /health                                     - ヘルスチェック
  GET /benchmarks                                 - 利用可能なベンチマーク一覧
  GET /benchmarks/{benchmark_id}/leaderboard      - 最新リーダーボード
  GET /models/{model_name}/scores                 - モデルの全ベンチマークスコア
  GET /benchmarks/{benchmark_id}/models/{model_name}/history - モデルのスコア時系列
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from db import get_supabase

app = FastAPI(
    title="AgentBench Pulse API",
    description="SWE-bench / BigCodeBench / EvalPlus のスコアを集約した時系列APIです。",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/benchmarks")
def list_benchmarks():
    """利用可能なベンチマークの一覧を返す。"""
    sb = get_supabase()
    try:
        resp = sb.table("benchmarks").select("*").order("id").execute()
    except Exception as e:
        raise HTTPException(status_code=503, detail="Database unavailable") from e
    return resp.data


@app.get("/benchmarks/{benchmark_id}/leaderboard")
def get_leaderboard(
    benchmark_id: str,
    limit: int = Query(50, ge=1, le=200, description="最大返却件数"),
    snapshot_date: Optional[str] = Query(None, description="特定日 (YYYY-MM-DD)。省略時は最新スナップショット"),
):
    """
    指定ベンチマークのリーダーボードを返す（primary_score 降順）。
    snapshot_date 未指定時は最新クロール日のデータを使用する。
    """
    sb = get_supabase()

    # snapshot_date が未指定なら最新日を取得
    if not snapshot_date:
        try:
            latest = (
                sb.table("benchmark_results")
                .select("snapshot_date")
                .eq("benchmark_id", benchmark_id)
                .order("snapshot_date", desc=True)
                .limit(1)
                .execute()
            )
        except Exception as e:
            raise HTTPException(status_code=503, detail="Database unavailable") from e
        if not latest.data:
            raise HTTPException(status_code=404, detail=f"ベンチマーク '{benchmark_id}' のデータがありません")
        snapshot_date = latest.data[0]["snapshot_date"]

    try:
        resp = (
            sb.table("benchmark_results")
            .select("model_name, primary_score, score_details, snapshot_date, metadata")
            .eq("benchmark_id", benchmark_id)
            .eq("snapshot_date", snapshot_date)
            .order("primary_score", desc=True, nullsfirst=False)
            .limit(limit)
            .execute()
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail="Database unavailable") from e

    if not resp.data:
        raise HTTPException(status_code=404, detail=f"'{benchmark_id}' ({snapshot_date}) のデータが見つかりません")

    return {"benchmark_id": benchmark_id, "snapshot_date": snapshot_date, "results": resp.data}


@app.get("/models/{model_name}/scores")
def get_model_scores(
    model_name: str,
    days: int = Query(90, ge=1, le=365, description="取得する過去の日数"),
):
    """
    指定モデルの全ベンチマークにわたる最新スコアを返す。
    各ベンチマークにつき最新の1件のみを返す。
    """
    sb = get_supabase()
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    try:
        resp = (
            sb.table("benchmark_results")
            .select("benchmark_id, primary_score, score_details, snapshot_date, metadata")
            .eq("model_name", model_name)
            .gte("snapshot_date", cutoff)
            .order("snapshot_date", desc=True)
            .execute()
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail="Database unavailable") from e

    if not resp.data:
        raise HTTPException(status_code=404, detail=f"モデル '{model_name}' のデータが見つかりません")

    # ベンチマークごとに最新1件のみを返す
    seen: set[str] = set()
    latest_scores = []
    for row in resp.data:
        bid = row["benchmark_id"]
        if bid not in seen:
            seen.add(bid)
            latest_scores.append(row)

    return {"model_name": model_name, "scores": latest_scores}


@app.get("/benchmarks/{benchmark_id}/models/{model_name}/history")
def get_model_history(
    benchmark_id: str,
    model_name: str,
    limit: int = Query(30, ge=1, le=180, description="最大返却件数"),
):
    """
    指定ベンチマーク × モデルのスコア時系列を返す（snapshot_date 降順）。
    SWE-bench のように毎日クロールされるベンチマークで時系列変化を追跡できる。
    """
    sb = get_supabase()
    try:
        resp = (
            sb.table("benchmark_results")
            .select("primary_score, score_details, snapshot_date, metadata")
            .eq("benchmark_id", benchmark_id)
            .eq("model_name", model_name)
            .order("snapshot_date", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail="Database unavailable") from e

    if not resp.data:
        raise HTTPException(
            status_code=404,
            detail=f"'{benchmark_id}' における '{model_name}' のデータが見つかりません",
        )

    return {"benchmark_id": benchmark_id, "model_name": model_name, "history": resp.data}
