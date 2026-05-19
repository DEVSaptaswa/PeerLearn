"""apps/accounts/urls.py"""
from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("register/",               views.register_view,        name="register"),
    path("login/",                  views.login_view,           name="login"),
    path("logout/",                 views.logout_view,          name="logout"),
    path("profile/",                views.profile_view,         name="profile"),
    path("profile/edit/",           views.edit_profile_view,    name="edit_profile"),
    path("profile/<str:username>/", views.profile_view,         name="user_profile"),
    # Friendship
    path("friend/request/<int:user_id>/",       views.send_friend_request,   name="friend_request"),
    path("friend/respond/<int:friendship_id>/", views.respond_friend_request, name="friend_respond"),
    # Status
    path("status/set/", views.set_status_view, name="set_status"),
    # API
    path("api/friends/status/",              views.friends_status_api,  name="friends_status_api"),
    path("api/friends/requests/",            views.friend_requests_api, name="friend_requests_api"),
    path("api/users/search/",                views.search_users_api,    name="search_users_api"),
    path("api/profile-mini/<int:user_id>/",  views.profile_mini_api,    name="profile_mini_api"),
]
