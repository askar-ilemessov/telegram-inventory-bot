"""
Admin configuration for Inventory app.
"""
from django.contrib import admin
from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin for Category model."""
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Admin for Product model."""
    list_display = ('name', 'category', 'location', 'price', 'stock_quantity', 'unit', 'is_active', 'updated_at')
    list_filter = ('category', 'location', 'is_active', 'created_at')
    search_fields = ('name', 'category__name')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('price', 'stock_quantity', 'is_active')
    fieldsets = (
        (None, {
            'fields': ('name', 'category', 'location', 'price', 'unit', 'is_active')
        }),
        ('Stock', {
            'fields': ('stock_quantity',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related('category', 'location')

