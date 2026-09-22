from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Conversation, Message
from .zernio import ZernioError, send_message as send_zernio_message


def _conversations_qs():
    return Conversation.objects.select_related("lead").order_by("-last_message_at")


@login_required
def chat_list(request):
    return render(
        request,
        "crm/chat_list.html",
        {"conversations": _conversations_qs(), "conversation": None},
    )


@login_required
def chat_detail(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk)
    return render(
        request,
        "crm/chat_detail.html",
        {
            "conversation": conversation,
            "conversations": _conversations_qs(),
            "thread": conversation.messages.all(),
        },
    )


@login_required
def chat_send(request, pk):
    if request.method != "POST":
        return HttpResponseBadRequest()

    conversation = get_object_or_404(Conversation, pk=pk)
    text = request.POST.get("text", "").strip()
    send_error = None

    if text:
        try:
            message_id = send_zernio_message(
                conversation_id=conversation.zernio_conversation_id,
                account_id=conversation.zernio_account_id,
                text=text,
            )
        except ZernioError as exc:
            send_error = str(exc)
        else:
            Message.objects.create(
                conversation=conversation,
                zernio_message_id=message_id or None,
                direction=Message.Direction.OUT,
                text=text,
                sent_at=timezone.now(),
            )
            conversation.last_message_at = timezone.now()
            conversation.save(update_fields=["last_message_at"])

    return render(
        request,
        "crm/_messages.html",
        {"thread": conversation.messages.all(), "send_error": send_error},
    )
