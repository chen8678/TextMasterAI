from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.conf import settings


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response(
        {
            "ok": True,
            "module": "scar",
            "scar_enabled": bool(getattr(settings, "SCAR_ENABLED", False)),
            "default_domain": getattr(settings, "SCAR_DEFAULT_DOMAIN", "construction"),
        }
    )
