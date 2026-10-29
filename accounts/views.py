from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import DeleteAccountForm, SignUpForm


def signup(request):
    if request.user.is_authenticated:
        return redirect('ads:list')
    form = SignUpForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f'Welcome, {user.username}! Your account has been created.')
        return redirect('ads:list')
    return render(request, 'registration/signup.html', {'form': form})


@login_required
def delete_account(request):
    form = DeleteAccountForm(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = request.user
        logout(request)
        user.delete()
        messages.success(request, 'Your account and all of your ads have been deleted.')
        return redirect('ads:list')
    return render(request, 'registration/delete_account.html', {'form': form})
