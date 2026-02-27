-- AgentBench Pulse API - Supabase Schema
-- ベンチマーク集約API用テーブル定義

-- ベンチマーク一覧
CREATE TABLE IF NOT EXISTS benchmarks (
  id         TEXT PRIMARY KEY,   -- 'swebench', 'bigcodebench', 'evalplus'
  name       TEXT NOT NULL,
  description TEXT,
  data_source_url TEXT,
  license    TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- ベンチマーク結果（モデルごとのスコア時系列）
CREATE TABLE IF NOT EXISTS benchmark_results (
  id             BIGSERIAL PRIMARY KEY,
  benchmark_id   TEXT NOT NULL REFERENCES benchmarks(id),
  model_name     TEXT NOT NULL,
  primary_score  FLOAT,          -- メインスコア（swebench: resolve%, bigcodebench: pass@1 instruct, evalplus: humaneval+）
  score_details  JSONB,          -- ベンチマーク固有のサブスコア
  snapshot_date  DATE NOT NULL,  -- クロール日 or モデル提出日
  metadata       JSONB,          -- link, size, cost 等
  created_at     TIMESTAMPTZ DEFAULT now(),
  UNIQUE(benchmark_id, model_name, snapshot_date)
);

-- クエリ効率化インデックス
CREATE INDEX IF NOT EXISTS idx_br_benchmark_date  ON benchmark_results(benchmark_id, snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_br_model           ON benchmark_results(model_name);
CREATE INDEX IF NOT EXISTS idx_br_primary_score   ON benchmark_results(benchmark_id, primary_score DESC NULLS LAST);

-- ベンチマーク初期データ投入
INSERT INTO benchmarks (id, name, description, data_source_url, license) VALUES
  ('swebench',       'SWE-bench',      'GitHub Issue解決タスク。resolve rateでモデルをランキング',          'https://www.swebench.com/',                          'MIT'),
  ('bigcodebench',   'BigCodeBench',   'コーディングベンチマーク（Hard）。pass@1 instructでランキング',     'https://bigcode-bench.github.io/results-hard.json',  'Apache-2.0'),
  ('evalplus',       'EvalPlus',       'HumanEval+/MBPP+ベンチマーク。humaneval+ pass@1でランキング',       'https://evalplus.github.io/results.json',            'MIT')
ON CONFLICT (id) DO NOTHING;
