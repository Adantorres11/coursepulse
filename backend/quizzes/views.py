from django.db.models import Count
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .grading import AlreadyAnswered, submit_answer
from .models import Lecture, Question
from .serializers import (
    AnswerRequestSerializer,
    LectureSerializer,
    QuizSerializer,
)


def available_lectures():
    return (
        Lecture.objects
        .filter(published_at__lte=timezone.now())
        .annotate(question_count=Count("questions"))
        .filter(question_count__gt=0)
    )


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
        return available_lectures().prefetch_related("questions")

    def get_object(self):
        try:
            return super().get_object()
        except Http404:
            raise NotFound()


def check_can_answer(user, lecture):
    profile = getattr(user, "profile", None)
    if profile is None or profile.role != "student":
        raise PermissionDenied("Only students can answer questions.")
    if not lecture.classroom.enrollments.filter(user=user).exists():
        raise PermissionDenied("You must be enrolled in this class.")


class LectureAnswerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            lecture = available_lectures().get(pk=pk)
        except Lecture.DoesNotExist:
            raise NotFound()
        check_can_answer(request.user, lecture)
        serializer = AnswerRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            question = lecture.questions.get(pk=data["question_id"])
        except Question.DoesNotExist:
            raise NotFound()
        try:
            result = submit_answer(
                request.user,
                lecture,
                question,
                data["chosen_index"],
                data["time_taken_ms"],
            )
        except AlreadyAnswered:
            return Response(
                {"detail": "This question was already answered in this attempt."},
                status=400,
            )
        return Response(result, status=201)
