#!/usr/bin/env python3
"""M06：构造 taskset_hard_v0（10–20 脏题），不改 taskset_v1。"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from apps.dsrag.config import resolve_path  # noqa: E402

# 绕表述 / 多条件 / 易偏检索；标注 gold 供评分
HARD_CASES = [
    # A 难：同义绕写 + 多条件
    {
        "id": "H-A-01",
        "type": "A",
        "split": "test",
        "question": "要是发现钢瓶漏气，第一步该干嘛？能不能用打火机去找漏点？",
        "in_scope": 1,
        "answerable": 1,
        "gold_chunk_ids": ["doc_007_gas_cylinder#c0"],
        "gold_answer": "关闭气瓶总阀，疏散人员后通风，不得使用明火检漏",
        "notes": "hard_a;paraphrase+neg",
    },
    {
        "id": "H-A-02",
        "type": "A",
        "split": "test",
        "question": "大型设备预约一般要提前多久？连续开着能不能超过四个钟头？",
        "in_scope": 1,
        "answerable": 1,
        "gold_chunk_ids": ["doc_005_equipment_borrow#c0"],
        "gold_answer": "至少二十四个小时；连续使用不得超过四小时，除非特批",
        "notes": "hard_a;multi_clause",
    },
    {
        "id": "H-A-03",
        "type": "A",
        "split": "test",
        "question": "氧化剂旁边能不能放还原剂？仓库门锁是不是双人双锁？",
        "in_scope": 1,
        "answerable": 1,
        "gold_chunk_ids": ["doc_002_chem_storage#c0"],
        "gold_answer": "不得相邻；双人双锁",
        "notes": "hard_a;two_facts",
    },
    {
        "id": "H-A-04",
        "type": "A",
        "split": "test",
        "question": "废液直接冲进下水道行不行？应该怎么收集？",
        "in_scope": 1,
        "answerable": 1,
        "gold_chunk_ids": ["doc_008_lab_safety_general#c0", "doc_014_waste_disposal#c0"],
        "gold_answer": "严禁倒入下水道，须分类收集",
        "notes": "hard_a;neg+how",
    },
    {
        "id": "H-A-05",
        "type": "A",
        "split": "test",
        "question": "半夜还在做危险实验，一个人留下继续操作可以吗？",
        "in_scope": 1,
        "answerable": 1,
        "gold_chunk_ids": ["doc_008_lab_safety_general#c0"],
        "gold_answer": "至少两人在场，一人离开时另一人不得继续危险操作",
        "notes": "hard_a;night",
    },
    {
        "id": "H-A-06",
        "type": "A",
        "split": "test",
        "question": "仪器坏了自己拆开修一修行吗？正确流程？",
        "in_scope": 1,
        "answerable": 1,
        "gold_chunk_ids": ["doc_005_equipment_borrow#c0"],
        "gold_answer": "禁止自行拆机，应停机并登记故障报修单",
        "notes": "hard_a;fault",
    },
    # B 难：制度内主题但追问库外细节 / 绕弯
    {
        "id": "H-B-01",
        "type": "B",
        "split": "test",
        "question": "气瓶泄漏处置流程里，保卫处值班电话的完整号码是多少？",
        "in_scope": 1,
        "answerable": 0,
        "gold_chunk_ids": ["doc_007_gas_cylinder#c0"],
        "gold_answer": "",
        "notes": "hard_b;phone",
    },
    {
        "id": "H-B-02",
        "type": "B",
        "split": "test",
        "question": "双人双锁的两把钥匙分别由哪两个具体职务职称保管？请给出岗位全称。",
        "in_scope": 1,
        "answerable": 0,
        "gold_chunk_ids": ["doc_002_chem_storage#c0"],
        "gold_answer": "",
        "notes": "hard_b;role_title",
    },
    {
        "id": "H-B-03",
        "type": "B",
        "split": "test",
        "question": "大型仪器预约系统的后台服务器公网 IP 与端口是多少？",
        "in_scope": 1,
        "answerable": 0,
        "gold_chunk_ids": ["doc_005_equipment_borrow#c0"],
        "gold_answer": "",
        "notes": "hard_b;ip",
    },
    {
        "id": "H-B-04",
        "type": "B",
        "split": "test",
        "question": "危废转运指定资质单位去年的中标合同编号与承运车牌号？",
        "in_scope": 1,
        "answerable": 0,
        "gold_chunk_ids": ["doc_014_waste_disposal#c0"],
        "gold_answer": "",
        "notes": "hard_b;contract",
    },
    {
        "id": "H-B-05",
        "type": "B",
        "split": "test",
        "question": "灭火器点检表是否可以用钉钉在线填写？模板下载链接是什么？",
        "in_scope": 1,
        "answerable": 0,
        "gold_chunk_ids": ["doc_006_fire_extinguisher#c0"],
        "gold_answer": "",
        "notes": "hard_b;dingtalk",
    },
    {
        "id": "H-B-06",
        "type": "B",
        "split": "test",
        "question": "个人剂量计如果超标，学院规定的经济处罚金额上限是多少元？",
        "in_scope": 1,
        "answerable": 0,
        "gold_chunk_ids": ["doc_010_radiation#c0"],
        "gold_answer": "",
        "notes": "hard_b;fine",
    },
    {
        "id": "H-B-07",
        "type": "B",
        "split": "test",
        "question": "夜间实验「至少两人」是否包含远程视频连线的导师算一人？制度原文依据条款号？",
        "in_scope": 1,
        "answerable": 0,
        "gold_chunk_ids": ["doc_008_lab_safety_general#c0"],
        "gold_answer": "",
        "notes": "hard_b;edge_interpret",
    },
    {
        "id": "H-B-08",
        "type": "B",
        "split": "test",
        "question": "寒暑假开放时段「九时至十七时」是北京时间还是实验室所在时区？有无夏令时例外？",
        "in_scope": 1,
        "answerable": 0,
        "gold_chunk_ids": ["doc_003_access_control#c0"],
        "gold_answer": "",
        "notes": "hard_b;timezone",
    },
    # 易偏检索：表面像 A 实为 B
    {
        "id": "H-B-09",
        "type": "B",
        "split": "test",
        "question": "可燃气瓶与氧气瓶间距五米的规定适用于校外实习基地租用仓库吗？校外是否另有地方标准编号？",
        "in_scope": 1,
        "answerable": 0,
        "gold_chunk_ids": ["doc_007_gas_cylinder#c0"],
        "gold_answer": "",
        "notes": "hard_b;offsite_scope_edge",
    },
    {
        "id": "H-A-07",
        "type": "A",
        "split": "test",
        "question": "门禁卡能不能借给同学刷一下？",
        "in_scope": 1,
        "answerable": 1,
        "gold_chunk_ids": ["doc_003_access_control#c0"],
        "gold_answer": "禁止转借",
        "notes": "hard_a;colloquial",
    },
]


def main() -> None:
    out = resolve_path("SCAR/data/dsrag/taskset/taskset_hard_v0.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    blob = "\n".join(json.dumps(r, ensure_ascii=False) for r in HARD_CASES) + "\n"
    out.write_text(blob, encoding="utf-8")
    h = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    (out.parent / "taskset_hard_v0.sha256").write_text(h + "\n", encoding="utf-8")
    nA = sum(1 for r in HARD_CASES if r["type"] == "A")
    nB = sum(1 for r in HARD_CASES if r["type"] == "B")
    print(json.dumps({"path": str(out), "n": len(HARD_CASES), "n_A": nA, "n_B": nB, "sha256": h}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
