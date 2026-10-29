from django import forms
from django.contrib.auth.forms import UserCreationForm


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=False)

    class Meta(UserCreationForm.Meta):
        fields = ['username', 'email']


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
