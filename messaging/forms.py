from django import forms

from .models import MAX_MESSAGE_LENGTH


class MessageForm(forms.Form):
    body = forms.CharField(
        label='Message',
        max_length=MAX_MESSAGE_LENGTH,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Write a message…'}),
    )

    def clean_body(self):
        body = self.cleaned_data['body'].strip()
        if not body:
            raise forms.ValidationError('Write a message first.')
        return body
