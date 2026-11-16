from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from vault.forms import SYNKAuthenticationForm, SYNKUserCreationForm

from . import keystore


def register(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = SYNKUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            keystore.unlock(request, user, form.cleaned_data['password1'])
            # simpan nama lengkap juga di profil terenkripsi
            key = keystore.get_key(request.session.session_key)
            if key is not None:
                from vault import services
                services.save_profile(user, key, {'full_name': form.cleaned_data['full_name']})
            return redirect('home')
    else:
        form = SYNKUserCreationForm()

    return render(request, 'register.html', {'form': form})


class VaultLoginView(LoginView):
    template_name = 'login.html'
    authentication_form = SYNKAuthenticationForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        ok = keystore.unlock(self.request, form.get_user(), form.cleaned_data['password'])
        if not ok:
            messages.error(self.request, 'Kunci enkripsi tidak dapat dibuka. Hubungi admin.')
        return response


@login_required
def dashboard(request):
    return redirect('home')