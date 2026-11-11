from django.contrib import admin

from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ['sender', 'body', 'created_at', 'read_at']
    can_delete = False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    """For moderating reported conversations; messages are read-only here."""
    list_display = ['ad', 'buyer', 'seller', 'last_message_at']
    readonly_fields = ['ad', 'buyer', 'seller', 'created_at', 'last_message_at']
    inlines = [MessageInline]
    search_fields = ['ad__title', 'buyer__username', 'seller__username']
