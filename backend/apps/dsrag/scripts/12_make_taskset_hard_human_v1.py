#!/usr/bin/env python3
"""M13：人工难例 taskset_hard_human_v1（20–30 题），非 chunk 直改写。"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from apps.dsrag.config import resolve_path  # noqa: E402

# 人工撰写：口语绕弯、多条件、易偏检索、制度边缘；不从 chunk 机械改写
CASES = [
    # —— A：应可答但表述脏 ——
    {"id": "HH-A-01", "type": "A", "split": "test", "in_scope": 1, "answerable": 1,
     "question": "钢瓶要是呲气了，先关哪儿？能不能拿打火机凑近了瞅瞅漏点？",
     "gold_chunk_ids": ["doc_007_gas_cylinder#c0"],
     "gold_answer": "关闭气瓶总阀，疏散人员后通风，不得使用明火检漏", "notes": "human;colloquial+neg"},
    {"id": "HH-A-02", "type": "A", "split": "test", "in_scope": 1, "answerable": 1,
     "question": "我想约扫描电镜，最早得提前多久约？中间能不能连续用五六个小时不换人？",
     "gold_chunk_ids": ["doc_005_equipment_borrow#c0"],
     "gold_answer": "至少二十四个小时；连续使用不得超过四小时，除非特批", "notes": "human;multi"},
    {"id": "HH-A-03", "type": "A", "split": "test", "in_scope": 1, "answerable": 1,
     "question": "仓库里氧化剂跟还原剂挨着摆行不行？门锁是不是得两个人两把钥匙？",
     "gold_chunk_ids": ["doc_002_chem_storage#c0"],
     "gold_answer": "不得相邻；双人双锁", "notes": "human;two_facts"},
    {"id": "HH-A-04", "type": "A", "split": "test", "in_scope": 1, "answerable": 1,
     "question": "废液顺手倒下水道冲掉可以吗？不然该怎么弄？",
     "gold_chunk_ids": ["doc_008_lab_safety_general#c0", "doc_014_waste_disposal#c0"],
     "gold_answer": "严禁倒入下水道，须分类收集", "notes": "human;neg+how"},
    {"id": "HH-A-05", "type": "A", "split": "test", "in_scope": 1, "answerable": 1,
     "question": "夜里就剩我一个还在做危险实验，同事出去买宵夜了，我能不能继续搞？",
     "gold_chunk_ids": ["doc_008_lab_safety_general#c0"],
     "gold_answer": "至少两人在场，一人离开时另一人不得继续危险操作", "notes": "human;night_scenario"},
    {"id": "HH-A-06", "type": "A", "split": "test", "in_scope": 1, "answerable": 1,
     "question": "仪器死机了我想自己拧开盖子看看风扇，制度允许吗？正确该怎么报？",
     "gold_chunk_ids": ["doc_005_equipment_borrow#c0"],
     "gold_answer": "禁止自行拆机，应停机并登记故障报修单", "notes": "human;fault"},
    {"id": "HH-A-07", "type": "A", "split": "test", "in_scope": 1, "answerable": 1,
     "question": "门禁卡借给室友刷一下带他进实验室，算不算违规？",
     "gold_chunk_ids": ["doc_003_access_control#c0"],
     "gold_answer": "禁止转借", "notes": "human;access"},
    {"id": "HH-A-08", "type": "A", "split": "test", "in_scope": 1, "answerable": 1,
     "question": "灭火器压力表指针要停在什么颜色区间才算正常？",
     "gold_chunk_ids": ["doc_006_fire_extinguisher#c0"],
     "gold_answer": "绿色区间", "notes": "human;color"},
    {"id": "HH-A-09", "type": "A", "split": "test", "in_scope": 1, "answerable": 1,
     "question": "开辐射装置前除了看联锁和警示灯，身上还得戴什么？",
     "gold_chunk_ids": ["doc_010_radiation#c0"],
     "gold_answer": "联锁与警示灯，并佩戴个人剂量计", "notes": "human;radiation_full"},
    {"id": "HH-A-10", "type": "A", "split": "test", "in_scope": 1, "answerable": 1,
     "question": "危废桶上的黄标签至少得写哪些信息？能不能自己联系外面回收车拉走？",
     "gold_chunk_ids": ["doc_014_waste_disposal#c0"],
     "gold_answer": "成分、产生日期、实验室与联系人；不得自行联系，须由学校指定有资质单位执行", "notes": "human;waste_multi"},
    {"id": "HH-A-11", "type": "A", "split": "test", "in_scope": 1, "answerable": 1,
     "question": "特殊化学品一次能领几天用量？单子要谁签字？",
     "gold_chunk_ids": ["doc_002_chem_storage#c0"],
     "gold_answer": "三日；导师与安全管理员双签", "notes": "human;chem_multi"},
    {"id": "HH-A-12", "type": "A", "split": "test", "in_scope": 1, "answerable": 1,
     "question": "寒暑假实验室默认几点到几点开门？",
     "gold_chunk_ids": ["doc_003_access_control#c0"],
     "gold_answer": "工作日九时至十七时", "notes": "human;hours"},
    # —— B：制度内主题但缺事实 / 易骗过检索 ——
    {"id": "HH-B-01", "type": "B", "split": "test", "in_scope": 1, "answerable": 0,
     "question": "气瓶泄漏后打给保卫处，值班座机完整号码是多少？",
     "gold_chunk_ids": ["doc_007_gas_cylinder#c0"], "gold_answer": "", "notes": "human;phone"},
    {"id": "HH-B-02", "type": "B", "split": "test", "in_scope": 1, "answerable": 0,
     "question": "双人双锁两把钥匙分别对应哪两个职务的正式岗位名称（写全称）？",
     "gold_chunk_ids": ["doc_002_chem_storage#c0"], "gold_answer": "", "notes": "human;titles"},
    {"id": "HH-B-03", "type": "B", "split": "test", "in_scope": 1, "answerable": 0,
     "question": "大型仪器预约后台服务器的公网 IP 和端口是多少？",
     "gold_chunk_ids": ["doc_005_equipment_borrow#c0"], "gold_answer": "", "notes": "human;ip"},
    {"id": "HH-B-04", "type": "B", "split": "test", "in_scope": 1, "answerable": 0,
     "question": "指定危废承运单位去年中标合同编号以及车牌号？",
     "gold_chunk_ids": ["doc_014_waste_disposal#c0"], "gold_answer": "", "notes": "human;contract"},
    {"id": "HH-B-05", "type": "B", "split": "test", "in_scope": 1, "answerable": 0,
     "question": "灭火器月度点检能不能在企业微信里填？模板下载链接发我？",
     "gold_chunk_ids": ["doc_006_fire_extinguisher#c0"], "gold_answer": "", "notes": "human;wecom"},
    {"id": "HH-B-06", "type": "B", "split": "test", "in_scope": 1, "answerable": 0,
     "question": "个人剂量计超标一次，学院规定的罚款上限是多少元？",
     "gold_chunk_ids": ["doc_010_radiation#c0"], "gold_answer": "", "notes": "human;fine"},
    {"id": "HH-B-07", "type": "B", "split": "test", "in_scope": 1, "answerable": 0,
     "question": "夜间「至少两人」算不算腾讯会议里挂着的导师？请给出制度条款号。",
     "gold_chunk_ids": ["doc_008_lab_safety_general#c0"], "gold_answer": "", "notes": "human;edge_video"},
    {"id": "HH-B-08", "type": "B", "split": "test", "in_scope": 1, "answerable": 0,
     "question": "寒暑假九时至十七时是北京时间还是实验室当地时区？有没有夏令时例外文件？",
     "gold_chunk_ids": ["doc_003_access_control#c0"], "gold_answer": "", "notes": "human;tz"},
    {"id": "HH-B-09", "type": "B", "split": "test", "in_scope": 1, "answerable": 0,
     "question": "气瓶间距五米的规定，校外实习基地租来的仓库要不要一并遵守？地方标准文号是多少？",
     "gold_chunk_ids": ["doc_007_gas_cylinder#c0"], "gold_answer": "", "notes": "human;offsite"},
    {"id": "HH-B-10", "type": "B", "split": "test", "in_scope": 1, "answerable": 0,
     "question": "生物安全柜出厂序列号登记在哪一张固定表格的哪一栏？",
     "gold_chunk_ids": ["doc_001_bio_lab#c0"], "gold_answer": "", "notes": "human;serial"},
    {"id": "HH-B-11", "type": "B", "split": "test", "in_scope": 1, "answerable": 0,
     "question": "安全准入线上课的完整 URL 以及考试系统管理员账号是什么？",
     "gold_chunk_ids": ["doc_013_training_exam#c0"], "gold_answer": "", "notes": "human;url"},
    {"id": "HH-B-12", "type": "B", "split": "test", "in_scope": 1, "answerable": 0,
     "question": "剧毒试剂柜的电子锁厂商型号与默认初始密码是多少？",
     "gold_chunk_ids": ["doc_002_chem_storage#c0"], "gold_answer": "", "notes": "human;pwd"},
    {"id": "HH-B-13", "type": "B", "split": "test", "in_scope": 1, "answerable": 0,
     "question": "应急演练参训率百分之九十是按人头还是按人次统计？缺席三次怎么折算？",
     "gold_chunk_ids": ["doc_004_emergency_drill#c0"], "gold_answer": "", "notes": "human;stat_edge"},
    {"id": "HH-A-13", "type": "A", "split": "test", "in_scope": 1, "answerable": 1,
     "question": "实验室分级一共几档，分别叫什么？",
     "gold_chunk_ids": ["doc_008_lab_safety_general#c0"],
     "gold_answer": "一般、较危险与高危险三级", "notes": "human;grade"},
    {"id": "HH-A-14", "type": "A", "split": "test", "in_scope": 1, "answerable": 1,
     "question": "着火了要在多长时间内上报负责人和保卫处？",
     "gold_chunk_ids": ["doc_008_lab_safety_general#c0"],
     "gold_answer": "五分钟内", "notes": "human;fire_report"},
]


def main() -> None:
    out = resolve_path("SCAR/data/dsrag/taskset/taskset_hard_human_v1.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    blob = "\n".join(json.dumps(r, ensure_ascii=False) for r in CASES) + "\n"
    out.write_text(blob, encoding="utf-8")
    h = hashlib.sha256(blob.encode()).hexdigest()
    (out.parent / "taskset_hard_human_v1.sha256").write_text(h + "\n", encoding="utf-8")
    nA = sum(1 for r in CASES if r["type"] == "A")
    nB = sum(1 for r in CASES if r["type"] == "B")
    print(json.dumps({"path": str(out), "n": len(CASES), "n_A": nA, "n_B": nB, "sha256": h}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
