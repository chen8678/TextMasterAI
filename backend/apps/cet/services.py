from datetime import datetime, timedelta
import json
from typing import Any, Dict, List, Optional, Tuple

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone

from apps.chat.ai_services import AIServiceFactory
from .models import (
    CETExam,
    CETQuestion,
    KnowledgePoint,
    MockExam,
    UserAnswer,
    Vocabulary,
    VocabularyLearningRecord,
    VocabularyNotebook,
)

User = get_user_model()

CET4 = "cet4"
OBJECTIVE_TYPES = {"listening", "reading", "translation", "vocabulary", "grammar"}


def _cet4_questions():
    return CETQuestion.objects.filter(
        Q(exam__exam_type=CET4) | Q(exam__isnull=True)
    )


class CETPracticeService:
    """练习与错题本相关服务"""

    def generate_practice(
        self,
        user: User,
        question_type: str,
        difficulty: Optional[int] = None,
        count: int = 10,
        exam_type: str = CET4,
    ) -> List[CETQuestion]:
        """按四级题库抽题；优先覆盖用户错得多的知识点。"""
        qs = _cet4_questions().filter(question_type=question_type)
        if exam_type and exam_type != CET4:
            # 首发仅四级；其他类型暂回落到四级池，避免空卷
            qs = _cet4_questions().filter(question_type=question_type)
        if difficulty is not None:
            qs = qs.filter(difficulty=difficulty)

        weak = self.analyze_weak_points(user)
        weak_names = set(weak.get("weak_knowledge_points") or [])
        preferred = list(
            qs.filter(knowledge_points__name__in=weak_names).distinct().order_by("?")[:count]
        )
        if len(preferred) >= count:
            return preferred[:count]
        remain = count - len(preferred)
        preferred_ids = {q.id for q in preferred}
        filler = list(qs.exclude(id__in=preferred_ids).order_by("?")[:remain])
        return preferred + filler

    def submit_practice(
        self,
        user: User,
        answers: Dict[str, Any],
    ) -> Dict[str, Any]:
        """提交专项练习答案并写入 UserAnswer；附带雷达前后对比。"""
        analysis = CETAnalysisService()
        radar_before = analysis.generate_ability_radar(user)

        total = 0
        correct = 0
        details: List[Dict[str, Any]] = []
        for qid, raw in (answers or {}).items():
            try:
                question = CETQuestion.objects.get(id=int(qid))
            except (TypeError, ValueError, CETQuestion.DoesNotExist):
                continue
            user_answer = str(raw or "").strip()
            total += 1
            is_correct = False
            score = None
            if question.question_type in OBJECTIVE_TYPES and question.correct_answer:
                is_correct = user_answer.lower() == question.correct_answer.strip().lower()
                score = 1.0 if is_correct else 0.0
            if is_correct:
                correct += 1
            UserAnswer.objects.create(
                user=user,
                question=question,
                user_answer=user_answer,
                is_correct=is_correct,
                score=score,
            )
            details.append(
                {
                    "question_id": question.id,
                    "is_correct": is_correct,
                    "correct_answer": question.correct_answer,
                    "explanation": question.explanation,
                }
            )

        radar_after = analysis.generate_ability_radar(user)
        return {
            "total": total,
            "correct": correct,
            "accuracy": round((correct / total), 4) if total else 0.0,
            "details": details,
            "weak_points": self.analyze_weak_points(user),
            "radar_delta": analysis.diff_radar(radar_before, radar_after),
        }

    def analyze_weak_points(self, user: User) -> Dict[str, Any]:
        """基于错题统计简单分析弱项"""
        wrong_answers = UserAnswer.objects.filter(user=user, is_correct=False)
        knowledge_point_errors: Dict[int, int] = {}
        for answer in wrong_answers.select_related("question").prefetch_related(
            "question__knowledge_points"
        ):
            for kp in answer.question.knowledge_points.all():
                knowledge_point_errors[kp.id] = knowledge_point_errors.get(kp.id, 0) + 1

        sorted_kp = sorted(knowledge_point_errors.items(), key=lambda x: x[1], reverse=True)
        weak_kp_ids = [kp_id for kp_id, _ in sorted_kp[:10]]
        weak_kps = list(KnowledgePoint.objects.filter(id__in=weak_kp_ids))
        weak_question_types: Dict[str, int] = {}
        for answer in wrong_answers:
            weak_question_types[answer.question.question_type] = (
                weak_question_types.get(answer.question.question_type, 0) + 1
            )

        return {
            "weak_knowledge_points": [kp.name for kp in weak_kps],
            "weak_question_types": weak_question_types,
        }


