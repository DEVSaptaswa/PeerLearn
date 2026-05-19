"""apps/channels/urls.py"""
from django.urls import path
from . import views

app_name = "channels"

urlpatterns = [
    path("",                                    views.channel_list,           name="list"),
    path("create/",                             views.create_channel,         name="create"),
    path("api/search/",                         views.search_channels_api,    name="search_api"),
    path("<slug:slug>/",                         views.channel_detail,         name="detail"),
    path("<slug:slug>/members/",                 views.channel_members,        name="members"),
    path("<slug:slug>/join/",                    views.join_channel,           name="join"),
    path("<slug:slug>/leave/",                   views.leave_channel,          name="leave"),
    path("<slug:slug>/request-access/",          views.request_access,         name="request_access"),
    path("<slug:slug>/invite/",                  views.invite_friend,          name="invite_friend"),
    path("<slug:slug>/mod/delete-discussion/",   views.mod_delete_discussion,  name="mod_delete_discussion"),
    path("access-request/<int:request_id>/review/", views.review_access_request, name="review_access"),
]
