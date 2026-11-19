from django.db import migrations

from accounts.usernames import assign_default_usernames


def forwards(apps, schema_editor):
    user_model = apps.get_model("auth", "User")
    assign_default_usernames(user_model)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
