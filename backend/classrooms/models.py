import secrets
import string

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models


def generate_access_code():
    alphabet = string.ascii_uppercase + string.digits

    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(6))
        if not Classroom.objects.filter(access_code__iexact=code).exists():
            return code


class Classroom(models.Model):
    name = models.CharField(max_length=255)
    course_code = models.CharField(max_length=50, blank=True)
    access_code = models.CharField(
        max_length=6,
        unique=True,
        default=generate_access_code,
        validators=[
            RegexValidator(
                regex=r"^[A-Z0-9]{6}\Z",
                message="Use exactly 6 uppercase letters or numbers.",
            ),
        ],
    )
    professor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="taught_classrooms",
    )

    def __str__(self):
        return self.name


class Enrollment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "classroom"],
                name="unique_user_classroom_enrollment",
            ),
        ]

    def __str__(self):
        return f"{self.user_id} enrolled in {self.classroom.name}"