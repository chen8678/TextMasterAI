from django.core.management.base import BaseCommand, CommandError
from apps.knowledge.models import Document
from apps.scar.services.ingest import compile_document


class Command(BaseCommand):
    help = "SCAR：对指定 Document 执行结构编译与定向索引"

    def add_arguments(self, parser):
        parser.add_argument("--document-id", required=True)
        parser.add_argument("--domain", default="construction")
        parser.add_argument("--no-vectorize", action="store_true")

    def handle(self, *args, **options):
        doc_id = options["document_id"]
        try:
            doc = Document.objects.get(id=doc_id)
        except Document.DoesNotExist as e:
            raise CommandError(f"Document 不存在: {doc_id}") from e
        result = compile_document(
            doc,
            domain=options["domain"],
            vectorize=not options["no_vectorize"],
        )
        if not result.get("ok"):
            raise CommandError(result.get("error") or "compile failed")
        self.stdout.write(self.style.SUCCESS(str(result)))
