"""
URL configuration for Inventory app.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.inventory_dashboard, name='inventory_dashboard'),
    path('purchase/<int:product_id>/', views.purchase_product, name='purchase_product'),
    path('transfer/<int:product_id>/', views.transfer_to_display, name='transfer_to_display'),
]