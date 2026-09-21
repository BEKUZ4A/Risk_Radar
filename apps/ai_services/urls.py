from django.urls import path

from .views import AIGuardrailPromptAPIView

urlpatterns = [
    path('guardrail-prompt/', AIGuardrailPromptAPIView.as_view(), name='ai-guardrail-prompt'),
]
