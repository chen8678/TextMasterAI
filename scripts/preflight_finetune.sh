#!/usr/bin/env bash
# 微调前资源检查 — 建议在训练前运行
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MIN_FREE_GB=4

echo "========================================"
echo "微调前资源检查 (M3 Pro 最简方案)"
echo "========================================"

echo ""
echo "[1] 硬件摘要"
python3 "$PROJECT_ROOT/scripts/check_finetune_env.py" | sed -n '/微调环境检测报告/,/====/p' | head -20

echo ""
echo "[2] 当前内存 (Pages free)"
memory_pressure 2>/dev/null | head -6 || vm_stat | head -6

FREE_PAGES=$(memory_pressure 2>/dev/null | awk '/Pages free/{print $3}' || echo 0)
if [[ "$FREE_PAGES" =~ ^[0-9]+$ ]]; then
  FREE_GB=$(python3 -c "print(round($FREE_PAGES * 16384 / 1024**3, 2))")
  echo "估算可用内存: ~${FREE_GB} GB"
  if python3 -c "exit(0 if $FREE_GB >= $MIN_FREE_GB else 1)"; then
    echo "✅ 空闲内存尚可"
  else
    echo "⚠️  空闲内存偏低，建议先释放资源"
  fi
fi

echo ""
echo "[3] 占用较高的进程"
ps aux -m 2>/dev/null | head -8

echo ""
echo "[4] Docker / Ollama"
docker ps --format '  {{.Names}} {{.Status}}' 2>/dev/null | head -5 || echo "  Docker 容器: 无"
if pgrep -x ollama >/dev/null 2>&1; then
  echo "  Ollama: 运行中"
  ollama list 2>/dev/null | sed 's/^/    /'
else
  echo "  Ollama: 未运行"
fi

echo ""
echo "[5] 训练数据"
TRAIN="$PROJECT_ROOT/backend/data/sft/train.jsonl"
VAL="$PROJECT_ROOT/backend/data/sft/val.jsonl"
if [[ -f "$TRAIN" && -f "$VAL" ]]; then
  TC=$(wc -l < "$TRAIN" | tr -d ' ')
  VC=$(wc -l < "$VAL" | tr -d ' ')
  echo "  train: $TC 条 | val: $VC 条"
else
  echo "  ❌ 缺少 train/val，请运行 python3 scripts/prepare_sft_dataset.py"
fi

echo ""
echo "[6] 微调环境"
if [[ -f "$PROJECT_ROOT/.venv-finetune/bin/activate" ]]; then
  echo "  ✅ 虚拟环境已安装"
else
  echo "  ❌ 未安装，请运行: bash scripts/setup_finetune_minimal.sh"
fi
if [[ -d "$PROJECT_ROOT/vendor/LLaMA-Factory" ]]; then
  echo "  ✅ LLaMA-Factory 已克隆"
else
  echo "  ❌ LLaMA-Factory 未安装"
fi

echo ""
echo "========================================"
echo "训练前建议释放资源:"
echo "  ollama stop bge-m3          # 释放 ~1.2GB"
echo "  docker compose down         # 若在跑 KB"
echo "  关闭 Chrome / 微信 等大应用"
echo ""
echo "推荐方案:"
echo "  模型: Qwen2.5-1.5B-Instruct"
echo "  框架: LLaMA-Factory + LoRA"
echo "  预计耗时: 20~60 分钟 (16 train / 2 epoch)"
echo "========================================"
