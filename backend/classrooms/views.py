from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from quizzes.models import QuizCompletion

from .models import Classroom, Enrollment
from .serializers import ClassCodeSerializer, ClassroomSerializer


class StudentClassListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ClassroomSerializer
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        profile = getattr(user, "profile", None)

        if profile is None or profile.role != "student":
            raise PermissionDenied(
                "Only students can access this class list."
            )

        completed_lectures = QuizCompletion.objects.filter(
            user=user,
        ).values_list("lecture_id", flat=True)

        available_quizzes = Q(
            lectures__published_at__lte=timezone.now(),
            lectures__questions__isnull=False,
        )

        return (
            Classroom.objects
            .filter(enrollments__user=user)
            .select_related("professor")
            .annotate(
                quiz_count=Count(
                    "lectures",
                    filter=available_quizzes,
                    distinct=True,
                ),
                new_quiz_count=Count(
                    "lectures",
                    filter=(
                        available_quizzes
                        & ~Q(lectures__id__in=completed_lectures)
                    ),
                    distinct=True,
                ),
            )
            .order_by("name", "id")
        )


class ClassCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def get_classroom(self, request, data):
        profile = getattr(request.user, "profile", None)

        if profile is None or profile.role != "student":
            raise PermissionDenied(
                "Only students can look up or join classes."
            )

        serializer = ClassCodeSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        classroom = (
            Classroom.objects
            .select_related("professor")
            .filter(
                access_code__iexact=serializer.validated_data["code"]
            )
            .first()
        )

        if classroom is None:
            raise NotFound(
                "We couldn't find a class with that code"
            )

        return classroom

    def class_data(self, classroom, user):
        available = classroom.lectures.filter(
            published_at__lte=timezone.now(),
            questions__isnull=False,
        ).distinct()

        completed = QuizCompletion.objects.filter(
            user=user,
        ).values_list("lecture_id", flat=True)

        classroom.quiz_count = available.count()
        classroom.new_quiz_count = available.exclude(
            id__in=completed,
        ).count()

        return ClassroomSerializer(classroom).data


class ClassLookupView(ClassCodeView):
    def get(self, request):
        classroom = self.get_classroom(
            request,
            request.query_params,
        )

        return Response(
            self.class_data(classroom, request.user)
        )


class ClassJoinView(ClassCodeView):
    def post(self, request):
        classroom = self.get_classroom(
            request,
            request.data,
        )

        enrollment, created = Enrollment.objects.get_or_create(
            user=request.user,
            classroom=classroom,
        )

        return Response(
            self.class_data(classroom, request.user),
            status=(
                status.HTTP_201_CREATED
                if created
                else status.HTTP_200_OK
            ),
        )


class ClassLeaderboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        classroom = get_object_or_404(Classroom, pk=pk)
        profile = getattr(request.user, "profile", None)

        if profile is None or profile.role != "student":
            raise PermissionDenied(
                "Only students can access this leaderboard."
            )

        if not classroom.enrollments.filter(
            user=request.user,
        ).exists():
            raise PermissionDenied(
                "You must be enrolled in this class."
            )

        students = (
            get_user_model().objects
            .filter(
                enrollments__classroom=classroom,
                profile__role="student",
            )
            .annotate(
                points=Sum(
                    "quiz_attempts__total_points",
                    filter=Q(
                        quiz_attempts__lecture__classroom=classroom,
                        quiz_attempts__completed_at__isnull=False,
                    ),
                    default=0,
                ),
            )
            .order_by("-points", "id")
        )

        entries = []
        previous_points = None
        rank = 0

        for position, student in enumerate(students, start=1):
            if student.points != previous_points:
                rank = position

            first_name = student.first_name.strip()
            last_name = student.last_name.strip()

            if not first_name:
                display_name = "Student"
            elif last_name:
                display_name = f"{first_name} {last_name[0].upper()}."
            else:
                display_name = first_name

            entries.append({
                "rank": rank,
                "display_name": display_name,
                "points": student.points,
                "is_current_user": student.pk == request.user.pk,
            })

            previous_points = student.points

        return Response(entries)
