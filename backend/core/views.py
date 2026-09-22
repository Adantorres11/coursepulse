from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def health(request):
    """Liveness check used by Docker, CI, and the first end-to-end smoke test."""
    return Response({"status": "ok", "service": "coursepulse-api"})
