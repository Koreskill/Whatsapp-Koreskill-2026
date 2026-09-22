from django.urls import path

from . import views, webhooks

urlpatterns = [
    path("webhooks/zernio/", webhooks.zernio_webhook, name="zernio-webhook"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("chat/", views.chat_list, name="chat-list"),
    path("chat/sidebar/", views.chat_sidebar, name="chat-sidebar"),
    path("chat/<int:pk>/", views.chat_detail, name="chat-detail"),
    path("chat/<int:pk>/thread/", views.chat_thread, name="chat-thread"),
    path("chat/<int:pk>/send/", views.chat_send, name="chat-send"),
    path("pipeline/", views.pipeline_board, name="pipeline-board"),
    path(
        "pipeline/leads/<int:pk>/move/",
        views.pipeline_move_lead,
        name="pipeline-move-lead",
    ),
]
