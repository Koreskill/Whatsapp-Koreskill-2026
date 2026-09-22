from django.urls import path

from . import views, webhooks

urlpatterns = [
    path("webhooks/zernio/", webhooks.zernio_webhook, name="zernio-webhook"),
    path("chat/", views.chat_list, name="chat-list"),
    path("chat/<int:pk>/", views.chat_detail, name="chat-detail"),
    path("chat/<int:pk>/send/", views.chat_send, name="chat-send"),
]