class CETVocabularyService:
    """词汇学习服务"""

    def create_vocabulary_notebook(
        self,
        user: User,
        word_list: List[str],
        exam_type: str = CET4,
        name: Optional[str] = None,
    ) -> VocabularyNotebook:
        """根据单词列表创建词汇本，并为每个词建立学习记录。"""
        exam_type = CET4
        notebook = VocabularyNotebook.objects.create(
            user=user,
            name=name or f"CET-4 词汇本",
            exam_type=exam_type,
        )
        for raw in word_list:
            word = str(raw or "").strip()
            if not word:
                continue
            vocabulary, _ = Vocabulary.objects.get_or_create(
                word=word,
                exam_type=exam_type,
                defaults={"meaning": "", "example_sentence": ""},
            )
            notebook.vocabularies.add(vocabulary)
            VocabularyLearningRecord.objects.get_or_create(
                user=user,
                vocabulary=vocabulary,
                defaults={"review_count": 0, "correct_count": 0},
            )
        return notebook

    def import_core_notebook(self, user: User, limit: int = 100) -> VocabularyNotebook:
        """从种子四级词库导入核心词本。"""
        words = list(
            Vocabulary.objects.filter(exam_type=CET4)
            .order_by("id")
            .values_list("word", flat=True)[: max(1, min(500, int(limit)))]
        )
        if not words:
            raise ValueError("四级词库为空，请先执行 python manage.py seed_cet4")
        return self.create_vocabulary_notebook(
            user=user,
            word_list=words,
            exam_type=CET4,
            name=f"CET-4 核心词（{len(words)}）",
        )

    def generate_review_plan(
        self,
        user: User,
        notebook: VocabularyNotebook,
    ) -> Dict[str, Any]:
        """根据简单记忆曲线规则生成复习计划。"""
        vocabs = list(notebook.vocabularies.all())
        for v in vocabs:
            VocabularyLearningRecord.objects.get_or_create(
                user=user,
                vocabulary=v,
                defaults={"review_count": 0, "correct_count": 0},
            )

        learning_records = VocabularyLearningRecord.objects.filter(
            user=user,
            vocabulary__in=vocabs,
        ).select_related("vocabulary")

        review_words: List[Dict[str, Any]] = []
        mastered = 0
        now = datetime.utcnow()
        for record in learning_records:
            elapsed_hours = (
                now - record.last_review_time.replace(tzinfo=None)
            ).total_seconds() / 3600
            memory_strength = min(
                1.0, (record.correct_count + 1) / (record.review_count + 1)
            )
            item = {
                "vocabulary_id": record.vocabulary_id,
                "vocabulary": record.vocabulary.word,
                "meaning": record.vocabulary.meaning,
                "example_sentence": record.vocabulary.example_sentence,
                "memory_strength": memory_strength,
                "next_review_time": record.last_review_time,
            }
            if elapsed_hours > 24 or memory_strength < 0.8 or record.review_count == 0:
                review_words.append(item)
            else:
                mastered += 1

        review_words.sort(key=lambda x: x["memory_strength"])
        return {
            "review_words": review_words[:50],
            "total_words": len(vocabs),
            "pending_words": len(review_words),
            "mastered_words": mastered,
        }

    def record_review(
        self,
        user: User,
        vocabulary_id: int,
        remembered: bool,
    ) -> Dict[str, Any]:
        """打卡一次词汇复习。"""
        vocabulary = Vocabulary.objects.get(id=vocabulary_id, exam_type=CET4)
        record, _ = VocabularyLearningRecord.objects.get_or_create(
            user=user,
            vocabulary=vocabulary,
            defaults={"review_count": 0, "correct_count": 0},
        )
        record.review_count = int(record.review_count or 0) + 1
        if remembered:
            record.correct_count = int(record.correct_count or 0) + 1
        record.save(update_fields=["review_count", "correct_count", "last_review_time"])
        strength = min(1.0, (record.correct_count + 1) / (record.review_count + 1))
        return {
            "vocabulary_id": vocabulary.id,
            "word": vocabulary.word,
            "review_count": record.review_count,
            "correct_count": record.correct_count,
            "memory_strength": strength,
        }


