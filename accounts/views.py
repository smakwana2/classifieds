from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.forms.utils import ErrorDict
from django.shortcuts import redirect, render

from ads import ratelimit
from ads.ratelimit import client_ip

from .forms import DeleteAccountForm, SignUpForm

# Failed password attempts allowed per 15 minutes, by client IP and by username.
LOGIN_WINDOW = 15 * 60
LOGIN_FAILURES_PER_IP = 20
LOGIN_FAILURES_PER_USERNAME = 10
DELETE_FAILURES_PER_USER = 5
SIGNUPS_PER_IP_PER_HOUR = 5
TOO_MANY_ATTEMPTS = 'Too many failed attempts. Please wait 15 minutes and try again.'


class ThrottledLoginView(LoginView):
    """Django's login view, refusing to check passwords after too many failures."""

    def _idents(self):
        username = self.request.POST.get('username', '').strip().lower()
        return [('login-ip', client_ip(self.request), LOGIN_FAILURES_PER_IP),
                ('login-user', username, LOGIN_FAILURES_PER_USERNAME)]

    def post(self, request, *args, **kwargs):
        if any(ratelimit.count(scope, ident, LOGIN_WINDOW) >= limit for scope, ident, limit in self._idents()):
            # Mark the form as already checked, with one error, so the password is never tested.
            form = self.get_form()
            form._errors, form.cleaned_data = ErrorDict(), {}
            form.add_error(None, TOO_MANY_ATTEMPTS)
            return self.render_to_response(self.get_context_data(form=form), status=429)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        for scope, ident, _ in self._idents():
            ratelimit.hit(scope, ident, LOGIN_WINDOW)
        return super().form_invalid(form)


def signup(request):
    if request.user.is_authenticated:
        return redirect('ads:list')
    form = SignUpForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        ip = client_ip(request)
        if ratelimit.count('signup', ip, 3600) >= SIGNUPS_PER_IP_PER_HOUR:
            form.add_error(None, 'Too many accounts have been created from your network recently. '
                                 'Please try again later.')
        else:
            user = form.save()
            ratelimit.hit('signup', ip, 3600)
            login(request, user)
            messages.success(request, f'Welcome, {user.username}! Your account has been created.')
            return redirect('ads:list')
    return render(request, 'registration/signup.html', {'form': form})


@login_required
def delete_account(request):
    form = DeleteAccountForm(request.user, request.POST or None)
    if request.method == 'POST':
        if ratelimit.count('delete-account', request.user.pk, LOGIN_WINDOW) >= DELETE_FAILURES_PER_USER:
            form.is_valid()
            form.add_error(None, TOO_MANY_ATTEMPTS)
        elif form.is_valid():
            user = request.user
            logout(request)
            user.delete()
            messages.success(request, 'Your account and all of your ads have been deleted.')
            return redirect('ads:list')
        else:
            ratelimit.hit('delete-account', request.user.pk, LOGIN_WINDOW)
    return render(request, 'registration/delete_account.html', {'form': form})
