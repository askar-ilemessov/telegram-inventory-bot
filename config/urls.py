"""
URL configuration for Inventory POS Bot project.
"""
from django.contrib import admin
from django.urls import path
from django.http import JsonResponse

def health_check(request):
    """Health check endpoint for Railway."""
    return JsonResponse({'status': 'ok'})

urlpatterns = [
    path('', health_check, name='health_check'),
    path('admin/', admin.site.urls),
]

# Admin site customization
admin.site.site_header = "Inventory POS Bot Administration"
admin.site.site_title = "Inventory POS Bot Admin"
admin.site.index_title = "Welcome to Inventory POS Bot Admin Panel"

