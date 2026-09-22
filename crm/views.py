from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .messaging import deliver_message
from .models import Conversation, Lead, Message, PipelineStage
from .zernio import ZernioError


def _conversations_qs():
    return Conversation.objects.select_related("lead").order_by("-last_message_at")


@login_required
def dashboard(request):
    stages = PipelineStage.objects.filter(is_active=True).annotate(
        lead_count=Count("leads")
    )
    max_stage_count = max((s.lead_count for s in stages), default=0)

    total_leads = Lead.objects.count()
    since_week = timezone.now() - timezone.timedelta(days=7)
    new_this_week = Lead.objects.filter(created_at__gte=since_week).count()

    closed_won = Lead.objects.filter(pipeline_stage__name="Cerrado").count()
    closed_lost = Lead.objects.filter(pipeline_stage__name="Perdido").count()
    decided = closed_won + closed_lost
    conversion_rate = round(closed_won / decided * 100) if decided else None

    ai_messages_count = Message.objects.filter(ai_generated=True).count()

    recent_leads = Lead.objects.select_related("pipeline_stage").order_by(
        "-created_at"
    )[:6]
    recent_messages = Message.objects.select_related(
        "conversation", "conversation__lead"
    ).order_by("-created_at")[:8]

    return render(
        request,
        "crm/dashboard.html",
        {
            "stages": stages,
            "max_stage_count": max_stage_count,
            "total_leads": total_leads,
            "new_this_week": new_this_week,
            "closed_won": closed_won,
            "closed_lost": closed_lost,
            "conversion_rate": conversion_rate,
            "ai_messages_count": ai_messages_count,
            "recent_leads": recent_leads,
            "recent_messages": recent_messages,
        },
    )


@login_required
def contacts_list(request):
    query = request.GET.get("q", "").strip()
    stage_id = request.GET.get("stage", "")
    stages = PipelineStage.objects.filter(is_active=True)
    leads = Lead.objects.select_related("pipeline_stage").prefetch_related(
        "conversations"
    ).order_by("-created_at", "-pk")

    if query:
        leads = leads.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(phone__icontains=query)
            | Q(email__icontains=query)
        )
    selected_stage = int(stage_id) if stage_id.isdigit() else None
    if selected_stage is not None:
        leads = leads.filter(pipeline_stage_id=selected_stage)

    page_obj = Paginator(leads, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "crm/contacts.html",
        {
            "page_obj": page_obj,
            "query": query,
            "stages": stages,
            "selected_stage": selected_stage,
            "selected_stage_param": stage_id if selected_stage is not None else "",
        },
    )


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
