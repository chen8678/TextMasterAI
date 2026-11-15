from django.urls import path
from . import views

urlpatterns = [
    path('content-generation/run/', views.run_content_generation, name='workflow-content-generation-run'),
    path('content-generation/<uuid:knowledge_base_id>/content/', views.get_generated_content, name='workflow-content-generation-content'),
    path('kb-qa-collector/run/', views.run_kb_qa_collector, name='workflow-kb-qa-collector-run'),
    path('kb-qa-collector/personas/', views.kb_qa_collector_personas, name='workflow-kb-qa-collector-personas'),
    path('ai-models/', views.ai_models, name='workflow-ai-models'),
]
