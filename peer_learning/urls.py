"""peer_learning/urls.py"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("channels/", include("apps.channels.urls")),
    path("discussions/", include("apps.discussions.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
