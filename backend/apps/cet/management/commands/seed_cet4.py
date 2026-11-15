"""灌入大学英语四级种子：试卷、知识点、题目、核心词汇。"""
from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.cet.models import CETExam, CETQuestion, KnowledgePoint, Vocabulary


class Command(BaseCommand):
    help = "Seed CET-4 exam, knowledge points, questions, and core vocabulary"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-questions",
            action="store_true",
            help="删除种子试卷下的旧题后重建（不影响用户答题记录以外的试卷）",
        )

    def handle(self, *args, **options):
        data_path = Path(__file__).resolve().parents[2] / "data" / "cet4_seed.json"
        if not data_path.exists():
            self.stderr.write(self.style.ERROR(f"missing seed file: {data_path}"))
            return

        payload = json.loads(data_path.read_text(encoding="utf-8"))
        with transaction.atomic():
            exam_meta = payload["exam"]
            exam, _ = CETExam.objects.update_or_create(
                exam_type="cet4",
                title=exam_meta.get("title") or "CET-4 备考练习卷（内置种子）",
                defaults={
                    "year": exam_meta.get("year"),
                    "is_official": bool(exam_meta.get("is_official", False)),
                },
            )

            kp_map = {}
            for item in payload.get("knowledge_points") or []:
                kp, _ = KnowledgePoint.objects.update_or_create(
                    name=item["name"],
                    defaults={
                        "category": item.get("category") or "strategy",
                        "description": item.get("description") or "",
                    },
                )
                kp_map[kp.name] = kp

            vocab_created = 0
            for item in payload.get("vocabularies") or []:
                _, created = Vocabulary.objects.update_or_create(
                    word=item["word"].strip(),
                    exam_type="cet4",
                    defaults={
                        "meaning": item.get("meaning") or "",
                        "example_sentence": item.get("example_sentence") or "",
                    },
                )
                if created:
                    vocab_created += 1

            if options.get("reset_questions"):
                CETQuestion.objects.filter(exam=exam).delete()

            q_created = 0
            for item in payload.get("questions") or []:
                q, created = CETQuestion.objects.update_or_create(
                    exam=exam,
                    question_type=item["question_type"],
                    question_number=int(item.get("question_number") or 1),
                    defaults={
                        "content": item.get("content") or "",
                        "options": item.get("options") or [],
                        "correct_answer": item.get("correct_answer") or "",
                        "explanation": item.get("explanation") or "",
                        "difficulty": int(item.get("difficulty") or 3),
                    },
                )
                names = item.get("knowledge_points") or []
                q.knowledge_points.set([kp_map[n] for n in names if n in kp_map])
                if created:
                    q_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"CET-4 seed OK: exam_id={exam.id} "
                f"vocab+={vocab_created}/{Vocabulary.objects.filter(exam_type='cet4').count()} "
                f"questions+={q_created}/{CETQuestion.objects.filter(exam=exam).count()}"
            )
        )
