from django.utils.functional import SimpleLazyObject

from .models import unread_count


def unread_messages(request):
    """`unread_messages` for the header badge; counted only if a template uses it."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {}
    return {'unread_messages': SimpleLazyObject(lambda: unread_count(user))}
