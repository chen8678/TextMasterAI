"""将 SCAR/data/construction/samples 导入独立知识库并结构编译。"""

from __future__ import annotations

from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.knowledge.models import Document, KnowledgeBase
from apps.scar.services.ingest import compile_document
from apps.scar.services.schema_compiler import repo_construction_data_dir


class Command(BaseCommand):
    help = "SCAR：导入 construction 样例 JSON 到知识库并编译"

    def add_arguments(self, parser):
        parser.add_argument("--knowledge-base-id", default="", help="已有 KB；空则新建")
        parser.add_argument("--title", default="SCAR construction eval")
        parser.add_argument("--owner-username", default="admin")
        parser.add_argument("--no-vectorize", action="store_true", default=True)
        parser.add_argument("--vectorize", action="store_true", help="尝试定向向量化")
        parser.add_argument(
            "--samples-subdir",
            default="samples",
            help="相对 construction 数据目录：samples 或 samples_v2",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        owner = User.objects.filter(username=options["owner_username"]).first()
        if not owner:
            owner = User.objects.order_by("date_joined").first()
        if not owner:
            raise CommandError("无可用用户，无法创建知识库")

        kb_id = (options["knowledge_base_id"] or "").strip()
        if kb_id:
            try:
                kb = KnowledgeBase.objects.get(id=kb_id)
            except KnowledgeBase.DoesNotExist as e:
                raise CommandError(f"KB 不存在: {kb_id}") from e
        else:
            kb = KnowledgeBase.objects.create(
                title=options["title"],
                description="SCAR heldout 评测用 construction 样例库",
                owner=owner,
                category="engineering",
                settings={"scar_domain": "construction", "purpose": "scar_eval"},
            )

        subdir = (options["samples_subdir"] or "samples").strip() or "samples"
        samples_dir = repo_construction_data_dir() / subdir
        paths = sorted(samples_dir.glob("site_*.json"))
        if not paths:
            raise CommandError(f"无样例: {samples_dir}")

        vectorize = bool(options["vectorize"])
        imported = []
        for path in paths:
            raw = path.read_text(encoding="utf-8")
            title = path.stem  # site_A / site_C00
            doc = Document.objects.filter(knowledge_base=kb, title=title).first()
            if doc:
                doc.content = raw
                doc.content_type = "text"
                doc.metadata = {**(doc.metadata or {}), "scar_sample": title, "source_file": path.name}
                doc.save(update_fields=["content", "content_type", "metadata", "updated_at"])
            else:
                doc = Document.objects.create(
                    knowledge_base=kb,
                    title=title,
                    content=raw,
                    content_type="text",
                    metadata={"scar_sample": title, "source_file": path.name},
                )
            result = compile_document(doc, domain="construction", raw_text=raw, vectorize=vectorize)
            doc_vec_ok = False
            if vectorize:
                doc_vec_ok = self._vectorize_document(doc)
            imported.append(
                {
                    "title": title,
                    "document_id": str(doc.id),
                    "document_vectorized": doc_vec_ok,
                    **result,
                }
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"knowledge_base_id={kb.id}\n" + "\n".join(str(x) for x in imported)
            )
        )

    def _vectorize_document(self, document: Document) -> bool:
        """为 Document 整篇写入 vector_embedding，供 B0 hybrid 使用。"""
        try:
            from apps.knowledge.vectorization_service import VectorizationService

            emb = VectorizationService().vectorize_text(document.content or "")
            document.vector_embedding = emb.tolist() if hasattr(emb, "tolist") else list(emb)
            document.save(update_fields=["vector_embedding", "updated_at"])
            return True
        except Exception as e:
            self.stderr.write(self.style.WARNING(f"Document 向量化失败 {document.title}: {e}"))
            return False
