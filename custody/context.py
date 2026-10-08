from .utils import user_can_write


def permissions(request):
    return {"can_write": user_can_write(request.user)}
