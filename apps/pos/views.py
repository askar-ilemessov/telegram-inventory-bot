"""
POS Reports Web Views.
"""
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.inventory.models import Product
from .models import Shift
from .services import ReportService


@login_required
def reports_dashboard(request):
    """Full reports dashboard — mirrors all bot reports on one page."""
    if not request.user.is_staff:
        messages.error(request, "У вас нет доступа к этой странице")
        return redirect('landing')

    staff_profile = getattr(request.user, 'staff_profile', None)
    if not staff_profile or not staff_profile.location:
        messages.error(request, "У вас не назначена локация")
        return redirect('landing')

    location = staff_profile.location

    # Last 50 shifts for this location, newest first
    all_shifts = (
        Shift.objects
        .filter(location=location)
        .select_related('staff')
        .order_by('-started_at')[:50]
    )

    # Resolve which shift to show (query param or auto-select)
    shift_id = request.GET.get('shift_id')
    if shift_id:
        selected_shift = get_object_or_404(Shift, id=shift_id, location=location)
    else:
        # Prefer open shift; fall back to most recent closed
        selected_shift = (
            Shift.objects.filter(location=location, is_closed=False).first()
            or all_shifts.first()
        )

    # Build shift-specific report data
    summary = None
    sales_details = []
    refunds_details = []

    if selected_shift:
        summary = ReportService.get_shift_summary(selected_shift)
        sales_details = ReportService.get_sales_details(selected_shift)
        refunds_details = ReportService.get_refunds_details(selected_shift)

    # Inventory — location-wide, not shift-specific
    products = (
        Product.objects
        .filter(location=location, is_active=True)
        .select_related('category', 'storage_stock', 'display_stock')
        .order_by('category__name', 'name')
    )

    inventory = []
    for product in products:
        storage = getattr(product, 'storage_stock', None)
        display = getattr(product, 'display_stock', None)
        storage_qty = storage.quantity if storage else Decimal('0.00')
        display_qty = display.quantity if display else Decimal('0.00')
        inventory.append({
            'category': product.category.name,
            'name': product.name,
            'unit': product.unit,
            'price': product.price,
            'storage': storage_qty,
            'display': display_qty,
            'total': storage_qty + display_qty,
        })

    context = {
        'location': location,
        'staff_profile': staff_profile,
        'all_shifts': all_shifts,
        'selected_shift': selected_shift,
        'summary': summary,
        'sales_details': sales_details,
        'refunds_details': refunds_details,
        'inventory': inventory,
    }

    return render(request, 'reports/dashboard.html', context)
