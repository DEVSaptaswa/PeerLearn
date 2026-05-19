"""apps/discussions/urls.py"""
from django.urls import path
from . import views

app_name = "discussions"

urlpatterns = [
    # ── Fixed-prefix routes MUST come before slug-capture patterns ─────────────
    # Django matches top-to-bottom; <slug:channel_slug> would swallow
    # "upvote", "mod", "search" if they appeared after it.
    path("search/",  views.unified_search,          name="search"),
    path("upvote/<str:discussion_id>/", views.upvote_discussion_view, name="upvote"),
    path("mod/<slug:channel_slug>/message/<str:message_id>/delete/",
         views.mod_delete_message, name="mod_delete_message"),

    # ── Channel-scoped routes ──────────────────────────────────────────────────
    path("<slug:channel_slug>/",                             views.discussions_api,          name="api_list"),
    path("<slug:channel_slug>/create/",                      views.create_discussion_view,   name="create"),
    path("<slug:channel_slug>/<str:discussion_id>/",         views.discussion_detail,        name="detail"),
    path("<slug:channel_slug>/<str:discussion_id>/reply/",   views.post_message,             name="post_message"),
]
