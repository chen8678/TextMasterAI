"""预置英语 curriculum 知识库单测。"""

import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.english_learning.curriculum.constants import CURRICULUM_TIERS
from apps.english_learning.curriculum.parsers import parse_kylebing_json, parse_kajweb_jsonl
from apps.english_learning.curriculum.services import import_tier_into_kb
from apps.english_learning.services import get_or_create_profile
from apps.knowledge.models import KnowledgeBaseMember

User = get_user_model()

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "curriculum"


class CurriculumParserTests(APITestCase):
    def test_parse_kylebing_sample(self):
        path = FIXTURE_DIR / "sample_junior.json"
        entries = parse_kylebing_json(path)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].word, "hello")

    def test_parse_kajweb_jsonl_sample(self):
        path = FIXTURE_DIR / "sample_primary.jsonl"
        entries = parse_kajweb_jsonl(path)
        self.assertGreaterEqual(len(entries), 1)
        self.assertTrue(entries[0].word)


class CurriculumInitTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="curr_user", email="curr@t.local", password="pw-curr"
        )
        self._tmp_raw = Path(tempfile.mkdtemp())
        self._raw_patch = patch(
            "apps.english_learning.curriculum.services.RAW_DIR",
            self._tmp_raw,
        )
        self._raw_patch.start()
        (self._tmp_raw / "1-初中-顺序.json").write_text(
            (FIXTURE_DIR / "sample_junior.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (self._tmp_raw / "primary_merged.jsonl").write_text(
            (FIXTURE_DIR / "sample_primary.jsonl").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    def tearDown(self):
        self._raw_patch.stop()

    def test_import_junior_tier_creates_kb_and_docs(self):
        tier = next(t for t in CURRICULUM_TIERS if t.slug == "junior")
        result = import_tier_into_kb(tier, chunk_size=50, skip_vectorize=True, force=True)
        self.assertFalse(result["skipped"])
        self.assertGreaterEqual(result["documents"], 1)
        self.assertEqual(result["words"], 2)

    def test_user_gets_viewer_membership_on_profile(self):
        tier = next(t for t in CURRICULUM_TIERS if t.slug == "junior")
        import_tier_into_kb(tier, chunk_size=50, skip_vectorize=True, force=True)
        profile = get_or_create_profile(self.user)
        self.assertIsNotNone(profile.default_kb_id)
        n = KnowledgeBaseMember.objects.filter(user=self.user).count()
        self.assertGreaterEqual(n, 1)

    def test_curriculum_api_lists_libraries(self):
        tier = next(t for t in CURRICULUM_TIERS if t.slug == "junior")
        import_tier_into_kb(tier, chunk_size=50, skip_vectorize=True, force=True)
        self.client.force_authenticate(user=self.user)
        get_or_create_profile(self.user)
        url = reverse("english-curriculum")
        r = self.client.get(url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("libraries", r.data)
        self.assertTrue(any(lib.get("slug") == "junior" for lib in r.data["libraries"]))
