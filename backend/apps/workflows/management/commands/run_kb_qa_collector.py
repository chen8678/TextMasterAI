from __future__ import annotations

import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.knowledge.models import KnowledgeBase
from apps.workflows.kb_collector_personas import (
    build_workflow_config_from_persona,
    list_personas,
    resolve_persona_for_kb,
)
from apps.workflows.kb_qa_collector_workflow import run_kb_qa_collector_workflow


class Command(BaseCommand):
    help = "运行 KB 问答采集工作流：按知识库角色模拟提问 → KB 编排 → 导出训练 JSON/JSONL。"

    def add_arguments(self, parser):
        parser.add_argument("--kb-id", type=str, default="", help="知识库 UUID")
        parser.add_argument("--username", type=str, default="", help="执行用户（默认取知识库 owner）")
        parser.add_argument(
            "--config",
            type=str,
            default="",
            help="可选工作流配置 JSON；不传则按知识库自动匹配提问角色",
        )
        parser.add_argument("--persona-id", type=str, default="", help="强制指定提问角色 ID")
        parser.add_argument("--no-persona", action="store_true", help="禁用按知识库自动匹配角色")
        parser.add_argument("--list-personas", action="store_true", help="列出已注册的提问角色")
        parser.add_argument("--questions", type=str, nargs="*", default=[], help="内联问题列表")
        parser.add_argument("--dry-run", action="store_true", help="只解析问题，不调用 KB")

    def handle(self, *args, **options):
        if options["list_personas"]:
            for item in list_personas():
                kb_ids = ", ".join(item.get("knowledge_base_ids") or [])
                self.stdout.write(
                    f"{item['id']}\t{item['role_name']}\tKB={kb_ids}\tseed={item.get('seed_path')}"
                )
            return

        kb_id = options["kb_id"]
        if not kb_id:
            self.stderr.write(self.style.ERROR("请提供 --kb-id，或使用 --list-personas 查看角色"))
            return

        kb = KnowledgeBase.objects.filter(id=kb_id).first()
        if not kb:
            self.stderr.write(self.style.ERROR(f"知识库不存在: {kb_id}"))
            return

        user = kb.owner
        if options["username"]:
            user = get_user_model().objects.filter(username=options["username"]).first()
            if not user:
                self.stderr.write(self.style.ERROR(f"用户不存在: {options['username']}"))
                return

        persona = None
        if not options["no_persona"]:
            persona = resolve_persona_for_kb(
                knowledge_base_id=str(kb_id),
                knowledge_base_title=kb.title,
                persona_id=options["persona_id"],
            )

        cfg: dict = {}
        config_path = options["config"]
        if config_path:
            if not Path(config_path).is_file():
                self.stderr.write(self.style.ERROR(f"配置文件不存在: {config_path}"))
                return
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        elif persona:
            cfg = build_workflow_config_from_persona(persona)
            self.stdout.write(
                self.style.NOTICE(
                    f"已自动匹配角色：{persona.role_name} ({persona.id})"
                )
            )

        inline_questions = options["questions"] or cfg.get("questions") or []
        result = run_kb_qa_collector_workflow(
            knowledge_base_id=str(kb_id),
            user=user,
            questions=inline_questions,
            question_source=cfg.get("question_source", "inline"),
            seed_path=cfg.get("seed_path", ""),
            llm_question_count=int(cfg.get("llm_question_count") or 0),
            agent_id=cfg.get("agent_id", "qa"),
            ai_model=cfg.get("ai_model", "deepseek"),
            config=cfg.get("config") or {},
            retrieval_params=cfg.get("retrieval_params"),
            instruction=cfg.get("instruction", ""),
            delay_seconds=float(cfg.get("delay_seconds", 0.5)),
            max_questions=int(cfg.get("max_questions", 50)),
            output_path=cfg.get("output_path", ""),
            dry_run=bool(options["dry_run"] or cfg.get("dry_run", False)),
            persona_id=options["persona_id"] or cfg.get("persona_id", ""),
            auto_use_persona=not options["no_persona"],
            persona=persona,
        )

        if result.get("success"):
            self.stdout.write(self.style.SUCCESS("采集完成"))
            if result.get("role_name"):
                self.stdout.write(f"提问角色: {result.get('role_name')} ({result.get('persona_id')})")
            self.stdout.write(f"run_id: {result.get('run_id')}")
            self.stdout.write(f"采集条数: {result.get('total_collected')}")
            self.stdout.write(f"JSON: {result.get('output_path')}")
            self.stdout.write(f"JSONL: {result.get('jsonl_path')}")
        else:
            self.stderr.write(self.style.ERROR(result.get("error") or "采集失败"))
            for err in result.get("errors") or []:
                self.stderr.write(f"  - {err.get('question')}: {err.get('error')}")
