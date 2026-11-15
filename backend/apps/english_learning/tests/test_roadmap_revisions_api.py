"""路线修订列表 API 与 graph 草案模块可导入性。"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.english_learning.models import RoadmapRevision
from apps.english_learning.services import get_or_create_profile

User = get_user_model()


class RoadmapRevisionsApiTests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(
            username="rev_a", email="rev_a@t.local", password="pw-rev"
        )
        self.user_b = User.objects.create_user(
            username="rev_b", email="rev_b@t.local", password="pw-rev"
        )
        self.profile_a = get_or_create_profile(self.user_a)
        self.profile_b = get_or_create_profile(self.user_b)

    def test_list_only_own_revisions(self):
        RoadmapRevision.objects.create(
            profile=self.profile_a, version=1, markdown="# A only", source_skill_run_id=""
        )
        RoadmapRevision.objects.create(
            profile=self.profile_b, version=1, markdown="# B only", source_skill_run_id=""
        )
        url = reverse("english-roadmap-revisions")
        self.client.force_authenticate(user=self.user_a)
        r = self.client.get(url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["markdown"], "# A only")
        self.client.force_authenticate(user=self.user_b)
        r2 = self.client.get(url)
        self.assertEqual(len(r2.data), 1)
        self.assertEqual(r2.data[0]["markdown"], "# B only")

    def test_revision_includes_knowledge_base_id_from_document(self):
        from apps.knowledge.models import Document

        doc = Document.objects.create(
            knowledge_base=self.profile_a.default_kb,
            title="Roadmap doc",
            content="# body",
            content_type="markdown",
            file_path="",
            content_hash="c" * 64,
        )
        RoadmapRevision.objects.create(
            profile=self.profile_a,
            version=10,
            markdown="# v10",
            document=doc,
            source_skill_run_id="",
        )
        self.client.force_authenticate(user=self.user_a)
        r = self.client.get(reverse("english-roadmap-revisions"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        row = next(x for x in r.data if x["version"] == 10)
        self.assertEqual(row["document_id"], str(doc.pk))
        self.assertEqual(row["knowledge_base_id"], str(self.profile_a.default_kb_id))

    def test_revision_without_document_has_null_knowledge_base_id(self):
        RoadmapRevision.objects.create(
            profile=self.profile_a, version=5, markdown="# no doc", source_skill_run_id=""
        )
        self.client.force_authenticate(user=self.user_a)
        r = self.client.get(reverse("english-roadmap-revisions"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        row = next(x for x in r.data if x["version"] == 5)
        self.assertIsNone(row.get("knowledge_base_id"))

    def test_limit_query_clamped(self):
        for v in range(1, 4):
            RoadmapRevision.objects.create(
                profile=self.profile_a, version=v, markdown=f"# v{v}", source_skill_run_id=""
            )
        self.client.force_authenticate(user=self.user_a)
        r = self.client.get(reverse("english-roadmap-revisions"), {"limit": "2"})
        self.assertEqual(len(r.data), 2)


class EnglishLearningGraphDraftSmokeTests(SimpleTestCase):
    def test_graph_exports_without_langgraph(self):
        from apps.english_learning.graph import WIZARD_GRAPH_NODE_NAMES
        from apps.english_learning.graph.state import EnglishLearningState

        self.assertIn("tutor_runtime", WIZARD_GRAPH_NODE_NAMES)
        st: EnglishLearningState = {"phase": "tutor", "kb_id": "x"}
        self.assertEqual(st.get("phase"), "tutor")
