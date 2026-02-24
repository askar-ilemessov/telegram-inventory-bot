"""
Views for Inventory web interface.
"""
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from .models import Product, StorageStock, DisplayStock, Category, PurchaseTransaction, TransferTransaction
from .services import InventoryService


@login_required
def inventory_dashboard(request):
    """Main inventory dashboard."""
    if not request.user.is_staff:
        messages.error(request, "У вас нет доступа к этой странице")
        return redirect('landing')
    
    # Get user's location
    staff_profile = getattr(request.user, 'staff_profile', None)
    if not staff_profile or not staff_profile.location:
        messages.error(request, "У вас не назначена локация")
        return redirect('landing')
    
    location = staff_profile.location
    
    # Get all products with stock info
    products = Product.objects.filter(
        location=location,
        is_active=True
    ).select_related('category', 'storage_stock', 'display_stock').order_by('category__name', 'name')
    
    context = {
        'location': location,
        'products': products,
        'staff_profile': staff_profile,
    }
    
    return render(request, 'inventory/dashboard.html', context)


@login_required
def purchase_product(request, product_id):
    """Purchase product (add to storage)."""
    if not request.user.is_staff:
        messages.error(request, "У вас нет доступа")
        return redirect('landing')
    
    staff_profile = getattr(request.user, 'staff_profile', None)
    if not staff_profile or staff_profile.role not in ['ADMIN', 'MANAGER']:
        messages.error(request, "Только менеджеры и админы могут делать закупки")
        return redirect('inventory_dashboard')
    
    product = get_object_or_404(Product, id=product_id, location=staff_profile.location)
    
    if request.method == 'POST':
        try:
            quantity = Decimal(request.POST.get('quantity', '0'))
            purchase_price = Decimal(request.POST.get('purchase_price', '0'))
            supplier = request.POST.get('supplier', '').strip() or None
            
            if quantity <= 0:
                raise ValueError("Количество должно быть больше 0")
            if purchase_price < 0:
                raise ValueError("Цена не может быть отрицательной")
            
            # Create purchase transaction
            InventoryService.purchase(
                product=product,
                location=staff_profile.location,
                quantity=quantity,
                purchase_price=purchase_price,
                created_by=request.user,
                supplier=supplier
            )
            
            messages.success(
                request,
                f"✅ Закупка оформлена: {product.name} ({quantity} {product.unit}) на сумму {quantity * purchase_price}₸"
            )
            return redirect('inventory_dashboard')
            
        except Exception as e:
            messages.error(request, f"❌ Ошибка: {str(e)}")
    
    context = {
        'product': product,
        'staff_profile': staff_profile,
    }
    
    return render(request, 'inventory/purchase.html', context)


@login_required
def transfer_to_display(request, product_id):
    """Transfer product from storage to display."""
    if not request.user.is_staff:
        messages.error(request, "У вас нет доступа")
        return redirect('landing')
    
    staff_profile = getattr(request.user, 'staff_profile', None)
    if not staff_profile or staff_profile.role not in ['ADMIN', 'MANAGER']:
        messages.error(request, "Только менеджеры и админы могут перемещать товары")
        return redirect('inventory_dashboard')
    
    product = get_object_or_404(Product, id=product_id, location=staff_profile.location)
    storage = get_object_or_404(StorageStock, product=product, location=staff_profile.location)
    
    if request.method == 'POST':
        try:
            quantity = Decimal(request.POST.get('quantity', '0'))
            
            if quantity <= 0:
                raise ValueError("Количество должно быть больше 0")
            
            if quantity > storage.quantity:
                raise ValueError(f"Недостаточно товара на складе (доступно: {storage.quantity})")
            
            # Transfer to display
            InventoryService.transfer(
                product=product,
                location=staff_profile.location,
                quantity=quantity,
                created_by=request.user
            )
            
            messages.success(
                request,
                f"✅ Перемещено на витрину: {product.name} ({quantity} {product.unit})"
            )
            return redirect('inventory_dashboard')
            
        except Exception as e:
            messages.error(request, f"❌ Ошибка: {str(e)}")
    
    context = {
        'product': product,
        'storage': storage,
        'staff_profile': staff_profile,
    }
    
    return render(request, 'inventory/transfer.html', context)