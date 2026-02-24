"""
URL configuration for POS Reports.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.reports_dashboard, name='reports_dashboard'),
]