class CETAnalysisService:
    """学习分析服务（简版）"""

    DIMENSIONS = (
        "listening",
        "reading",
        "translation",
        "writing",
        "vocabulary",
        "grammar",
    )

    def generate_ability_radar(self, user: User) -> Dict[str, float]:
        """按题型正确率估算能力雷达（无记录时返回中性 0.5）。"""
        rows = (
            UserAnswer.objects.filter(user=user)
            .values("question__question_type")
            .annotate(
                total=Count("id"),
                correct=Count("id", filter=Q(is_correct=True)),
            )
        )
        by_type = {
            r["question__question_type"]: (
                (r["correct"] / r["total"]) if r["total"] else 0.5
            )
            for r in rows
        }
        return {dim: float(by_type.get(dim, 0.5)) for dim in self.DIMENSIONS}

    def diff_radar(
        self,
        before: Dict[str, float],
        after: Dict[str, float],
    ) -> Dict[str, Any]:
        """对比两次雷达快照，供练习/模考结束页展示「可见变化」。"""
        label_map = {
            "listening": "听力",
            "reading": "阅读",
            "translation": "翻译",
            "writing": "写作",
            "vocabulary": "词汇",
            "grammar": "语法",
        }
        delta: Dict[str, float] = {}
        highlights: List[Dict[str, Any]] = []
        for dim in self.DIMENSIONS:
            b = float(before.get(dim, 0.5))
            a = float(after.get(dim, 0.5))
            d = round(a - b, 4)
            delta[dim] = d
            if abs(d) >= 0.0005:
                highlights.append(
                    {
                        "dimension": dim,
                        "label": label_map.get(dim, dim),
                        "before": round(b, 4),
                        "after": round(a, 4),
                        "delta": d,
                        "delta_percent_points": round(d * 100, 2),
                    }
                )
        highlights.sort(key=lambda x: abs(x["delta"]), reverse=True)
        top = highlights[:3]
        if not top:
            summary = "本轮样本对整体雷达影响很小；继续积累后变化会更明显。"
        else:
            bits = []
            for h in top:
                sign = "+" if h["delta_percent_points"] >= 0 else ""
                bits.append(f"{h['label']} {sign}{h['delta_percent_points']} 分点")
            summary = "相对提交前：" + "；".join(bits)
        return {
            "before": {k: round(float(before.get(k, 0.5)), 4) for k in self.DIMENSIONS},
            "after": {k: round(float(after.get(k, 0.5)), 4) for k in self.DIMENSIONS},
            "delta": delta,
            "highlights": top,
            "summary": summary,
        }

    LABEL_MAP = {
        "listening": "听力",
        "reading": "阅读",
        "translation": "翻译",
        "writing": "写作",
        "vocabulary": "词汇",
        "grammar": "语法",
    }

    def _count_vocab_due(self, user: User) -> int:
        """与词汇复习计划同一启发式：间隔过久 / 掌握弱 / 未复习。"""
        now = datetime.utcnow()
        due = 0
        for record in VocabularyLearningRecord.objects.filter(user=user):
            last = record.last_review_time
            if last is None:
                due += 1
                continue
            elapsed_hours = (now - last.replace(tzinfo=None)).total_seconds() / 3600.0
            strength = min(
                1.0, (record.correct_count + 1) / (record.review_count + 1)
            )
            if elapsed_hours > 24 or strength < 0.8 or record.review_count == 0:
                due += 1
        return due

    def _count_wrong_due(self, user: User) -> Tuple[int, int]:
        """返回 (到期复练错题题数, 全部错题题数)。≥20h 前的错题视为到期。"""
        total_wrong = (
            UserAnswer.objects.filter(user=user, is_correct=False)
            .values("question_id")
            .distinct()
            .count()
        )
        cutoff = timezone.now() - timedelta(hours=20)
        due = (
            UserAnswer.objects.filter(
                user=user, is_correct=False, created_at__lte=cutoff
            )
            .values("question_id")
            .distinct()
            .count()
        )
        return due, total_wrong

    def build_learner_snapshot(self, user: User) -> Dict[str, Any]:
        """只读学习者状态：雷达 + 弱项 + 诊断依据 + 今日任务 + 到期复习。"""
        practice = CETPracticeService()
        weak = practice.analyze_weak_points(user)
        radar = self.generate_ability_radar(user)
        types_sorted = sorted(
            (weak.get("weak_question_types") or {}).items(),
            key=lambda x: x[1],
            reverse=True,
        )
        primary_type = types_sorted[0][0] if types_sorted else None
        primary_count = int(types_sorted[0][1]) if types_sorted else 0
        secondary_type = types_sorted[1][0] if len(types_sorted) > 1 else None

        radar_weakest_dim, radar_weakest_val = min(
            ((d, float(radar.get(d, 0.5))) for d in self.DIMENSIONS),
            key=lambda x: x[1],
        )
        primary_label = self.LABEL_MAP.get(primary_type or "", primary_type or "")
        radar_label = self.LABEL_MAP.get(radar_weakest_dim, radar_weakest_dim)
        radar_pct = int(round(radar_weakest_val * 100))

        if primary_type:
            diagnosis_line = (
                f"诊断依据：题型「{primary_label}」累计错 {primary_count} 次"
                f"；雷达最低维「{radar_label}」{radar_pct}%"
            )
            basis_tags = [
                f"题型:{primary_label}",
                f"错次:{primary_count}",
                f"雷达最低:{radar_label} {radar_pct}%",
            ]
        else:
            diagnosis_line = (
                f"诊断依据：暂无错题样本；雷达当前最低维「{radar_label}」{radar_pct}%"
                "——先用词汇热身定位。"
            )
            basis_tags = [f"雷达最低:{radar_label} {radar_pct}%", "样本不足"]

        wrong_due, wrong_total = self._count_wrong_due(user)
        vocab_due = self._count_vocab_due(user)
        today = timezone.localdate()
        if wrong_due > 0 or vocab_due > 0:
            suggested_review_date = today.isoformat()
            bits = []
            if wrong_due:
                bits.append(f"{wrong_due} 道到期错题")
            if vocab_due:
                bits.append(f"{vocab_due} 个到期词")
            suggested_review_note = "建议今天复习：" + "、".join(bits)
        elif primary_type:
            suggested_review_date = (today + timedelta(days=2)).isoformat()
            suggested_review_note = (
                f"练完「{primary_label}」后，建议 {suggested_review_date} 再回来复练弱项。"
            )
        else:
            suggested_review_date = (today + timedelta(days=1)).isoformat()
            suggested_review_note = (
                f"热身完成后，建议 {suggested_review_date} 回来看弱项是否成形。"
            )

        missions: List[Dict[str, Any]] = []

        def _mission(
            title: str,
            why: str,
            cta: str,
            path: str,
            query: Optional[Dict[str, str]] = None,
            kind: str = "practice",
        ) -> Dict[str, Any]:
            return {
                "title": title,
                "why": why,
                "diagnosis_line": diagnosis_line,
                "cta": cta,
                "path": path,
                "query": query or {},
                "kind": kind,
            }

        if wrong_due > 0 and primary_type:
            missions.append(
                _mission(
                    title=f"到期复练：{primary_label} 弱项 8 题",
                    why=suggested_review_note
                    + " 间隔回来练，比连续空刷更有效。",
                    cta=f"复练{primary_label}",
                    path="/cet/practice",
                    query={"type": primary_type, "count": "8"},
                    kind="review_wrong",
                )
            )
        if vocab_due > 0:
            missions.append(
                _mission(
                    title=f"到期词汇：复习约 {min(vocab_due, 10)} 词",
                    why=suggested_review_note
                    + " 不熟的词优先见面，认识的词也算有效行为。",
                    cta="去词汇复习",
                    path="/cet/vocabulary",
                    kind="review_vocab",
                )
            )

        if primary_type:
            missions.append(
                _mission(
                    title=f"针对「{primary_label}」练 8 题（约 12 分钟）",
                    why=(
                        f"因为你最近在「{primary_label}」上错得更多"
                        f"（{primary_count} 次）。只练这一块，进步更容易被看见。"
                    ),
                    cta=f"开始{primary_label}练习",
                    path="/cet/practice",
                    query={"type": primary_type, "count": "8"},
                )
            )
            alt = secondary_type or "vocabulary"
            alt_label = self.LABEL_MAP.get(alt, alt)
            missions.append(
                _mission(
                    title=f"备选：补强「{alt_label}」",
                    why="自主选择：如果今天不想碰最弱项，就从次弱项开始——仍然有效。",
                    cta=f"练{alt_label}",
                    path="/cet/practice",
                    query={"type": alt, "count": "8"},
                )
            )
            missions.append(
                _mission(
                    title="用模考验证这一周有没有真进步",
                    why="练完再拍快照，才能确认能力是否迁移到整卷。",
                    cta="去模考复盘",
                    path="/cet/mock-exam",
                    kind="mock",
                )
            )
        else:
            missions.append(
                _mission(
                    title="热身：做 8 道四级词汇题",
                    why="还没有错题燃料。先用一小段提取练习热身，我们再一起找弱项。",
                    cta="开始词汇热身",
                    path="/cet/practice",
                    query={"type": "vocabulary", "count": "8"},
                )
            )
            missions.append(
                _mission(
                    title="导入四级核心词并打卡 10 个",
                    why="这些词高频出现在四级阅读与听力里；短间隔复习比一次硬背更有效。",
                    cta="去词汇学习",
                    path="/cet/vocabulary",
                    kind="vocab",
                )
            )
            missions.append(
                _mission(
                    title="拍一张能力快照：短模考",
                    why="模考的意义是决定明天练什么，不是给你下判决。",
                    cta="开始四级模考",
                    path="/cet/mock-exam",
                    kind="mock",
                )
            )

        # 去重：同 path+query 只留第一次（到期复练优先）
        seen = set()
        unique_missions: List[Dict[str, Any]] = []
        for m in missions:
            key = (m["path"], tuple(sorted((m.get("query") or {}).items())))
            if key in seen:
                continue
            seen.add(key)
            unique_missions.append(m)

        return {
            "radar": {k: round(float(radar.get(k, 0.5)), 4) for k in self.DIMENSIONS},
            "weak_points": weak,
            "diagnosis": {
                "primary_type": primary_type,
                "primary_label": primary_label or None,
                "primary_wrong_count": primary_count,
                "radar_weakest": radar_weakest_dim,
                "radar_weakest_label": radar_label,
                "radar_weakest_percent": radar_pct,
                "line": diagnosis_line,
                "basis_tags": basis_tags,
            },
            "review": {
                "wrong_due_count": wrong_due,
                "wrong_total": wrong_total,
                "vocab_due_count": vocab_due,
                "suggested_review_date": suggested_review_date,
                "suggested_review_note": suggested_review_note,
            },
            "today_missions": unique_missions,
            "weak_practice": {
                "path": "/cet/practice",
                "query": {
                    "type": primary_type or "vocabulary",
                    "count": "8",
                },
                "cta": f"针对{(primary_label or '词汇')}练 8 题",
            },
        }


