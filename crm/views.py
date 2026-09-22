from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render

from .messaging import deliver_message
from .models import Conversation, Lead, PipelineStage
from .zernio import ZernioError


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
def chat_thread(request, pk):
    conversation = get_object_or_404(Conversation, pk=pk)
    return render(
        request, "crm/_messages.html", {"thread": conversation.messages.all()}
    )


@login_required
def chat_sidebar(request):
    active_pk = request.GET.get("active")
    conversation = Conversation.objects.filter(pk=active_pk).first() if active_pk else None
    return render(
        request,
        "crm/_conversations.html",
        {"conversations": _conversations_qs(), "conversation": conversation},
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
            deliver_message(conversation, text)
        except ZernioError as exc:
            send_error = str(exc)

    return render(
        request,
        "crm/_messages.html",
        {"thread": conversation.messages.all(), "send_error": send_error},
    )


@login_required
def pipeline_board(request):
    stages = PipelineStage.objects.filter(is_active=True).prefetch_related("leads")
    return render(request, "crm/pipeline.html", {"stages": stages})


@login_required
def pipeline_move_lead(request, pk):
    if request.method != "POST":
        return HttpResponseBadRequest()
    lead = get_object_or_404(Lead, pk=pk)
    stage = get_object_or_404(PipelineStage, pk=request.POST.get("stage_id"))
    lead.pipeline_stage = stage
    lead.save(update_fields=["pipeline_stage"])
    return HttpResponse(status=204)
