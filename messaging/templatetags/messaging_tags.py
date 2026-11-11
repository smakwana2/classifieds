from django import template

from ..forms import MessageForm
from ..models import Conversation

register = template.Library()


@register.inclusion_tag('messaging/_contact_seller.html', takes_context=True)
def contact_seller(context, ad):
    """The "Message the seller" box on an ad page (or, for the seller, a link to their inbox)."""
    user = context['request'].user
    info = {'ad': ad, 'user': user, 'request': context['request']}
    if user.is_authenticated:
        if user.pk == ad.owner_id:
            info['conversation_count'] = ad.conversations.count()
        else:
            info['conversation'] = Conversation.objects.filter(ad=ad, buyer=user).first()
            info['form'] = MessageForm()
    return info