class CETWritingService:
    """写作/翻译批改服务（调用现有 AI 模型，返回结构化评分结果）"""

    def __init__(self, model: str = "deepseek-chat"):
        self.model = model
        self.ai_service = None
        self._init_ai_service()

    def _get_provider_key(self, model: str) -> str:
        if model.startswith("deepseek"):
            return "deepseek"
        if model.startswith("qwen"):
            return "qwen"
        if model.startswith("glm") or model.startswith("cogview"):
            return "glm"
        return "deepseek"

    def _init_ai_service(self) -> None:
        """复用 QAService 的 AI 初始化策略"""
        from django.conf import settings  # 延迟导入以避免循环

        provider_key = self._get_provider_key(self.model)
        api_key: Optional[str] = None

        ai_config = getattr(settings, "AI_ENGINE_CONFIG", {})
        api_key = (ai_config.get(provider_key) or {}).get("api_key")

        if not api_key or not str(api_key).strip():
            import os

            api_key = os.getenv(f"{provider_key.upper()}_API_KEY")

        if api_key and str(api_key).strip():
            self.ai_service = AIServiceFactory.create_service(self.model, api_key.strip())

    def _call_llm(self, system_prompt: str, user_content: str) -> str:
        if not self.ai_service:
            return "无法连接到写作批改模型，请检查后端 AI 配置。"
        messages = self.ai_service.format_messages(system_prompt, user_content)
        return self.ai_service.generate_response(messages)

    def grade_writing(self, question: CETQuestion, content: str) -> Dict[str, Any]:
        """对作文或翻译进行多维度评分，并返回结构化结果"""
        system_prompt = (
            "你是一名专业的大学英语四级/六级写作与翻译评分教师，"
            "需要根据题目与考生作文，从内容、语言、结构、连贯性等维度给出评分与详细建议。"
            "请尽量使用中文说明理由，但保留关键英文例句。"
        )
        user_prompt = f"""
题目类型：{question.get_question_type_display()}
题目内容（原题）：
{question.content}

考生作文/翻译内容：
{content}

请你进行认真评分，并按以下 JSON 结构返回（不要添加多余解释）：
{{
  "total_score": 评分总分（0-100 的数字）,
  "scores": {{
    "content": 内容得分（0-25 的数字）,
    "language": 语言得分（0-25 的数字）,
    "structure": 结构得分（0-25 的数字）,
    "coherence": 连贯性得分（0-25 的数字）
  }},
  "feedback": "用中文给出整体评价，说明优点与不足",
  "suggestions": [
    "改进建议1",
    "改进建议2"
  ]
}}
"""
        raw = self._call_llm(system_prompt, user_prompt)

        # 尝试解析 JSON，失败则退化为仅返回文本反馈
        parsed: Dict[str, Any]
        try:
            # 去掉可能的代码块包裹
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.strip("`")
                # 去掉可能的语言标记行
                lines = cleaned.splitlines()
                if lines and not lines[0].lstrip().startswith("{"):
                    cleaned = "\n".join(lines[1:])
            parsed = json.loads(cleaned)
        except Exception:
            parsed = {
                "total_score": None,
                "scores": {},
                "feedback": raw,
                "suggestions": [],
            }

        # 填充默认字段，避免前端解析出错
        scores = parsed.get("scores") or {}
        stem = " ".join((question.content or "").split())
        if len(stem) > 80:
            stem = stem[:80] + "…"
        evidence_line = f"对照题目要求：{stem}" if stem else "对照题目要求：请紧扣题干任务作答。"
        return {
            "total_score": parsed.get("total_score"),
            "scores": {
                "content": scores.get("content"),
                "language": scores.get("language"),
                "structure": scores.get("structure"),
                "coherence": scores.get("coherence"),
            },
            "feedback": parsed.get("feedback"),
            "suggestions": parsed.get("suggestions") or [],
            "evidence_line": evidence_line,
            "question_brief": stem,
            "raw": raw,
        }


