#!/usr/bin/env bash
# 最简本机微调环境安装 — M3 Pro + Qwen2.5-1.5B + LLaMA-Factory
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FINETUNE_DIR="$PROJECT_ROOT/finetune"
VENV_DIR="$PROJECT_ROOT/.venv-finetune"
LF_DIR="$PROJECT_ROOT/vendor/LLaMA-Factory"
DATA_SRC="$PROJECT_ROOT/backend/data/sft"

echo "==> 项目根目录: $PROJECT_ROOT"

# LLaMA-Factory 需要 Python >= 3.11；避免 pyenv 默认 3.9 误用
PYTHON_BIN=""
for candidate in \
  "${PYTHON_BIN_OVERRIDE:-}" \
  /opt/homebrew/bin/python3.14 \
  /opt/homebrew/bin/python3.12 \
  /opt/homebrew/bin/python3.11 \
  /opt/homebrew/bin/python3 \
  "$(command -v python3.14 2>/dev/null || true)" \
  "$(command -v python3.12 2>/dev/null || true)" \
  "$(command -v python3.11 2>/dev/null || true)"; do
  [[ -n "$candidate" && -x "$candidate" ]] || continue
  if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
    PYTHON_BIN="$candidate"
    break
  fi
done

if [[ -z "$PYTHON_BIN" ]]; then
  echo "❌ 未找到 Python >= 3.11"
  echo "   可安装: brew install python@3.12"
  echo "   或指定: PYTHON_BIN_OVERRIDE=/path/to/python3.12 bash $0"
  exit 1
fi
echo "==> 使用 Python: $PYTHON_BIN ($("$PYTHON_BIN" --version))"

if [[ ! -f "$DATA_SRC/train.jsonl" ]]; then
  echo "缺少训练数据，请先运行:"
  echo "  python3 scripts/prepare_sft_dataset.py"
  exit 1
fi

echo "==> 创建虚拟环境: $VENV_DIR"
if [[ -d "$VENV_DIR" ]]; then
  echo "   删除旧虚拟环境（可能由 Python 3.9 创建）"
  rm -rf "$VENV_DIR"
fi
"$PYTHON_BIN" -m venv "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
python -m pip install -U pip wheel

echo "==> 安装微调依赖（精简）"
pip install "torch>=2.1" "transformers>=4.41" "datasets>=2.16.0" peft accelerate sentencepiece tiktoken protobuf pyyaml

if [[ ! -d "$LF_DIR/.git" ]]; then
  echo "==> 克隆 LLaMA-Factory"
  mkdir -p "$(dirname "$LF_DIR")"
  git clone --depth 1 https://github.com/hiyouga/LLaMA-Factory.git "$LF_DIR"
fi

echo "==> 安装 LLaMA-Factory"
pip install -e "$LF_DIR"

# Python 3.14 需要 datasets>=4.4.0 修复 pickle 兼容性（LLaMA-Factory 上限声明偏旧）
PY_MINOR="$("$PYTHON_BIN" -c 'import sys; print(sys.version_info.minor)')"
if [[ "$PY_MINOR" -ge 14 ]]; then
  echo "==> Python 3.14+：升级 datasets 以修复加载数据报错"
  pip install "datasets>=4.4.0,<5"
fi

echo "==> 链接训练数据到 LLaMA-Factory/data/"
mkdir -p "$LF_DIR/data/english_vocab_sft"
ln -sf "$DATA_SRC/train.jsonl" "$LF_DIR/data/english_vocab_sft/train.jsonl"
ln -sf "$DATA_SRC/val.jsonl" "$LF_DIR/data/english_vocab_sft/val.jsonl"

python3 - <<'PY'
import json
from pathlib import Path

project = Path(__file__).resolve().parent if '__file__' in dir() else Path.cwd()
# fix path when run from bash heredoc - use env
PY

python3 - "$PROJECT_ROOT" <<'PY'
import json, sys
from pathlib import Path
project = Path(sys.argv[1])
lf_data = project / "vendor" / "LLaMA-Factory" / "data" / "dataset_info.json"
snippet = project / "finetune" / "dataset_info.json"
info = {}
if lf_data.exists():
    info = json.loads(lf_data.read_text(encoding="utf-8"))
info.update(json.loads(snippet.read_text(encoding="utf-8")))
lf_data.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"已更新 {lf_data}")
PY

cat > "$PROJECT_ROOT/finetune/activate_env.sh" <<EOF
#!/usr/bin/env bash
source "$VENV_DIR/bin/activate"
export PYTORCH_ENABLE_MPS_FALLBACK=1
export HF_HOME="$PROJECT_ROOT/finetune/hf_cache"
export MODELSCOPE_CACHE="$PROJECT_ROOT/finetune/ms_cache"
export DISABLE_VERSION_CHECK=1
cd "$LF_DIR"
echo "已激活微调环境，当前目录: \$(pwd)"
echo "训练命令: llamafactory-cli train $PROJECT_ROOT/finetune/qwen1.5b_mps.yaml"
EOF
chmod +x "$PROJECT_ROOT/finetune/activate_env.sh"

echo ""
echo "✅ 安装完成"
echo "下一步:"
echo "  1. bash scripts/preflight_finetune.sh   # 训练前检查"
echo "  2. source finetune/activate_env.sh"
echo "  3. llamafactory-cli train $PROJECT_ROOT/finetune/qwen1.5b_mps.yaml"
