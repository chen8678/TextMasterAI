from django.core.management.base import BaseCommand

from apps.english_learning.curriculum.constants import CURRICULUM_TIERS, RAW_DIR
from apps.english_learning.curriculum.services import (
    backfill_all_users_curriculum_access,
    init_all_curriculum_kbs,
)


class Command(BaseCommand):
    help = "初始化系统预置英语词库知识库（小学→六级），并为用户挂载只读访问"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-vectorize",
            action="store_true",
            help="跳过向量化（开发/CI 加速；生产勿用）",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="强制重建文档（删除 tier 内旧文档后重新导入）",
        )
        parser.add_argument(
            "--chunk-size",
            type=int,
            default=120,
            help="每篇 Document 词条数（默认 120）",
        )
        parser.add_argument(
            "--slug",
            action="append",
            dest="slugs",
            help="仅导入指定 slug（可多次指定）",
        )
        parser.add_argument(
            "--backfill-users",
            action="store_true",
            help="为全部已有用户补挂 curriculum 只读成员",
        )

    def handle(self, *args, **options):
        if not RAW_DIR.is_dir():
            self.stderr.write(
                self.style.ERROR(
                    f"raw 目录不存在: {RAW_DIR}\n请先运行: ./scripts/download_english_curriculum_data.sh"
                )
            )
            return

        missing = []
        for tier in CURRICULUM_TIERS:
            if options.get("slugs") and tier.slug not in options["slugs"]:
                continue
            if not (RAW_DIR / tier.source_file).is_file():
                missing.append(tier.source_file)
        if missing:
            self.stderr.write(
                self.style.ERROR(
                    "缺少词库文件:\n  "
                    + "\n  ".join(missing)
                    + "\n请运行 ./scripts/download_english_curriculum_data.sh"
                )
            )
            return

        results = init_all_curriculum_kbs(
            chunk_size=options["chunk_size"],
            skip_vectorize=options["skip_vectorize"],
            force=options["force"],
            slugs=options.get("slugs"),
        )
        for row in results:
            if row.get("skipped"):
                self.stdout.write(
                    self.style.WARNING(
                        f"[skip] {row['slug']}: kb={row['kb_id']} docs={row['documents']} words={row['words']}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[ok] {row['slug']}: kb={row['kb_id']} "
                        f"docs={row['documents']} (+{row.get('documents_created', 0)}) words={row['words']}"
                    )
                )

        if options["backfill_users"]:
            n = backfill_all_users_curriculum_access()
            self.stdout.write(self.style.SUCCESS(f"backfill memberships created: {n}"))

        self.stdout.write(self.style.SUCCESS("init_english_curriculum 完成"))
