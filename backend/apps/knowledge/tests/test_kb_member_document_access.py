"""共享知识库成员：文档列表/详情/写操作的权限矩阵（E2 扩展）。"""
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.english_learning.services import get_or_create_profile
from apps.knowledge.models import Document, KnowledgeBaseMember

User = get_user_model()


class KnowledgeBaseMemberDocumentAccessTests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(
            username="kb_mem_a", email="kb_mem_a@t.local", password="pw-kb-mem"
        )
        self.user_b = User.objects.create_user(
            username="kb_mem_b", email="kb_mem_b@t.local", password="pw-kb-mem"
        )
        self.profile_a = get_or_create_profile(self.user_a)
        self.kb_a = self.profile_a.default_kb
        self.doc = Document.objects.create(
            knowledge_base=self.kb_a,
            title="Shared roadmap",
            content="# Body",
            content_type="markdown",
            file_path="",
            content_hash="b" * 64,
        )

    def _add_member(self, *, role: str):
        self.client.force_authenticate(user=self.user_a)
        url = reverse("knowledge-base-members", kwargs={"pk": str(self.kb_a.pk)})
        return self.client.post(
            url,
            {"user_id": str(self.user_b.id), "role": role},
            format="json",
        )

    def test_viewer_can_list_and_get_document(self):
        r = self._add_member(role="viewer")
        self.assertIn(r.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        kb_id = str(self.kb_a.pk)
        list_url = reverse("document-list", kwargs={"knowledge_base_id": kb_id})
        self.client.force_authenticate(user=self.user_b)
        r_list = self.client.get(list_url)
        self.assertEqual(r_list.status_code, status.HTTP_200_OK)
        ids = [row.get("id") for row in (r_list.data or [])]
        self.assertIn(str(self.doc.pk), ids)
        detail_url = reverse(
            "document-detail",
            kwargs={"knowledge_base_id": kb_id, "pk": str(self.doc.pk)},
        )
        r_detail = self.client.get(detail_url)
        self.assertEqual(r_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(r_detail.data.get("title"), "Shared roadmap")

    def test_viewer_cannot_put_delete_or_post_document(self):
        self._add_member(role="viewer")
        kb_id = str(self.kb_a.pk)
        doc_id = str(self.doc.pk)
        detail_url = reverse(
            "document-detail",
            kwargs={"knowledge_base_id": kb_id, "pk": doc_id},
        )
        list_url = reverse("document-list", kwargs={"knowledge_base_id": kb_id})
        self.client.force_authenticate(user=self.user_b)
        self.assertEqual(
            self.client.put(detail_url, {"title": "Hijack"}, format="json").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(self.client.delete(detail_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            self.client.post(
                list_url,
                {"title": "New", "content": "x", "content_type": "markdown"},
                format="json",
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_editor_can_put_document(self):
        self._add_member(role="editor")
        kb_id = str(self.kb_a.pk)
        detail_url = reverse(
            "document-detail",
            kwargs={"knowledge_base_id": kb_id, "pk": str(self.doc.pk)},
        )
        self.client.force_authenticate(user=self.user_b)
        r_put = self.client.put(detail_url, {"title": "Updated by B"}, format="json")
        self.assertEqual(r_put.status_code, status.HTTP_200_OK)
        self.assertEqual(r_put.data.get("title"), "Updated by B")
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.title, "Updated by B")

    def test_non_member_cannot_access_after_member_removed(self):
        self._add_member(role="viewer")
        self.client.force_authenticate(user=self.user_a)
        del_url = reverse(
            "knowledge-base-member-detail",
            kwargs={"pk": str(self.kb_a.pk), "user_id": str(self.user_b.id)},
        )
        r_del = self.client.delete(del_url)
        self.assertEqual(r_del.status_code, status.HTTP_200_OK)
        self.assertFalse(
            KnowledgeBaseMember.objects.filter(
                knowledge_base=self.kb_a, user=self.user_b
            ).exists()
        )
        list_url = reverse("document-list", kwargs={"knowledge_base_id": str(self.kb_a.pk)})
        self.client.force_authenticate(user=self.user_b)
        self.assertEqual(self.client.get(list_url).status_code, status.HTTP_404_NOT_FOUND)
