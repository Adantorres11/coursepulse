import secrets
import string

from django.db import migrations


def populate_access_codes(apps, schema_editor):
    Classroom = apps.get_model("classrooms", "Classroom")
    database = schema_editor.connection.alias
    classrooms = Classroom.objects.using(database)
    alphabet = string.ascii_uppercase + string.digits

    for classroom in classrooms.filter(access_code__isnull=True).iterator():
        while True:
            code = "".join(secrets.choice(alphabet) for _ in range(6))

            if not classrooms.filter(access_code__iexact=code).exists():
                break

        classroom.access_code = code
        classroom.save(using=database, update_fields=["access_code"])


class Migration(migrations.Migration):
    dependencies = [
        ("classrooms", "0003_classroom_access_code"),
    ]

    operations = [
        migrations.RunPython(
            populate_access_codes,
            reverse_code=migrations.RunPython.noop,
        ),
    ]