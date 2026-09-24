from django.conf import settings
from django.contrib.auth import login
from accounts.models import User

class AutoLoginMiddleware:
    """
    Development middleware to allow seamless headless browser capture
    via ?demo_user=<username> when DEBUG=True.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.DEBUG:
            demo_user = request.GET.get('demo_user')
            if demo_user:
                user = User.objects.filter(username=demo_user).first()
                if user:
                    request.user = user
                    login(request, user)
        response = self.get_response(request)
        return response
