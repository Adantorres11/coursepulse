from django.contrib.auth import get_user_model

from accounts.models import Profile
from classrooms.models import Enrollment


def make_student(username, classroom=None, role="student"):
    user = get_user_model().objects.create_user(username=username, password="pw")
    Profile.objects.create(user=user, role=role)
    if classroom is not None:
        Enrollment.objects.create(user=user, classroom=classroom)
    return user


def answer(client, lecture, question, chosen_index):
    return client.post(
        f"/api/lectures/{lecture.id}/answers/",
        {
            "question_id": question.id,
            "chosen_index": chosen_index,
            "time_taken_ms": 4200,
        },
        format="json",
    )
