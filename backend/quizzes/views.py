from django.db.models import Count
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny

from .models import Lecture
from .serializers import LectureSerializer, QuizSerializer


class LectureListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = LectureSerializer
    pagination_class = None

    def get_queryset(self):
        return (
            Lecture.objects
            .select_related("classroom")
            .filter(published_at__lte=timezone.now())
            .annotate(question_count=Count("questions"))
            .filter(question_count__gt=0)
            .order_by("-published_at", "-id")
        )


class LectureQuizView(RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = QuizSerializer

    def get_queryset(self):
        return (
            Lecture.objects
            .filter(published_at__lte=timezone.now())
            .annotate(question_count=Count("questions"))
            .filter(question_count__gt=0)
            .prefetch_related("questions")
        )

    def get_object(self):
        try:
            return super().get_object()
        except Http404:
            raise NotFound()
