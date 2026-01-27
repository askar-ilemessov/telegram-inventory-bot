"""
Admin configuration for POS app.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Shift, Transaction, Payment, StockCount


class TransactionInline(admin.TabularInline):
    """Inline for transactions in shift admin."""
    model = Transaction
    extra = 0
    can_delete = False
    readonly_fields = ('product', 'transaction_type', 'qty', 'amount', 'notes', 'created_at')
    fields = ('product', 'transaction_type', 'qty', 'amount', 'created_at')
    
    def has_add_permission(self, request, obj=None):
        return False


class PaymentInline(admin.TabularInline):
    """Inline for payments in transaction admin."""
    model = Payment
    extra = 0
    can_delete = False
    readonly_fields = ('method', 'amount', 'created_at')
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    """Admin for Shift model."""
    list_display = ('id', 'staff', 'location', 'started_at', 'closed_at', 'is_closed_badge', 'total_sales', 'total_cash', 'total_card')
    list_filter = ('is_closed', 'location', 'started_at')
    search_fields = ('staff__user__username', 'staff__user__first_name', 'staff__user__last_name')
    readonly_fields = ('started_at', 'closed_at', 'created_at', 'updated_at', 'total_sales', 'total_cash', 'total_card')
    inlines = [TransactionInline]
    date_hierarchy = 'started_at'
    
    fieldsets = (
        (None, {
            'fields': ('staff', 'location', 'is_closed')
        }),
        ('Время', {
            'fields': ('started_at', 'closed_at')
        }),
        ('Итоги', {
            'fields': ('total_sales', 'total_cash', 'total_card'),
            'classes': ('collapse',)
        }),
        ('Дополнительно', {
            'fields': ('notes', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_closed_badge(self, obj):
        """Display colored badge for shift status."""
        if obj.is_closed:
            return format_html('<span style="color: green;">✓ Закрыта</span>')
        return format_html('<span style="color: red;">✗ Открыта</span>')
    is_closed_badge.short_description = 'Статус'
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('staff__user', 'location')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """Admin for Transaction model (read-only)."""
    list_display = ('id', 'shift', 'product', 'transaction_type', 'qty', 'amount', 'created_at', 'exported_badge')
    list_filter = ('transaction_type', 'created_at', 'exported_at')
    search_fields = ('product__name', 'shift__staff__user__username')
    readonly_fields = ('shift', 'product', 'transaction_type', 'qty', 'amount', 'notes', 'created_at', 'exported_at')
    inlines = [PaymentInline]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (None, {
            'fields': ('shift', 'product', 'transaction_type', 'qty', 'amount')
        }),
        ('Дополнительно', {
            'fields': ('notes', 'created_at', 'exported_at'),
            'classes': ('collapse',)
        }),
    )
    
    def exported_badge(self, obj):
        """Display export status."""
        if obj.exported_at:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: orange;">⏳</span>')
    exported_badge.short_description = 'Экспорт'
    
    def has_add_permission(self, request):
        """Transactions are append-only, created via services."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Transactions cannot be deleted."""
        return False
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('shift__staff__user', 'shift__location', 'product')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Admin for Payment model (read-only)."""
    list_display = ('id', 'transaction', 'method', 'amount', 'created_at')
    list_filter = ('method', 'created_at')
    readonly_fields = ('transaction', 'method', 'amount', 'created_at')
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StockCount)
class StockCountAdmin(admin.ModelAdmin):
    """Admin for StockCount model."""
    list_display = ('id', 'shift', 'product', 'quantity', 'created_at')
    list_filter = ('created_at', 'shift__location')
    search_fields = ('product__name', 'shift__staff__user__username')
    readonly_fields = ('shift', 'product', 'quantity', 'created_at')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (None, {
            'fields': ('shift', 'product', 'quantity')
        }),
        ('Дополнительно', {
            'fields': ('notes', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('shift__staff__user', 'shift__location', 'product')

