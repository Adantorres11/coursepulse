from django.core.exceptions import FieldDoesNotExist


def person_display_name(user):
    """Label for a person on professor screens.

    A dedicated username wins when the account model has one, so a username
    field can replace full names in this one function. Until then the label
    is the full name, then the login.
    """
    username = dedicated_username(user)
    if username:
        return username
    full_name = (user.get_full_name() or "").strip()
    if full_name:
        return full_name
    return user.username


def dedicated_username(user):
    """Public username, or None when that field is not on the account yet."""
    profile = getattr(user, "profile", None)
    if profile is not None and _has_field(profile, "username"):
        username = _clean(getattr(profile, "username", None))
        if username:
            return username

    for field_name in ("display_username", "public_username"):
        if _has_field(user, field_name):
            username = _clean(getattr(user, field_name, None))
            if username:
                return username

    return None


def _has_field(instance, field_name):
    meta = getattr(instance, "_meta", None)
    if meta is None:
        return False
    try:
        meta.get_field(field_name)
    except FieldDoesNotExist:
        return False
    return True


def _clean(value):
    if not isinstance(value, str):
        return ""
    return value.strip()
