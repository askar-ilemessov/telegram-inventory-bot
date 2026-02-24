"""
Admin configuration for Inventory app.
"""
from django.contrib import admin
from .models import Category, Product, StorageStock, DisplayStock, PurchaseTransaction, TransferTransaction


@admin.register(StorageStock)
class StorageStockAdmin(admin.ModelAdmin):
    """Admin for StorageStock model."""
    list_display = ('product', 'location', 'quantity', 'last_purchase_price', 'updated_at')
    list_filter = ('location', 'updated_at')
    search_fields = ('product__name',)
    readonly_fields = ('product', 'location', 'quantity', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('product', 'location', 'quantity')
        }),
        ('Закупка', {
            'fields': ('last_purchase_price',)
        }),
        ('Системная информация', {
            'fields': ('updated_at',),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Prevent manual creation (auto-created with Product)."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion."""
        return False


@admin.register(DisplayStock)
class DisplayStockAdmin(admin.ModelAdmin):
    """Admin for DisplayStock model."""
    list_display = ('product', 'location', 'quantity', 'updated_at')
    list_filter = ('location', 'updated_at')
    search_fields = ('product__name',)
    readonly_fields = ('product', 'location', 'quantity', 'updated_at')
    
    fieldsets = (
        (None, {
            'fields': ('product', 'location', 'quantity')
        }),
        ('Системная информация', {
            'fields': ('updated_at',),
            'classes': ('collapse',)
        }),
    )
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion."""
        return False


@admin.register(PurchaseTransaction)
class PurchaseTransactionAdmin(admin.ModelAdmin):
    """Admin for PurchaseTransaction model."""
    list_display = ('id', 'product', 'location', 'quantity', 'purchase_price', 'total_cost', 'supplier', 'created_by', 'created_at')
    list_filter = ('location', 'created_at', 'supplier')
    search_fields = ('product__name', 'supplier', 'notes')
    readonly_fields = ('product', 'location', 'quantity', 'purchase_price', 'total_cost', 'created_by', 'created_at')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (None, {
            'fields': ('product', 'location', 'quantity', 'purchase_price', 'total_cost')
        }),
        ('Поставщик', {
            'fields': ('supplier', 'notes')
        }),
        ('Системная информация', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('product', 'location', 'created_by')
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion (append-only)."""
        return False


@admin.register(TransferTransaction)
class TransferTransactionAdmin(admin.ModelAdmin):
    """Admin for TransferTransaction model."""
    list_display = ('id', 'product', 'location', 'quantity', 'created_by', 'created_at')
    list_filter = ('location', 'created_at')
    search_fields = ('product__name', 'notes')
    readonly_fields = ('product', 'location', 'quantity', 'created_by', 'created_at')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (None, {
            'fields': ('product', 'location', 'quantity')
        }),
        ('Дополнительно', {
            'fields': ('notes',)
        }),
        ('Системная информация', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('product', 'location', 'created_by')
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion (append-only)."""
        return False


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Admin for Product model."""
    list_display = ('name', 'category', 'location', 'price', 'stock_quantity', 'unit', 'is_active')
    list_filter = ('category', 'location', 'is_active')
    search_fields = ('name',)
    list_editable = ('price', 'is_active')
    
    fieldsets = (
        (None, {
            'fields': ('name', 'category', 'location', 'price', 'unit', 'is_active')
        }),
        ('Остатки (только чтение)', {
            'fields': ('get_storage_stock', 'get_display_stock', 'get_total_stock'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('get_storage_stock', 'get_display_stock', 'get_total_stock')
    
    def stock_quantity(self, obj):
        """Display total stock in list."""
        return obj.stock_quantity
    stock_quantity.short_description = 'Остаток'
    
    def get_storage_stock(self, obj):
        """Display storage stock."""
        storage = getattr(obj, 'storage_stock', None)
        return storage.quantity if storage else '0.00'
    get_storage_stock.short_description = 'На складе'
    
    def get_display_stock(self, obj):
        """Display display stock."""
        display = getattr(obj, 'display_stock', None)
        return display.quantity if display else '0.00'
    get_display_stock.short_description = 'На витрине'
    
    def get_total_stock(self, obj):
        """Display total stock."""
        return obj.stock_quantity
    get_total_stock.short_description = 'Всего'
    
    def get_queryset(self, request):
        """Optimize queryset."""
        qs = super().get_queryset(request)
        return qs.select_related('category', 'location', 'storage_stock', 'display_stock')


