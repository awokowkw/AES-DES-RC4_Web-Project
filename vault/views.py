from django.shortcuts import render
from django.contrib.auth import login as auth_login
from django.shortcuts import redirect, render

from .forms import SYNKAuthenticationForm, SYNKUserCreationForm
from .mock_data import (
    DASHBOARD_DATA,
    FILE_MANAGER_DATA,
    PROFILE_DATA,
    RECENT_DATA,
    SECURITY_COMPARISON_DATA,
)


# Tahap 2: validasi server-side, pembuatan akun, dan login.
def login_page(request):
    """Sign in an existing account using Django's authentication system."""
    form = SYNKAuthenticationForm(
        request,
        data=request.POST if request.method == 'POST' else None,
    )

    if request.method == 'POST' and form.is_valid():
        auth_login(request, form.get_user())
        return redirect('home')

    return render(request, 'login.html', {'form': form})


def register_page(request):
    """Create an account with Django's existing user model."""
    form = SYNKUserCreationForm(
        request.POST if request.method == 'POST' else None
    )

    if request.method == 'POST' and form.is_valid():
        user = form.save()
        auth_login(request, user)
        return redirect('home')

    return render(request, 'register.html', {'form': form})


# Tahap 3: dashboard dengan data preview.
def home_page(request):
    """Render the dashboard using centralized frontend preview data."""
    context = {
        **DASHBOARD_DATA,
        'active_page': 'home',
    }
    return render(request, 'dashboard.html', context)


# Tahap 4: daftar file dan folder dengan data preview.
def file_list_page(request):
    """Render the file manager with centralized preview data."""
    context = {
        **FILE_MANAGER_DATA,
        'active_nav': 'files',
        'active_page': 'home',
        'storage': DASHBOARD_DATA['storage'],
    }
    return render(request, 'files/list.html', context)


# Tahap 6: halaman profil memakai identitas akun dan data preview tambahan.
def profile_page(request):
    profile = PROFILE_DATA.copy()

    if request.user.is_authenticated:
        full_name = request.user.get_full_name().strip()
        if full_name:
            profile['full_name'] = full_name
            profile['first_name'] = request.user.first_name or full_name.split()[0]
            name_parts = full_name.split()
            profile['initials'] = ''.join(part[0] for part in name_parts[:2]).upper()
        profile['username'] = request.user.get_username()
        profile['email'] = request.user.email or profile['email']

    context = {
        'profile': profile,
        'active_page': 'profile',
        'storage': DASHBOARD_DATA['storage'],
    }
    return render(request, 'profile.html', context)


# Tahap 7: halaman Recent memakai sampel aktivitas dari satu sumber mock data.
def recent_page(request):
    context = {
        **RECENT_DATA,
        'recent_sections': [
            ('Recently opened', 'RECENTLY OPENED', 'opened', RECENT_DATA['opened']),
            ('Recently uploaded', 'RECENTLY UPLOADED', 'uploaded', RECENT_DATA['uploaded']),
            ('Recently modified', 'RECENTLY MODIFIED', 'modified', RECENT_DATA['modified']),
        ],
        'active_nav': 'recent',
        'active_page': 'recent',
        'profile': PROFILE_DATA,
        'storage': DASHBOARD_DATA['storage'],
    }
    return render(request, 'recent.html', context)


# Tahap 7: tabel perbandingan menampilkan data contoh sampai backend menyediakan hasil.
def security_page(request):
    context = {
        'comparison_results': SECURITY_COMPARISON_DATA,
        'active_nav': 'security',
        'active_page': 'security',
        'profile': PROFILE_DATA,
        'storage': DASHBOARD_DATA['storage'],
    }
    return render(request, 'security.html', context)


# Tahap 7: preferensi pada halaman Settings hanya berupa tampilan frontend.
def settings_page(request):
    context = {
        'active_page': 'settings',
        'profile': PROFILE_DATA,
        'storage': DASHBOARD_DATA['storage'],
    }
    return render(request, 'settings.html', context)
