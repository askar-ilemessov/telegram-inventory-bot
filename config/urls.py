"""
URL configuration for Inventory POS Bot project.
"""
from django.contrib import admin
from django.urls import path
from django.shortcuts import render

def landing_page(request):
    """Landing page with link to admin."""
    return render(request, 'landing.html')

urlpatterns = [
    path('', landing_page, name='landing'),
    path('admin/', admin.site.urls),
]

# Admin site customization
admin.site.site_header = "Inventory POS Bot Administration"
admin.site.site_title = "Inventory POS Bot Admin"
admin.site.index_title = "Welcome to Inventory POS Bot Admin Panel"