class CETListeningService:
    """听力文本处理服务：基于听力原文生成摘要、关键词和练习题草案"""

    def __init__(self, model: str = "deepseek-chat"):
        self.model = model
        self.ai_service = None
        self._init_ai_service()

    def _get_provider_key(self, model: str) -> str:
        if model.startswith("deepseek"):
            return "deepseek"
        if model.startswith("qwen"):
            return "qwen"
        if model.startswith("glm") or model.startswith("cogview"):
            return "glm"
        return "deepseek"

    def _init_ai_service(self) -> None:
        from django.conf import settings
        import os

        provider_key = self._get_provider_key(self.model)
        ai_config = getattr(settings, "AI_ENGINE_CONFIG", {})
        api_key = (ai_config.get(provider_key) or {}).get("api_key") or os.getenv(
            f"{provider_key.upper()}_API_KEY"
        )
        if api_key and str(api_key).strip():
            self.ai_service = AIServiceFactory.create_service(self.model, api_key.strip())

    def _call_llm(self, system_prompt: str, user_content: str) -> str:
        if not self.ai_service:
            return "无法连接到听力分析模型，请检查后端 AI 配置。"
        messages = self.ai_service.format_messages(system_prompt, user_content)
        return self.ai_service.generate_response(messages)

    def process_transcript(self, transcript: str) -> Dict[str, Any]:
        """基于听力原文生成摘要、关键词和题目草案"""
        system_prompt = (
            "你是一名大学英语四级/六级听力教师，负责基于听力原文生成学习材料。"
            "请只返回 JSON，不要添加任何多余说明。"
        )
        user_prompt = f"""
以下是英语听力原文（可能包含中英文混排），请你完成三个任务：
1）用中文给出 2-3 句听力内容摘要；
2）提取 5-10 个英文关键词或短语；
3）基于原文设计 3-5 道练习题（可包含选择题/判断题/填空题），题干用英文，可附中文提示。

请按下面 JSON 结构返回（严格 JSON 格式）：
{{
  "summary": "中文摘要",
  "keywords": ["keyword1", "keyword2", "..."],
  "questions": [
    {{
      "type": "choice | true_false | gap_fill",
      "question": "英文题干",
      "options": ["A", "B", "C", "D"],
      "answer": "正确答案（如 'A' 或 'True' 或 填空答案）",
      "explanation": "中文解析（可选）"
    }}
  ]
}}

听力原文：
{transcript}
"""
        raw = self._call_llm(system_prompt, user_prompt)
        try:
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.strip("`")
                lines = cleaned.splitlines()
                if lines and not lines[0].lstrip().startswith("{"):
                    cleaned = "\n".join(lines[1:])
            data = json.loads(cleaned)
        except Exception:
            data = {
                "summary": "",
                "keywords": [],
                "questions": [],
            }
        return {
            "summary": data.get("summary", ""),
            "keywords": data.get("keywords") or [],
            "questions": data.get("questions") or [],
            "raw": raw,
        }


