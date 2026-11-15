# apps.dsrag（Decision-Split RAG 旁路）

代码根已锁定。本包**不**修改 `apps.scar` 定案主链。

## 冒烟（S1 契约）

在仓库 `backend/` 下：

```bash
cd backend
.venv/bin/python -c "
from apps.dsrag.config import load_merged, make_run_id
from apps.dsrag.schema import Trace, Candidate, AnswerableDecision

m = load_merged()
print('policy_hash', m['policy_hash'])
print('top_k', m['base']['top_k'])
print('generator', m['base']['generator_model'])
print('run_id', make_run_id('R0', 'dev'))

t = Trace(
    id='smoke-1',
    config_id='R0',
    status='answer',
    question='测试？',
    candidates=[Candidate('c1', 0.9, 'hello')],
    answerable=AnswerableDecision('answerable', 0.8, 'ok'),
    generated=True,
    answer_text='hello',
    policy_hash=m['policy_hash'],
)
t2 = Trace.from_json(t.to_json())
assert t2.to_dict() == t.to_dict()
print('trace_roundtrip_ok')
"
```

## 配置

- `configs/base.yaml` — 路径 / 模型 / top_k  
- `configs/policy_dev.yaml` — Answerable 阈值（仅 dev）  

## 索引（S3）

```bash
cd backend
.venv/bin/python apps/dsrag/scripts/01_build_index.py
.venv/bin/python -c "from apps.dsrag.index import retrieve; print([c.chunk_id for c in retrieve('气瓶泄漏', 5)])"
```

**规则：** 更换 `chunks.jsonl` 或重建索引后，旧 `SCAR/artifacts/dsrag/` runs **作废**，须重跑评测。  
当前若向量服务 8001 不可用，自动回退 `sklearn_tfidf_char23`（见 `index/meta.yaml` 的 `backend`）。

## R0（S6）

```bash
cd backend
# 冒烟
.venv/bin/python apps/dsrag/scripts/03_run_r0.py --split dev --limit 5
# 全量 dev
.venv/bin/python apps/dsrag/scripts/03_run_r0.py --split dev
```

产物：`SCAR/artifacts/dsrag/r0_{split}_{YYYYMMDD}/`（`predictions.jsonl` + `summary.json` + `RUN_NOTE.md`）。  
R0 期望 Gen 调用率 **1.00**。

## R2（S7）

```bash
cd backend
.venv/bin/python apps/dsrag/scripts/04_run_r2.py --split dev --threshold 0.5
```

产物：`SCAR/artifacts/dsrag/r2_{split}_{YYYYMMDD}/`。  
短路题 `generated=false` / `status=refuse_evidence`；summary 含 B 漏放、A 误拦、Gen 调用率。

## 汇总（S8）

```bash
cd backend
.venv/bin/python apps/dsrag/scripts/06_summarize_unit.py
.venv/bin/python apps/dsrag/scripts/06_summarize.py \
  --pred ../SCAR/artifacts/dsrag/r0_dev_20260929/predictions.jsonl \
  --pred ../SCAR/artifacts/dsrag/r2_dev_20260929/predictions.jsonl \
  --split dev --label R0 --label 'R2@τ=0.5' \
  --preview-out ../SCAR/artifacts/dsrag/week1_preview_table.md
```

## 阈值扫描（S9 · 仅 dev）

```bash
cd backend
.venv/bin/python apps/dsrag/scripts/05_tune_threshold_dev.py \
  --pred ../SCAR/artifacts/dsrag/r2_dev_20260929/predictions.jsonl \
  --taus 0.3,0.4,0.5,0.6,0.7
```

产物：`SCAR/artifacts/dsrag/threshold_scan_dev_YYYYMMDD/`（`curve.md` / `chosen_tau.txt`）。**禁止**用 test 选 τ。

## 周报（S10）

见 `DS-RAG/reports/week1_gate_preview.md`（镜像：`SCAR/artifacts/dsrag/reports/`）。  
本周终点；**S11 仅当人类明确下令**。

## S11（Scope / R1 / R3 · 已下令完成）

```bash
cd backend
.venv/bin/python apps/dsrag/scripts/03_make_taskset_v1.py
.venv/bin/python apps/dsrag/scripts/09_run_eval.py --config R0 --split test
.venv/bin/python apps/dsrag/scripts/09_run_eval.py --config R1 --split test
.venv/bin/python apps/dsrag/scripts/09_run_eval.py --config R2 --split test
.venv/bin/python apps/dsrag/scripts/09_run_eval.py --config R3 --split test
```

主表 / 门禁：`SCAR/artifacts/dsrag/s11_test_main_20260929/MANIFEST.md`  
失败案例：`DS-RAG/reports/s11_failure_cases.md`

## S12（R2-rule 对照）

```bash
cd backend
.venv/bin/python apps/dsrag/scripts/10_tune_r2_rule_dev.py --prepare-scores --run-test
```

分析：`DS-RAG/reports/s12_r2_rule_contrast.md`
