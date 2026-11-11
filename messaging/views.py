from django.contrib import messages as flash
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, OuterRef, Q, Subquery
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ads import ratelimit
from ads.models import Ad

from .forms import MessageForm
from .models import Conversation, Message

# Sending limits per user: messages per hour and per day, and new conversations per day.
MESSAGES_PER_HOUR = 30
MESSAGES_PER_DAY = 200
NEW_CONVERSATIONS_PER_DAY = 20
HOUR, DAY = 60 * 60, 60 * 60 * 24
INBOX_PAGE_SIZE = 20


def _sending_limit_error(user, new_conversation=False):
    if new_conversation and ratelimit.count('new-conversation', user.pk, DAY) >= NEW_CONVERSATIONS_PER_DAY:
        return 'You’ve contacted a lot of sellers today. Please try again tomorrow.'
    if (ratelimit.count('message', user.pk, HOUR) >= MESSAGES_PER_HOUR
            or ratelimit.count('message-day', user.pk, DAY) >= MESSAGES_PER_DAY):
        return 'You’re sending messages too quickly. Please wait a while and try again.'
    return None


def _count_sent(user, new_conversation=False):
    ratelimit.hit('message', user.pk, HOUR)
    ratelimit.hit('message-day', user.pk, DAY)
    if new_conversation:
        ratelimit.hit('new-conversation', user.pk, DAY)


@login_required
@require_POST
@transaction.atomic
def start(request, ad_pk):
    """Send the first message about an ad (or add to the buyer's existing conversation)."""
    ad = get_object_or_404(Ad.objects.select_related('owner'), pk=ad_pk)
    if ad.owner_id == request.user.pk:
        raise Http404  # sellers don't message themselves
    conversation = Conversation.objects.filter(ad=ad, buyer=request.user).first()
    form = MessageForm(request.POST)
    error = None if not form.is_valid() else _sending_limit_error(request.user, conversation is None)
    if not form.is_valid() or error:
        flash.error(request, error or form.errors['body'][0])
        return redirect(f'{ad.get_absolute_url()}#contact')
    if conversation is None:
        conversation = Conversation.objects.create(ad=ad, buyer=request.user, seller=ad.owner)
        _count_sent(request.user, new_conversation=True)
    else:
        _count_sent(request.user)
    conversation.add_message(request.user, form.cleaned_data['body'])
    flash.success(request, f'Message sent to {ad.owner.username}.')
    return redirect(conversation)


@login_required
def inbox(request):
    user = request.user
    last = Message.objects.filter(conversation=OuterRef('pk')).order_by('-created_at', '-pk')
    conversations = (
        Conversation.objects.for_user(user)
        .select_related('ad', 'buyer', 'seller')
        .prefetch_related('ad__images')
        .annotate(
            unread=Count('messages', filter=Q(messages__read_at=None) & ~Q(messages__sender=user)),
            last_body=Subquery(last.values('body')[:1]),
            last_sender_id=Subquery(last.values('sender_id')[:1]),
        )
    )
    page = Paginator(conversations, INBOX_PAGE_SIZE).get_page(request.GET.get('page'))
    for conversation in page.object_list:
        conversation.other = conversation.other_party(user)
    return render(request, 'messaging/inbox.html', {'page': page})


@login_required
def conversation(request, pk):
    conversation = get_object_or_404(Conversation.objects.select_related('ad', 'buyer', 'seller'), pk=pk)
    if not conversation.has_participant(request.user):
        raise Http404  # don't reveal that the conversation exists
    form = MessageForm(request.POST or None)
    if request.method == 'POST':
        error = _sending_limit_error(request.user) if form.is_valid() else None
        if error:
            form.add_error('body', error)
        elif form.is_valid():
            with transaction.atomic():
                _count_sent(request.user)
                conversation.add_message(request.user, form.cleaned_data['body'])
            return redirect(f'{conversation.get_absolute_url()}#latest')
    conversation.mark_read_by(request.user)
    return render(request, 'messaging/conversation.html', {
        'conversation': conversation,
        'thread': conversation.messages.select_related('sender'),
        'other': conversation.other_party(request.user),
        'form': form,
    })