class CETExamService:
    """模拟考试服务（简化版）"""

    # 四级模考各题型配额（总计约 30 题，保证可练完）
    MOCK_QUOTA = {
        "listening": 6,
        "reading": 8,
        "vocabulary": 6,
        "grammar": 4,
        "translation": 3,
        "writing": 1,
    }

    def create_mock_exam(
        self,
        user: User,
        exam_type: str = CET4,
    ) -> MockExam:
        """创建四级模考：按题型配额抽取，避免空卷或单一题型刷屏。"""
        exam_type = CET4
        picked: List[CETQuestion] = []
        for qtype, quota in self.MOCK_QUOTA.items():
            chunk = list(
                _cet4_questions()
                .filter(question_type=qtype)
                .order_by("?")[:quota]
            )
            picked.extend(chunk)
        if not picked:
            picked = list(_cet4_questions().order_by("?")[:30])

        mock_exam = MockExam.objects.create(
            user=user,
            exam_type=exam_type,
        )
        if picked:
            mock_exam.questions.set(picked)
        return mock_exam

    def submit_exam(self, mock_exam: MockExam, answers: Dict[str, Any]) -> Dict[str, Any]:
        """提交考试并计算各部分得分；附带雷达前后对比。"""
        analysis = CETAnalysisService()
        radar_before = analysis.generate_ability_radar(mock_exam.user)

        section_correct: Dict[str, int] = {}
        section_total: Dict[str, int] = {}
        total_correct = 0
        total_questions = 0

        for q in mock_exam.questions.all():
            qid = str(q.id)
            user_answer = str(answers.get(qid, "") or "").strip()
            total_questions += 1
            section_total[q.question_type] = section_total.get(q.question_type, 0) + 1

            is_objective = q.question_type in OBJECTIVE_TYPES
            is_correct = False
            score = None

            if is_objective and q.correct_answer:
                is_correct = user_answer.lower() == q.correct_answer.strip().lower()
                score = 1.0 if is_correct else 0.0

            UserAnswer.objects.create(
                user=mock_exam.user,
                question=q,
                user_answer=user_answer,
                is_correct=is_correct,
                score=score,
            )

            if is_correct:
                total_correct += 1
                section_correct[q.question_type] = section_correct.get(q.question_type, 0) + 1

        mock_exam.is_submitted = True
        mock_exam.save(update_fields=["is_submitted"])

        total_score = (total_correct / total_questions * 100.0) if total_questions else 0.0
        section_scores: Dict[str, float] = {}
        for qtype, cnt in section_total.items():
            correct_cnt = section_correct.get(qtype, 0)
            section_scores[qtype] = (correct_cnt / cnt * 100.0) if cnt else 0.0

        radar_after = analysis.generate_ability_radar(mock_exam.user)
        return {
            "total_score": round(total_score, 2),
            "section_scores": {k: round(v, 2) for k, v in section_scores.items()},
            "total_questions": total_questions,
            "total_correct": total_correct,
            "radar_delta": analysis.diff_radar(radar_before, radar_after),
            "weak_points": CETPracticeService().analyze_weak_points(mock_exam.user),
        }


