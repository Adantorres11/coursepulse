from django.db import migrations
from django.db.models import Q


def mark_pending_lectures_without_recordings_ready(lecture_model):
    # 0006 already does this for a fresh database. A database that applied an
    # earlier copy of 0006 (before it had this step) still has lectures with no
    # recording stuck on "pending", and nothing will ever process them.
    lecture_model.objects.filter(
        Q(recording__isnull=True) | Q(recording=""),
        status="pending",
    ).update(status="ready")


def forwards(apps, schema_editor):
    mark_pending_lectures_without_recordings_ready(apps.get_model("quizzes", "Lecture"))


class Migration(migrations.Migration):

    dependencies = [
        ("quizzes", "0011_merge_20261115_1826"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
