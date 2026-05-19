"""apps/core/middleware.py"""
from utils.redis_client import update_presence


class UserPresenceMiddleware:
    """
    Updates Redis presence key on every authenticated request.
    Runs after AuthenticationMiddleware so request.user is populated.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            update_presence(request.user.pk)
        return self.get_response(request)
