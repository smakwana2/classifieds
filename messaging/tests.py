from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from ads.models import Ad, Category

from .models import Conversation, Message, unread_count


class MessagingTests(TestCase):
    def setUp(self):
        cache.clear()  # rate-limit counters live in the cache
        self.seller = User.objects.create_user('sam', password='pw-12345!')
        self.buyer = User.objects.create_user('bea', password='pw-12345!')
        self.outsider = User.objects.create_user('oz', password='pw-12345!')
        category = Category.objects.create(name='Furniture')
        self.ad = Ad.objects.create(owner=self.seller, title='Oak desk', description='x', category=category)

    def login(self, user):
        self.client.force_login(user)

    def send_first(self, body='Is it still available?', ad=None):
        return self.client.post(reverse('messaging:start', args=[(ad or self.ad).pk]), {'body': body})

    def test_buyer_and_seller_can_talk(self):
        self.login(self.buyer)
        response = self.send_first()
        conversation = Conversation.objects.get()
        self.assertRedirects(response, conversation.get_absolute_url())
        self.assertEqual((conversation.buyer, conversation.seller), (self.buyer, self.seller))

        # The seller sees an unread badge and the conversation in the inbox...
        self.login(self.seller)
        self.assertEqual(unread_count(self.seller), 1)
        inbox = self.client.get(reverse('messaging:inbox'))
        self.assertContains(inbox, 'aria-label="1 unread"', count=2)  # header badge and inbox row
        self.assertContains(inbox, 'Is it still available?')
        # ...and opening it marks it read.
        thread = self.client.get(conversation.get_absolute_url())
        self.assertContains(thread, 'Interested in your ad')
        self.assertEqual(unread_count(self.seller), 0)
        self.assertNotContains(self.client.get(reverse('messaging:inbox')), 'unread')

        # The seller replies; the buyer sees it and that their own message was seen.
        response = self.client.post(conversation.get_absolute_url(), {'body': 'Yes, come by Saturday.'})
        self.assertRedirects(response, f'{conversation.get_absolute_url()}#latest')
        self.login(self.buyer)
        self.assertEqual(unread_count(self.buyer), 1)
        thread = self.client.get(conversation.get_absolute_url()).content.decode()
        self.assertLess(thread.index('Is it still available?'), thread.index('Yes, come by Saturday.'))
        self.assertEqual(Message.objects.filter(read_at=None).count(), 0)

    def test_messaging_the_same_ad_again_continues_the_conversation(self):
        self.login(self.buyer)
        self.send_first('First')
        self.send_first('Second')
        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(Conversation.objects.get().messages.count(), 2)
        self.assertContains(self.client.get(self.ad.get_absolute_url()), 'Continue your conversation')

    def test_ad_page_contact_box(self):
        self.assertContains(self.client.get(self.ad.get_absolute_url()), 'Log in to message the seller')
        self.login(self.buyer)
        self.assertContains(self.client.get(self.ad.get_absolute_url()), 'Message sam')
        self.send_first()
        self.login(self.seller)
        page = self.client.get(self.ad.get_absolute_url())
        self.assertNotContains(page, 'Send message')
        self.assertContains(page, '1 conversation about this ad')

    def test_sellers_cannot_message_their_own_ad(self):
        self.login(self.seller)
        self.assertEqual(self.send_first().status_code, 404)
        self.assertFalse(Conversation.objects.exists())

    def test_login_and_post_required_to_start(self):
        response = self.send_first()
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('messaging:start', args=[self.ad.pk])}",
                             fetch_redirect_response=False)
        self.login(self.buyer)
        self.assertEqual(self.client.get(reverse('messaging:start', args=[self.ad.pk])).status_code, 405)
        self.assertFalse(Conversation.objects.exists())

    def test_outsiders_cannot_read_or_post(self):
        conversation = Conversation.objects.create(ad=self.ad, buyer=self.buyer, seller=self.seller)
        conversation.add_message(self.buyer, 'Private note')
        self.login(self.outsider)
        self.assertEqual(self.client.get(conversation.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.post(conversation.get_absolute_url(), {'body': 'hi'}).status_code, 404)
        self.assertNotContains(self.client.get(reverse('messaging:inbox')), 'Private note')
        self.assertEqual(conversation.messages.count(), 1)
        self.client.logout()
        self.assertEqual(self.client.get(conversation.get_absolute_url()).status_code, 302)  # to login

    def test_blank_and_overlong_messages_rejected(self):
        self.login(self.buyer)
        response = self.send_first('   ')
        self.assertRedirects(response, f'{self.ad.get_absolute_url()}#contact', fetch_redirect_response=False)
        self.assertFalse(Conversation.objects.exists())
        self.send_first('x' * 2001)
        self.assertFalse(Conversation.objects.exists())

    def test_message_text_is_escaped(self):
        self.login(self.buyer)
        self.send_first('<script>alert(1)</script>\nsecond line')
        page = self.client.get(Conversation.objects.get().get_absolute_url()).content.decode()
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;<br>second line', page)
        self.assertNotIn('<script>alert(1)', page)

    def test_sending_is_rate_limited(self):
        self.login(self.buyer)
        with mock.patch('messaging.views.MESSAGES_PER_HOUR', 2):
            self.send_first('one')
            self.send_first('two')
            response = self.send_first('three')
        self.assertRedirects(response, f'{self.ad.get_absolute_url()}#contact', fetch_redirect_response=False)
        self.assertEqual(Message.objects.count(), 2)

        other_ad = Ad.objects.create(owner=self.outsider, title='Lamp', description='x', category=self.ad.category)
        with mock.patch('messaging.views.NEW_CONVERSATIONS_PER_DAY', 1):
            self.send_first('hello', ad=other_ad)
        self.assertFalse(Conversation.objects.filter(ad=other_ad).exists())

    def test_reply_rate_limit_shows_an_error(self):
        conversation = Conversation.objects.create(ad=self.ad, buyer=self.buyer, seller=self.seller)
        self.login(self.seller)
        with mock.patch('messaging.views.MESSAGES_PER_HOUR', 0):
            response = self.client.post(conversation.get_absolute_url(), {'body': 'hi'})
        self.assertContains(response, 'sending messages too quickly')
        self.assertFalse(conversation.messages.exists())

    def test_deleting_the_ad_or_an_account_removes_conversations(self):
        self.login(self.buyer)
        self.send_first()
        self.ad.delete()
        self.assertFalse(Conversation.objects.exists())
        self.assertFalse(Message.objects.exists())

        ad = Ad.objects.create(owner=self.seller, title='Chair', description='x', category=self.ad.category)
        self.send_first(ad=ad)
        self.buyer.delete()
        self.assertFalse(Conversation.objects.exists())

    def test_inbox_lists_the_most_recent_conversation_first(self):
        chair = Ad.objects.create(owner=self.outsider, title='Chair', description='x', category=self.ad.category)
        self.login(self.buyer)
        self.send_first('About the desk', ad=self.ad)
        self.send_first('About the chair', ad=chair)
        desk = Conversation.objects.get(ad=self.ad)
        self.client.post(desk.get_absolute_url(), {'body': 'One more question about the desk'})
        titles = [c.ad.title for c in self.client.get(reverse('messaging:inbox')).context['page'].object_list]
        self.assertEqual(titles, ['Oak desk', 'Chair'])
        self.client.post(Conversation.objects.get(ad=chair).get_absolute_url(), {'body': 'And the chair?'})
        titles = [c.ad.title for c in self.client.get(reverse('messaging:inbox')).context['page'].object_list]
        self.assertEqual(titles, ['Chair', 'Oak desk'])

    def test_inbox_query_count_does_not_grow(self):
        def queries():
            with CaptureQueriesContext(connection) as captured:
                self.client.get(reverse('messaging:inbox'))
            return len(captured)

        def add_conversations(n, start):
            for i in range(start, start + n):
                ad = Ad.objects.create(owner=self.seller, title=f'Item {i}', description='x', category=self.ad.category)
                Conversation.objects.create(ad=ad, buyer=self.buyer, seller=self.seller).add_message(self.buyer, 'hi')

        self.login(self.seller)
        add_conversations(2, 0)
        few = queries()
        add_conversations(8, 2)
        self.assertEqual(queries(), few)
