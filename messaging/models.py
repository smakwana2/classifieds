"""Private conversations between a buyer and the seller of an ad.

One conversation per (ad, buyer). Only its two participants can read or post in
it. Deleting the ad or either account deletes the conversation and its messages.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from ads.models import Ad

MAX_MESSAGE_LENGTH = 2000


class ConversationQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(Q(buyer=user) | Q(seller=user))


class Conversation(models.Model):
    ad = models.ForeignKey(Ad, related_name='conversations', on_delete=models.CASCADE)
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='conversations_as_buyer',
                              on_delete=models.CASCADE)
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='conversations_as_seller',
                               on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(default=timezone.now, db_index=True)

    objects = ConversationQuerySet.as_manager()

    class Meta:
        ordering = ['-last_message_at']
        constraints = [models.UniqueConstraint(fields=['ad', 'buyer'], name='one_conversation_per_buyer_per_ad')]

    def __str__(self):
        return f'{self.buyer} ↔ {self.seller} about “{self.ad}”'

    def get_absolute_url(self):
        return reverse('messaging:conversation', args=[self.pk])

    def has_participant(self, user):
        return user.pk in (self.buyer_id, self.seller_id)

    def other_party(self, user):
        return self.seller if user.pk == self.buyer_id else self.buyer

    def add_message(self, sender, body):
        message = self.messages.create(sender=sender, body=body)
        self.last_message_at = message.created_at
        self.save(update_fields=['last_message_at'])
        return message

    def mark_read_by(self, user):
        return self.messages.filter(read_at=None).exclude(sender=user).update(read_at=timezone.now())


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, related_name='messages', on_delete=models.CASCADE)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='sent_messages', on_delete=models.CASCADE)
    body = models.TextField(max_length=MAX_MESSAGE_LENGTH)
    created_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(null=True, blank=True)  # when the other participant first saw it

    class Meta:
        ordering = ['created_at', 'pk']
        indexes = [models.Index(fields=['conversation', 'read_at'])]

    def __str__(self):
        return f'{self.sender}: {self.body[:40]}'


def unread_count(user):
    """Messages sent to `user` that they haven't opened yet."""
    return (Message.objects.filter(read_at=None)
            .filter(Q(conversation__buyer=user) | Q(conversation__seller=user))
            .exclude(sender=user).count())
