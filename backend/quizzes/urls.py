from classrooms.views import LectureUnpublishView
from django.urls import path

from . import views

urlpatterns = [
    path(
        "lectures/",
        views.LectureListView.as_view(),
        name="lecture-list",
    ),
    path(
        "lectures/<int:pk>/quiz/",
        views.LectureQuizView.as_view(),
        name="lecture-quiz",
    ),
    path(
        "lectures/<int:pk>/questions/<int:question_id>/start/",
        views.LectureQuestionStartView.as_view(),
        name="lecture-question-start",
    ),
    path(
        "lectures/<int:pk>/answers/",
        views.LectureAnswerView.as_view(),
        name="lecture-answers",
    ),
    path(
    "lectures/<int:pk>/unpublish/",
    LectureUnpublishView.as_view(),
    name="lecture-unpublish",
    ),
]