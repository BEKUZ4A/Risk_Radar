from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.risks.services import RiskEngineService
from apps.users.permissions import IsBusinessOwner
from apps.users.models import UserActivityLog


class AIGuardrailPromptAPIView(APIView):
    """
    Local Ollama uchun qat'iy system_prompt + JSON kontekst.
    Backend LLM chaqirmaydi — faqat guardrail beradi. OWNER only.
    """

    permission_classes = [IsBusinessOwner]

    @extend_schema(
        summary='Frontend Local AI uchun Guardrail Prompt va Context',
        responses={200: dict},
    )
    def get(self, request):
        unified_json = RiskEngineService.generate_unified_dashboard_json()

        system_prompt = (
            "You are a business risk assistant for the Business Owner dashboard.\n"
            "Answer ONLY using the provided JSON context.\n"
            "RULES:\n"
            "1. Respond only about business performance, risk scores, stock alerts, "
            "and financial metrics found in the JSON.\n"
            "2. If a question is out of domain, reply exactly: "
            "'Sorry, I can only answer using the provided system JSON context.'\n"
            "3. Do not invent numbers that are not in the JSON.\n"
            "4. Be concise and factual.\n\n"
            f"CURRENT JSON CONTEXT:\n{unified_json}"
        )

        UserActivityLog.objects.create(
            user=request.user,
            action_name='AI_GUARDRAIL_PROMPT',
            ip_address=request.META.get('REMOTE_ADDR'),
            request_data={},
        )

        return Response(
            {
                'system_prompt': system_prompt,
                'context_json': unified_json,
            },
            status=status.HTTP_200_OK,
        )