class CETTutorService:
    """四级答疑 / 伴读：有限轮次 + 强制收束到弱项练习（Duolingo Closer 纪律）。"""

    MAX_TURNS = 6

    def __init__(self, model: str = "deepseek-chat", max_turns: int = MAX_TURNS):
        self.model = model
        self.max_turns = max(1, min(12, int(max_turns or self.MAX_TURNS)))
        self.ai_service = None
        self._init_ai_service()

    def _get_provider_key(self, model: str) -> str:
        if model.startswith("deepseek"):
            return "deepseek"
        if model.startswith("qwen"):
            return "qwen"
        if model.startswith("glm") or model.startswith("cogview"):
            return "glm"
        return "deepseek"

    def _init_ai_service(self) -> None:
        from django.conf import settings
        import os

        provider_key = self._get_provider_key(self.model)
        ai_config = getattr(settings, "AI_ENGINE_CONFIG", {})
        api_key = (ai_config.get(provider_key) or {}).get("api_key") or os.getenv(
            f"{provider_key.upper()}_API_KEY"
        )
        if api_key and str(api_key).strip():
            self.ai_service = AIServiceFactory.create_service(self.model, api_key.strip())

    def _closer_payload(self, user: User) -> Dict[str, Any]:
        snap = CETAnalysisService().build_learner_snapshot(user)
        weak = snap.get("weak_practice") or {}
        diagnosis = (snap.get("diagnosis") or {}).get("line") or ""
        return {
            "summary": "本轮答疑到此结束。把刚弄清的点立刻练一遍，比继续聊更有效。",
            "cta": weak.get("cta") or "针对弱项练 8 题",
            "path": weak.get("path") or "/cet/practice",
            "query": weak.get("query") or {"type": "vocabulary", "count": "8"},
            "diagnosis_line": diagnosis,
        }

    def _fallback_reply(self, message: str, diagnosis_line: str, turns_remaining: int) -> str:
        tip = diagnosis_line or "先围绕今日弱项提问。"
        if turns_remaining <= 0:
            return (
                f"我先用一句话回应：围绕「{message[:40]}」请对照真题场景理解考点，"
                f"然后立刻去做练习巩固。{tip}"
            )
        return (
            f"关于「{message[:60]}」：建议先抓住题干关键词与选项差异，"
            f"再用一道同题型题验证。{tip}"
            f"（本轮还剩 {turns_remaining} 次提问）"
        )

    def _llm_reply(self, message: str, diagnosis_line: str, turns_remaining: int) -> str:
        if not self.ai_service:
            return self._fallback_reply(message, diagnosis_line, turns_remaining)
        system_prompt = (
            "你是大学英语四级备考答疑助手。只解答与四级词汇/听力/阅读/写作/翻译/语法相关的问题。"
            "不要直接泄整题答案；用简短中文给思路与考点。"
            "禁止无休止追问；若用户已理解，鼓励去练题。"
            f"当前学习诊断：{diagnosis_line or '暂无'}。"
            f"本轮用户还可提问 {turns_remaining} 次后必须结束。"
        )
        try:
            messages = self.ai_service.format_messages(system_prompt, message)
            text = (self.ai_service.generate_response(messages) or "").strip()
            return text or self._fallback_reply(message, diagnosis_line, turns_remaining)
        except Exception:
            return self._fallback_reply(message, diagnosis_line, turns_remaining)

    def respond(
        self,
        user: User,
        message: str,
        prior_user_turns: int = 0,
    ) -> Dict[str, Any]:
        """
        prior_user_turns：本会话中用户已完成的提问次数（不含本条）。
        达到 max_turns 后拒绝继续聊，只返回收束 CTA。
        """
        closer = self._closer_payload(user)
        try:
            prior = max(0, int(prior_user_turns))
        except (TypeError, ValueError):
            prior = 0

        if prior >= self.max_turns:
            return {
                "reply": "这一轮答疑预算已经用完。" + closer["summary"],
                "user_turn_count": prior,
                "max_turns": self.max_turns,
                "turns_remaining": 0,
                "session_closed": True,
                "closer": closer,
            }

        text = (message or "").strip()
        if not text:
            return {
                "error": "请输入想问的四级问题",
                "user_turn_count": prior,
                "max_turns": self.max_turns,
                "turns_remaining": self.max_turns - prior,
                "session_closed": False,
                "closer": None,
            }

        new_count = prior + 1
        remaining_after = self.max_turns - new_count
        session_closed = remaining_after <= 0
        # 生成回复时告知「本条之后还剩几次」
        reply = self._llm_reply(
            text,
            closer.get("diagnosis_line") or "",
            max(0, remaining_after),
        )
        if session_closed:
            reply = f"{reply}\n\n{closer['summary']}"

        return {
            "reply": reply,
            "user_turn_count": new_count,
            "max_turns": self.max_turns,
            "turns_remaining": max(0, remaining_after),
            "session_closed": session_closed,
            "closer": closer if session_closed else None,
        }

