"""
测试包 URL：登录 + 知识库 + AI 问答 +（默认）CET
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse


def root_view(request):
    return JsonResponse({
        "message": "智能知识问答平台 API（测试包）",
        "api": "/api/v1/",
        "docs": "请使用前端地址访问，例如 http://localhost:3000",
    })

urlpatterns = [
    path("", root_view),
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.auth.urls")),
    path("api/v1/knowledge/", include("apps.knowledge.urls")),
    path("api/v1/chat/", include("apps.chat.urls")),
    path("api/v1/system/", include("apps.system.urls")),
]
# P0-06：按首发 SKU 挂载可选域（默认仅 CET）
if getattr(settings, "ENABLE_CET_API", True):
    urlpatterns.append(path("api/v1/cet/", include("apps.cet.urls")))
if getattr(settings, "ENABLE_WORKFLOWS_API", False):
    urlpatterns.append(path("api/v1/workflows/", include("apps.workflows.urls")))
if getattr(settings, "ENABLE_SKILLS_API", False):
    urlpatterns.append(path("api/v1/skills/", include("apps.skills.urls")))
if getattr(settings, "ENABLE_AGENTS_API", False):
    urlpatterns.append(path("api/v1/agents/", include("apps.agents.urls")))
if getattr(settings, "ENABLE_ENGLISH_LEARNING_API", False):
    urlpatterns.append(path("api/v1/english-learning/", include("apps.english_learning.urls")))
if getattr(settings, "ENABLE_SCAR_API", False):
    urlpatterns.append(path("api/v1/scar/", include("apps.scar.urls")))

# P0-02：免登录 simple API 默认关闭；仅显式 ENABLE_SIMPLE_API=true 时挂载
if getattr(settings, "ENABLE_SIMPLE_API", False):
    urlpatterns.insert(2, path("api/v1/simple/", include("apps.simple_api.urls")))
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
