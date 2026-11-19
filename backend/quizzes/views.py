from rest_framework import status
from kombu.exceptions import OperationalError
from redis.exceptions import RedisError
from .pipeline import enqueue_lecture_processing
from django.shortcuts import get_object_or_404
from django.db.models import Count
from django.http import Http404
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .grading import AlreadyAnswered, NotStarted, start_question, submit_answer
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


class LectureQuestionStartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, question_id):
        try:
            lecture = available_lectures().get(pk=pk)
            question = lecture.questions.get(pk=question_id)
        except (Lecture.DoesNotExist, Question.DoesNotExist):
            raise NotFound()
        check_can_answer(request.user, lecture)
        try:
            start, created = start_question(request.user, lecture, question)
        except AlreadyAnswered:
            return Response(
                {"detail": "This question was already answered in this attempt."},
                status=400,
            )
        return Response(
            {"question_id": question.id, "started_at": start.started_at},
            status=201 if created else 200,
        )


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
            )
        except NotStarted:
            return Response(
                {"detail": "Start this question before answering."},
                status=400,
            )
        except AlreadyAnswered:
            return Response(
                {"detail": "This question was already answered in this attempt."},
                status=400,
            )
        return Response(result, status=201)


class LectureStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        lecture = get_object_or_404(
            Lecture.objects.select_related("classroom"),
            pk=pk,
        )

        profile = getattr(request.user, "profile", None)

        if (
            profile is None
            or profile.role != "professor"
            or lecture.classroom.professor_id != request.user.id
        ):
            raise PermissionDenied(
                "Only the class owner can access lecture status."
            )

        return Response({
            "id": lecture.id,
            "status": lecture.status,
            "error_message": (
                lecture.error_message
                if lecture.status == "failed"
                else ""
            ),
            "progress_message": (
                lecture.progress_message
                if lecture.status == "processing"
                else ""
            ),
            "notice": (
                lecture.notice
                if lecture.status == "ready"
                else ""
            ),
        })


class LectureRetryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        lecture = get_object_or_404(
            Lecture.objects.select_related("classroom"),
            pk=pk,
        )

        profile = getattr(request.user, "profile", None)

        if (
            profile is None
            or profile.role != "professor"
            or lecture.classroom.professor_id != request.user.id
        ):
            raise PermissionDenied(
                "Only the class owner can retry this lecture."
            )

        if lecture.status != "failed":
            return Response(
                {"detail": "Only failed lectures can be retried."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated = Lecture.objects.filter(
            pk=lecture.pk,
            status="failed",
        ).update(
            status="pending",
            error_message="",
            notice="",
            last_progress_at=timezone.now(),
        )

        if not updated:
            return Response(
                {"detail": "Lecture is already being retried."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            enqueue_lecture_processing(lecture.id)
        except (ImportError, OperationalError, RedisError):
            Lecture.objects.filter(
                pk=lecture.pk,
                status="pending",
            ).update(
                status="failed",
                error_message=lecture.error_message,
            )

            return Response(
                {"detail": "Processing is currently unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "id": lecture.id,
                "status": "pending",
                "error_message": "",
            },
            status=status.HTTP_202_ACCEPTED,
        )
