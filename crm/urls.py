from django.urls import path

from . import webhooks

urlpatterns = [
    path("webhooks/zernio/", webhooks.zernio_webhook, name="zernio-webhook"),
]
