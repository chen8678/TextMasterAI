#!/usr/bin/env python3
"""
检测本机是否适合本地大模型微调，并给出模型/工具建议。

用法:
  python scripts/check_finetune_env.py
  python scripts/check_finetune_env.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _run(cmd: List[str]) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True).strip()
    except Exception:
        return ""


def _gb(bytes_val: float) -> float:
    return round(bytes_val / 1024**3, 1)


def _pkg_version(name: str) -> Optional[str]:
    try:
        mod = __import__(name)
        return getattr(mod, "__version__", "installed")
    except Exception:
        return None


def detect_system() -> Dict[str, Any]:
    uname = platform.uname()
    cpu_brand = _run(["sysctl", "-n", "machdep.cpu.brand_string"]) if sys.platform == "darwin" else platform.processor()
    physical = _run(["sysctl", "-n", "hw.physicalcpu"]) if sys.platform == "darwin" else ""
    logical = _run(["sysctl", "-n", "hw.logicalcpu"]) if sys.platform == "darwin" else str(os.cpu_count() or "")
    ram_gb = _gb(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")) if hasattr(os, "sysconf") else None

    gpu_info = ""
    metal = ""
    if sys.platform == "darwin":
        disp = _run(["system_profiler", "SPDisplaysDataType"])
        for line in disp.splitlines():
            s = line.strip()
            if "Chipset Model:" in s or "Total Number of Cores:" in s or "Metal Support:" in s:
                gpu_info += s + "\n"
        metal = "Metal 3" if "Metal 3" in disp else ("Metal" if "Metal" in disp else "")

    disks = []
    for path in [Path.home(), Path("/Volumes/Samsung Protable SSD T5 Media")]:
        try:
            du = shutil.disk_usage(path)
            disks.append({
                "path": str(path),
                "total_gb": _gb(du.total),
                "free_gb": _gb(du.free),
                "used_pct": round((du.used / du.total) * 100, 1),
            })
        except Exception:
            pass

    return {
        "platform": uname.system,
        "machine": uname.machine,
        "cpu_brand": cpu_brand,
        "physical_cores": physical,
        "logical_cores": logical,
        "ram_gb": ram_gb,
        "gpu_summary": gpu_info.strip(),
        "metal": metal,
        "python": platform.python_version(),
        "disks": disks,
    }


def detect_ml_stack() -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "torch": None,
        "mps_available": False,
        "cuda_available": False,
        "cuda_device": None,
        "cuda_mem_gb": None,
        "packages": {},
    }
    try:
        import torch

        info["torch"] = torch.__version__
        info["mps_available"] = bool(torch.backends.mps.is_available())
        info["cuda_available"] = bool(torch.cuda.is_available())
        if info["cuda_available"]:
            info["cuda_device"] = torch.cuda.get_device_name(0)
            info["cuda_mem_gb"] = _gb(torch.cuda.get_device_properties(0).total_memory)
    except Exception as exc:
        info["torch_error"] = str(exc)

    for pkg in ["transformers", "datasets", "peft", "accelerate", "bitsandbytes", "llamafactory", "mlx", "mlx_lm"]:
        info["packages"][pkg] = _pkg_version(pkg)

    info["docker"] = bool(shutil.which("docker"))
    if info["docker"]:
        info["docker_version"] = _run(["docker", "version", "--format", "{{.Server.Version}}"])

    return info


def recommend(system: Dict[str, Any], ml: Dict[str, Any]) -> Dict[str, Any]:
    ram = system.get("ram_gb") or 0
    machine = system.get("machine", "")
    has_cuda = ml.get("cuda_available")
    cuda_mem = ml.get("cuda_mem_gb") or 0
    has_mps = ml.get("mps_available")
    is_apple = machine == "arm64" and system.get("platform") == "Darwin"

    rec = {
        "local_feasible": False,
        "recommended_route": "",
        "model_suggestions": [],
        "tool_suggestions": [],
        "warnings": [],
        "missing_packages": [],
    }

    required = ["transformers", "datasets", "peft", "accelerate"]
    for p in required:
        if not ml.get("packages", {}).get(p):
            rec["missing_packages"].append(p)

    if is_apple and has_mps:
        if ram >= 16:
            rec["local_feasible"] = True
            rec["recommended_route"] = "local_mps_small_model"
            rec["model_suggestions"] = [
                {
                    "model": "Qwen/Qwen2.5-1.5B-Instruct",
                    "method": "LoRA (fp16/bf16 on MPS)",
                    "fit": "recommended",
                    "note": "18GB 统一内存下最稳妥的本地首次实验",
                },
                {
                    "model": "Qwen/Qwen2.5-3B-Instruct",
                    "method": "LoRA (MPS)",
                    "fit": "possible",
                    "note": "可试，需减小 batch / cutoff_len，训练较慢",
                },
                {
                    "model": "Qwen/Qwen2.5-7B-Instruct",
                    "method": "QLoRA",
                    "fit": "not_recommended_local",
                    "note": "Mac 上 bitsandbytes/Q CUDA 不可用，7B 本地训练风险高",
                },
            ]
            rec["tool_suggestions"] = [
                "首选: LLaMA-Factory（MPS + 小模型）",
                "备选: mlx-lm（Apple Silicon 原生，适合 3B 推理/轻量微调）",
                "7B 正式实验: AutoDL / ModelScope 租 24GB NVIDIA GPU",
            ]
            rec["warnings"].append("Apple Silicon 无 CUDA；bitsandbytes QLoRA 基本不能指望。")
            if ram < 24:
                rec["warnings"].append(f"统一内存仅 {ram}GB，训练时请关闭浏览器/IDE 等大内存应用。")
        else:
            rec["recommended_route"] = "cloud_gpu"
            rec["warnings"].append(f"内存仅 {ram}GB，不建议本地微调。")

    if has_cuda and cuda_mem >= 20:
        rec["local_feasible"] = True
        rec["recommended_route"] = "local_cuda_qlora"
        rec["model_suggestions"] = [
            {
                "model": "Qwen/Qwen2.5-7B-Instruct",
                "method": "QLoRA 4bit",
                "fit": "recommended",
                "note": f"检测到 CUDA 显存约 {cuda_mem}GB",
            }
        ]
        rec["tool_suggestions"] = ["LLaMA-Factory + QLoRA"]

    if not rec["local_feasible"] and not has_cuda:
        rec["recommended_route"] = "cloud_gpu"
        rec["model_suggestions"] = [
            {
                "model": "Qwen/Qwen2.5-7B-Instruct",
                "method": "QLoRA 4bit",
                "fit": "recommended",
                "note": "云 GPU 24GB 卡，适合当前英语词汇助教场景",
            }
        ]
        rec["tool_suggestions"] = ["AutoDL / ModelScope 租 GPU + LLaMA-Factory"]

    # disk check
    ext = next((d for d in system.get("disks", []) if "Samsung" in d.get("path", "")), None)
    if ext and ext.get("free_gb", 0) < 30:
        rec["warnings"].append(f"外置 SSD 剩余空间仅 {ext['free_gb']}GB，下载 7B 模型可能紧张。")

    return rec


def print_report(payload: Dict[str, Any]) -> None:
    s = payload["system"]
    ml = payload["ml"]
    rec = payload["recommendation"]

    print("=" * 60)
    print("微调环境检测报告")
    print("=" * 60)
    print(f"时间: {payload['generated_at']}")
    print(f"CPU: {s.get('cpu_brand')} ({s.get('machine')})")
    print(f"核心: physical={s.get('physical_cores')} logical={s.get('logical_cores')}")
    print(f"内存: {s.get('ram_gb')} GB 统一内存")
    if s.get("gpu_summary"):
        print("GPU:")
        for line in s["gpu_summary"].splitlines():
            print(f"  {line}")
    print(f"Python: {s.get('python')}")
    print(f"PyTorch: {ml.get('torch') or '未安装'}")
    print(f"MPS: {ml.get('mps_available')} | CUDA: {ml.get('cuda_available')}")
    if ml.get("cuda_device"):
        print(f"CUDA 设备: {ml['cuda_device']} ({ml.get('cuda_mem_gb')} GB)")
    print("\n磁盘:")
    for d in s.get("disks", []):
        print(f"  {d['path']}: free {d['free_gb']}GB / {d['total_gb']}GB ({d['used_pct']}% used)")
    print("\n相关包:")
    for k, v in ml.get("packages", {}).items():
        print(f"  {k}: {v or '未安装'}")
    if rec.get("missing_packages"):
        print("\n建议安装:")
        print("  pip install datasets peft accelerate")
        print("  # 本地 Mac 实验后再装 LLaMA-Factory")
    print("\n推荐路线:", rec.get("recommended_route"))
    print("本地可微调:", "是" if rec.get("local_feasible") else "否（建议云 GPU）")
    print("\n模型建议:")
    for m in rec.get("model_suggestions", []):
        print(f"  - [{m['fit']}] {m['model']} | {m['method']}")
        print(f"    {m['note']}")
    if rec.get("tool_suggestions"):
        print("\n工具建议:")
        for t in rec["tool_suggestions"]:
            print(f"  - {t}")
    if rec.get("warnings"):
        print("\n注意:")
        for w in rec["warnings"]:
            print(f"  ! {w}")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(description="检测微调环境并给出模型建议")
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告")
    parser.add_argument(
        "--out",
        default="backend/data/training_datasets/env_report.json",
        help="JSON 报告保存路径（相对项目根目录）",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    system = detect_system()
    ml = detect_ml_stack()
    recommendation = recommend(system, ml)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "system": system,
        "ml": ml,
        "recommendation": recommendation,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_report(payload)

    out_path = root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.json:
        print(f"\n报告已保存: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
