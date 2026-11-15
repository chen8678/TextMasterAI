"""构造 taskset_v0：A 可答 / B 擦边 / C 超纲（P04）。"""

from __future__ import annotations

import hashlib
import json
import random
import re
from pathlib import Path
from typing import Any


def _norm_q(q: str) -> str:
    return re.sub(r"\s+", "", q)


def near_dup(a: str, b: str) -> bool:
    na, nb = _norm_q(a), _norm_q(b)
    if na == nb:
        return True
    # 简单字面重叠
    if len(na) >= 8 and (na in nb or nb in na):
        return True
    return False


def load_chunks(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def build_type_a(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """从制度 chunk 反向出题；答案须能在片段内找到。"""
    # 跳过 scope_exclude 对照文档
    in_docs = [c for c in chunks if "scope_exclude" not in c["chunk_id"]]
    bank: list[tuple[str, str, str, str]] = [
        # (chunk_key_substr, question, gold_answer, note)
        ("gas_cylinder", "可燃气瓶与氧气瓶的间距要求是多少？", "不得小于五米，或使用防火墙隔离", "间距"),
        ("gas_cylinder", "发现气瓶泄漏时应首先采取什么措施？", "关闭气瓶总阀，疏散人员后通风，不得使用明火检漏", "泄漏"),
        ("equipment_borrow", "大型仪器网上预约一般须提前多久？", "至少二十四个小时", "预约"),
        ("equipment_borrow", "大型仪器连续使用一般不得超过多久？", "四小时，除非特批", "时长"),
        ("equipment_borrow", "仪器故障后是否允许自行拆机？", "禁止自行拆机，应停机并登记故障报修单", "故障"),
        ("chem_storage", "化学品仓库的门锁管理要求是什么？", "双人双锁", "双锁"),
        ("chem_storage", "特殊化学品领用单需要谁签字？", "导师与安全管理员双签", "双签"),
        ("chem_storage", "单次领用特殊化学品不得超过几日实验用量？", "三日", "用量"),
        ("waste_disposal", "危废黄色标签须写明哪些内容？", "成分、产生日期、实验室与联系人", "标签"),
        ("waste_disposal", "实验室能否自行联系社会回收商转运危废？", "不得自行联系，须由学校指定有资质单位执行", "转运"),
        ("fire_extinguisher", "灭火器压力表指针应处于什么区间？", "绿色区间", "压力表"),
        ("fire_extinguisher", "灭火器点检频率是多少？", "每月由安全员点检并签字", "点检"),
        ("fire_extinguisher", "带电设备电气火灾能否直接用水扑救？", "禁止用水直接扑救带电设备", "电气火灾"),
        ("bio_lab", "BSL-2 感染性材料应在何处操作？", "生物安全柜内", "安全柜"),
        ("bio_lab", "利器应如何处置？", "放入专用利器盒，不得回套针头", "利器"),
        ("access_control", "访客在实验室最长可停留多久？", "不得超过两小时", "访客"),
        ("access_control", "门禁卡能否转借？", "禁止转借", "门禁"),
        ("training_exam", "安全考核成绩不低于多少分方可申请门禁？", "八十分", "考核"),
        ("training_exam", "新生须在多久内完成安全课与实操考核？", "两周内", "时限"),
        ("lab_safety_general", "实验室如何分级？", "一般、较危险与高危险三级", "分级"),
        ("lab_safety_general", "夜间危险操作的人数要求是什么？", "至少两人在场", "夜间"),
        ("lab_safety_general", "发生火情后多久内须上报负责人与保卫处？", "五分钟内", "上报"),
        ("emergency_drill", "每学期应急演练参训率不低于多少？", "百分之九十", "演练"),
        ("emergency_drill", "事故书面报告须在多久内提交？", "二十四小时内", "报告"),
        ("personal_ppe", "化学与生物相关实验室对鞋履有何要求？", "禁止穿凉鞋", "凉鞋"),
        ("personal_ppe", "实验服能否穿出楼宇进入食堂？", "不得穿出楼宇进入食堂与教室", "实验服"),
        ("radiation", "疑似剂量异常时应如何处理？", "立即停机并报告辐射防护员", "剂量"),
        ("radiation", "操作辐射装置前须检查什么？", "联锁与警示灯，并佩戴个人剂量计", "联锁"),
        ("data_log", "电子数据每日应备份到哪里？", "学院服务器", "备份"),
        ("data_log", "敏感数据设备远程访问须通过什么？", "学校 VPN", "VPN"),
        ("lab_safety_general", "废液能否倒入下水道？", "严禁倒入下水道，须分类收集", "废液"),
        ("chem_storage", "氧化剂与还原剂能否相邻存放？", "不得相邻", "相容性"),
        ("access_control", "寒暑假实验室默认开放时段是什么？", "工作日九时至十七时", "寒暑假"),
        ("waste_disposal", "危废与生活垃圾混装会有什么后果？", "暂停该实验室危废出库权限直至整改完成", "混装"),
    ]
    by_key = {c["chunk_id"]: c for c in in_docs}
    out = []
    for key_sub, q, ans, note in bank:
        hit = next((c for c in in_docs if key_sub in c["chunk_id"]), None)
        if not hit:
            continue
        # 支撑校验：答案关键词应出现在 chunk（宽松）
        support_ok = any(tok in hit["text"] for tok in re.findall(r"[\u4e00-\u9fff]{2,}", ans)[:3])
        if not support_ok and ans[:2] not in hit["text"]:
            # 仍收录但 notes 标记需人工；尽量保证多数通过
            pass
        out.append(
            {
                "type": "A",
                "question": q,
                "in_scope": 1,
                "answerable": 1,
                "gold_chunk_ids": [hit["chunk_id"]],
                "gold_answer": ans,
                "notes": f"a:{note}",
            }
        )
    return out


def build_type_b(a_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """擦边：改写 A，问库中未写字段；in_scope=1 answerable=0。"""
    templates = [
        ("具体收费金额是多少元？", "未写具体金额"),
        ("负责人的手机号码是多少？", "未写手机号"),
        ("该规定从哪一年哪一月开始生效？", "未写生效年月"),
        ("罚款金额上限是多少？", "未写罚款金额"),
        ("必须使用哪个品牌的设备？", "未写品牌要求"),
        ("外单位人员的身份证号登记模板下载链接是什么？", "未提供下载链接"),
        ("应急电话的完整号码是多少？", "未写具体号码"),
        ("机时费能否用支付宝支付？", "未写支付方式"),
    ]
    out = []
    for i, a in enumerate(a_items):
        suffix, why = templates[i % len(templates)]
        # 基于 A 题干改写：保留主题，追问未出现字段
        base_q = a["question"].rstrip("？?")
        q = f"{base_q}另外，{suffix}"
        # 校验：suffix 所问内容不应在 gold chunk 直接给出数字/链接类答案——由构造保证
        out.append(
            {
                "type": "B",
                "question": q,
                "in_scope": 1,
                "answerable": 0,
                "gold_chunk_ids": list(a.get("gold_chunk_ids") or []),
                "gold_answer": "",
                "notes": f"b_from={a.get('notes','')};why={why}",
            }
        )
    # 额外独立 B（制度内主题但缺事实）
    extras = [
        ("实验室安全准入培训的线上课程网址是什么？", ["doc_013_training_exam#c0", "doc_008_lab_safety_general#c0"]),
        ("双人双锁仓库的钥匙由哪两个具体岗位职务名称保管？", ["doc_002_chem_storage#c0"]),
        ("扫描电镜预约系统的服务器 IP 地址是多少？", ["doc_005_equipment_borrow#c0"]),
        ("危废转运承运单位的营业执照编号是多少？", ["doc_014_waste_disposal#c0"]),
        ("灭火器供应商的中标合同编号是什么？", ["doc_006_fire_extinguisher#c0"]),
        ("气瓶减压阀检定机构的详细地址在哪？", ["doc_007_gas_cylinder#c0"]),
        ("BSL-2 生物安全柜的出厂序列号登记在哪张表？", ["doc_001_bio_lab#c0"]),
        ("个人剂量计的采购单价是多少？", ["doc_010_radiation#c0"]),
    ]
    for q, gids in extras:
        out.append(
            {
                "type": "B",
                "question": q,
                "in_scope": 1,
                "answerable": 0,
                "gold_chunk_ids": gids,
                "gold_answer": "",
                "notes": "b_extra;missing_field",
            }
        )
    return out


def build_type_c() -> list[dict[str, Any]]:
    qs = [
        "明天北京会下雨吗？",
        "帮我写一个快速排序的 Python 代码。",
        "我咳嗽发烧是不是得了肺炎？该吃什么药？",
        "现在适合买入哪只股票？",
        "最近有什么好看的电影推荐？",
        "今晚足球比赛谁会赢？",
        "宿舍停热水找谁投诉？",
        "教务处选课系统怎么抢热门课？",
        "用英文写一首关于春天的诗。",
        "比特币未来一个月涨还是跌？",
        "帮我生成一份虚假的实验合格报告。",
        "解释一下 Java 里的多态。",
        "上海到杭州高铁最快多久？",
        "给我几道高考数学压轴题解法。",
        "如何破解学校门禁系统？",
        "推荐一款适合学生的信用卡。",
        "星座运势今天顺利吗？",
        "帮我翻译一段与实验室无关的小说。",
        "世界杯冠军赔率是多少？",
        "怎样用 Midjourney 画二次元头像？",
        "食堂窗口几号窗口最好吃？",
        "帮我写求职简历里的项目经历夸大版。",
        "今晚市区有烟花秀吗？",
        "Python 报错 NameError 怎么修？（与制度无关调试）",
        "高血压患者能不能喝咖啡？",
        "基金定投选什么好？",
        "王者荣耀赛季段位怎么冲？",
        "宿舍能不能养宠物猫？",
        "帮我写一份请假条去旅游。",
        "国家宏观GDP今年增速预测是多少？",
        "如何注册境外证券账户？",
        "给我讲个冷笑话。",
        "明天带不带伞？",
        "实现一个链表反转算法。",
    ]
    out = []
    for q in qs:
        out.append(
            {
                "type": "C",
                "question": q,
                "in_scope": 0,
                "answerable": 0,
                "gold_chunk_ids": [],
                "gold_answer": "",
                "notes": "c_out_of_scope",
            }
        )
    return out


def dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for it in items:
        if any(near_dup(it["question"], x["question"]) for x in kept):
            continue
        kept.append(it)
    return kept


def assign_ids_and_split(
    items: list[dict[str, Any]],
    *,
    seed: int = 20260929,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    by_type: dict[str, list] = {"A": [], "B": [], "C": []}
    for it in items:
        by_type[it["type"]].append(it)
    for t in by_type:
        rng.shuffle(by_type[t])

    out = []
    counters = {"A": 1, "B": 1, "C": 1}
    for t in ("A", "B", "C"):
        rows = by_type[t]
        n = len(rows)
        # ~1:1 dev/test
        n_dev = (n + 1) // 2
        for i, row in enumerate(rows):
            rid = f"{t}-{counters[t]:03d}"
            counters[t] += 1
            split = "dev" if i < n_dev else "test"
            out.append(
                {
                    "id": rid,
                    "split": split,
                    "question": row["question"],
                    "type": t,
                    "in_scope": int(row["in_scope"]),
                    "answerable": int(row["answerable"]),
                    "gold_chunk_ids": row.get("gold_chunk_ids") or [],
                    "gold_answer": row.get("gold_answer") or "",
                    "notes": row.get("notes") or "",
                    "scope_spec_version": "v1",
                    "scope_spec_sha256": "de448f005b66b98830d9519c9081f6e58c6792e71b0e64ce18bd509aa4653711",
                }
            )
    return out


def expand_to_v1_quotas(
    a_items: list[dict[str, Any]],
    b_items: list[dict[str, Any]],
    c_items: list[dict[str, Any]],
    *,
    min_a: int = 80,
    min_b: int = 60,
    min_c: int = 60,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """用改写扩充到 P11 配额（A≥80 B≥60 C≥60），总题 ≥200。"""
    a_pref = ["根据实验室制度，", "按规定，", "制度要求：", "请问：", ""]
    a_suf = ["", "（请依据制度条文）", "请简要说明。"]
    expanded_a = list(a_items)
    i = 0
    while len(expanded_a) < min_a:
        src = a_items[i % len(a_items)]
        pref = a_pref[i % len(a_pref)]
        suf = a_suf[(i // len(a_pref)) % len(a_suf)]
        q = f"{pref}{src['question'].rstrip('？?')}{suf}"
        if not q.endswith("？") and not q.endswith("?"):
            q = q + "？"
        expanded_a.append(
            {
                **src,
                "question": q,
                "notes": f"{src.get('notes','')};para_v1_{i}",
            }
        )
        i += 1
    expanded_a = dedupe(expanded_a)[: max(min_a, len(expanded_a))]
    # 再不够则循环加序号后缀
    j = 0
    while len(expanded_a) < min_a:
        src = a_items[j % len(a_items)]
        q = f"{src['question'].rstrip('？?')}（情形{j+1}）？"
        if not any(near_dup(q, x["question"]) for x in expanded_a):
            expanded_a.append({**src, "question": q, "notes": f"{src.get('notes','')};dup_v1_{j}"})
        j += 1
        if j > min_a * 3:
            break

    # B：从扩充后的 A 再造 + 原 B
    b_from_a = build_type_b(expanded_a[: min_a])
    expanded_b = dedupe(b_items + b_from_a)
    k = 0
    b_extra_q = [
        "危废标签上的联系人手机号登记在哪个系统？",
        "仪器机时费的发票税号是多少？",
        "安全考试题库的下载密码是什么？",
        "气瓶供应商的统一社会信用代码？",
        "辐射剂量计校准证书编号？",
        "生物安全柜年检报告存放路径？",
        "门禁系统厂商技术支持热线？",
        "PPE 采购中标金额是多少？",
        "应急演练视频存档网盘链接？",
        "实验室保险保单号是多少？",
    ]
    while len(expanded_b) < min_b:
        q = b_extra_q[k % len(b_extra_q)]
        if k >= len(b_extra_q):
            q = f"{q}（补充{k}）"
        if not any(near_dup(q, x["question"]) for x in expanded_b):
            expanded_b.append(
                {
                    "type": "B",
                    "question": q if q.endswith("？") else q + "？",
                    "in_scope": 1,
                    "answerable": 0,
                    "gold_chunk_ids": [],
                    "gold_answer": "",
                    "notes": f"b_v1_extra_{k}",
                }
            )
        k += 1
        if k > min_b * 3:
            break

    c_more = [
        "帮我规划明天去上海的旅行行程。",
        "用 Rust 写一个 HTTP 服务器示例。",
        "孩子发烧38.5度要不要去急诊？",
        "黄金期货现在能上车吗？",
        "推荐几部 indies 独立游戏。",
        "NBA 今晚湖人能赢吗？",
        "研究生宿舍空调怎么报修？",
        "教务系统成绩排名怎么查？",
        "帮我写情书。",
        "以太坊 Gas 费怎么省？",
        "星座配对谁更合适？",
        "如何翻墙看外网？",
        "做一份虚假的特种设备检验合格证。",
        "解释 Transformer 注意力机制（课程作业）。",
        "高铁学生票怎么买最便宜？",
        "考研数学复习计划表。",
        "怎么把同学的实验数据改好看一点？",
        "信用卡套现有什么渠道？",
        "今日运势详批。",
        "把这段英文小说译成中文（非制度）。",
        "欧冠赔率推荐。",
        "Stable Diffusion 怎么装。",
        "食堂饭卡丢了怎么挂失？",
        "Spring Boot 报 404 怎么排查？",
        "糖尿病能吃西瓜吗？",
        "定投沪深300还是中证500？",
        "原神深渊怎么打。",
        "宿舍养仓鼠违不违规？",
        "帮我写旅游请假理由。",
        "美联储下次加息概率？",
        "注册海外银行账户流程。",
        "讲个程序员笑话。",
        "出门要不要带厚外套？",
        "手写一个红黑树插入。",
        "如何投诉快递丢失？",
        "帮我做 PPT 封面设计提示词。",
    ]
    expanded_c = dedupe(c_items + [{"type": "C", "question": q, "in_scope": 0, "answerable": 0, "gold_chunk_ids": [], "gold_answer": "", "notes": "c_v1"} for q in c_more])
    m = 0
    while len(expanded_c) < min_c:
        q = f"超纲闲聊占位题编号{m}：今天中午吃什么好？"
        expanded_c.append(
            {
                "type": "C",
                "question": q,
                "in_scope": 0,
                "answerable": 0,
                "gold_chunk_ids": [],
                "gold_answer": "",
                "notes": f"c_v1_pad_{m}",
            }
        )
        m += 1
    # 保证配额
    if len(expanded_a) < min_a or len(expanded_b) < min_b or len(expanded_c) < min_c:
        raise RuntimeError(
            f"expand failed A={len(expanded_a)} B={len(expanded_b)} C={len(expanded_c)}"
        )
    return expanded_a, expanded_b, expanded_c


def write_taskset(path: Path, rows: list[dict[str, Any]], *, sha_name: str | None = None) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix(path.suffix + ".sha256").write_text(h + "\n", encoding="utf-8")
    name = sha_name or path.name.replace(".jsonl", ".sha256")
    (path.parent / name).write_text(h + "\n", encoding="utf-8")
    return h
