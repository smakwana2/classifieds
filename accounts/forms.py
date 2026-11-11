import re

from django import forms
from django.contrib.auth.models import User
from django.db import transaction
from django.utils.safestring import mark_safe

from legal.policy import MINIMUM_AGE, TERMS_VERSION

from .models import TermsAcceptance
from django.contrib.auth.forms import UserCreationForm


USERNAME_PATTERN = re.compile(r'[A-Za-z0-9_.-]{3,30}')


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=False)
    accept_terms = forms.BooleanField(
        required=True,
        error_messages={'required': f'You must be {MINIMUM_AGE} or older and agree to the Terms of Use and '
                                    'Privacy Policy to create an account.'},
    )

    class Meta(UserCreationForm.Meta):
        fields = ['username', 'email']
        help_texts = {'username': '3–30 characters: letters, numbers, dots, dashes or underscores.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Django's password rules come as an HTML list; it's Django's own text, so it's
        # trusted here. Every other help text is escaped by templates/_field.html.
        self.fields['password1'].help_text = mark_safe(str(self.fields['password1'].help_text))

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            TermsAcceptance.objects.create(user=user, version=TERMS_VERSION)
        return user

    def clean_username(self):
        # Plain ASCII names compared without case, so nobody can register a look-alike
        # of an existing seller ("Alice" vs "alice", or Cyrillic "а" vs Latin "a").
        username = super().clean_username()
        if username is None:  # Django already reported an exact duplicate
            return username
        if not USERNAME_PATTERN.fullmatch(username):
            raise forms.ValidationError('Use 3–30 letters, numbers, dots, dashes or underscores.')
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('A user with that username already exists.')
        return username


class DeleteAccountForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput,
        help_text='Enter your password to confirm. This also deletes all of your ads.',
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data['password']
        if not self.user.check_password(password):
            raise forms.ValidationError('Incorrect password.')
        return password
