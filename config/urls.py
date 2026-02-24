"""
URL configuration for Inventory POS Bot project.
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from django.shortcuts import redirect

def landing_page(request):
    """Redirect authenticated users to the dashboard; others to login."""
    if request.user.is_authenticated:
        return redirect('inventory_dashboard')
    return redirect('login')

urlpatterns = [
    path('', landing_page, name='landing'),
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='auth/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('inventory/', include('apps.inventory.urls')),
    path('reports/', include('apps.pos.urls')),
]

# Admin site customization
admin.site.site_header = "Inventory POS Bot Administration"
admin.site.site_title = "Inventory POS Bot Admin"
admin.site.index_title = "Welcome to Inventory POS Bot Admin Panel"

