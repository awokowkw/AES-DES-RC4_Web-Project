from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import render, redirect

from . import keystore
from .forms import RegisterForm


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            keystore.unlock(request, user, form.cleaned_data['password1'])  # buat + simpan kunci
            return redirect('dashboard')
    else:
        form = RegisterForm()

    return render(request, 'register.html', {'form': form})


class VaultLoginView(LoginView):
    template_name = 'login.html'
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)  # login Django (session dibuat)
        ok = keystore.unlock(self.request, form.get_user(), form.cleaned_data['password'])
        if not ok:
            # password cocok tapi kunci tak bisa dibuka (mis. password diubah lewat admin)
            from django.contrib import messages
            messages.error(self.request, 'Kunci enkripsi tidak dapat dibuka. Hubungi admin.')
        return response


@login_required
def dashboard(request):
    return render(request, 'dashboard.html')