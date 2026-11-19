"""Public usernames.

Import this helper anywhere a screen names a person:

    from accounts.usernames import display_username

display_username(user) is the account username. It never returns an email.
The same value is the username field on auth responses, and the name and
username fields on professors, roster rows, result rows, and leaderboard rows.
"""

import re

USERNAME_MAX_LENGTH = 150
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+\Z")
BLANK_USERNAME_MESSAGE = "Enter a username."
TAKEN_USERNAME_MESSAGE = "That username is already taken."
INVALID_USERNAME_MESSAGE = (
    "Use letters, numbers, underscores, or hyphens."
)

_UNSAFE = re.compile(r"[^A-Za-z0-9_-]")


def display_username(user):
    """The name to show for this person. Never an email address."""
    if user is None:
        return ""
    return username_for_display(getattr(user, "username", "") or "")


def username_for_display(username):
    username = (username or "").strip()
    if "@" not in username:
        return username
    return username_from_legacy_email(username)


def username_from_legacy_email(value):
    """A sensible username from an email address.

    Uses the part before @, keeps letters, numbers, underscores, and
    hyphens, and falls back to "user" when nothing usable remains.
    """
    local = (value or "").split("@", 1)[0]
    cleaned = _UNSAFE.sub("", local).strip("-_")
    if not cleaned:
        return "user"
    return cleaned[:USERNAME_MAX_LENGTH]


def assign_default_usernames(user_model):
    """Give each email-as-username account a unique username.

    Accounts that already have a real username are left alone. The local
    part of the email is used. A later account gets _2, _3, and so on
    when that name is already taken. Email addresses are not changed.
    """
    users = list(user_model.objects.all().order_by("id"))
    taken = {user.username.lower() for user in users}

    for user in users:
        if "@" not in (user.username or ""):
            continue

        taken.discard(user.username.lower())
        source = user.email if "@" in (user.email or "") else user.username
        candidate = unique_username(username_from_legacy_email(source), taken)
        taken.add(candidate.lower())

        if candidate != user.username:
            user.username = candidate
            user.save(update_fields=["username"])


def unique_username(base, taken):
    candidate = base[:USERNAME_MAX_LENGTH]
    if candidate.lower() not in taken:
        return candidate

    number = 2
    while True:
        suffix = f"_{number}"
        trimmed = base[: USERNAME_MAX_LENGTH - len(suffix)]
        candidate = f"{trimmed}{suffix}"
        if candidate.lower() not in taken:
            return candidate
        number += 1
