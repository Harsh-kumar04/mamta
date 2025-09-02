from django.contrib import admin
from .models import Pharmacist, Medicine, Cart, Order, Sale

class MedicineAdmin(admin.ModelAdmin):
    list_display = ('name', 'stock_quantity', 'is_low_stock', 'expiry_date', 'is_expiring_soon', 'price')
    list_filter = ('medicine_category','medicine_type')
    search_fields = ('name',)

admin.site.register(Pharmacist)
admin.site.register(Medicine, MedicineAdmin)
admin.site.register(Cart)
admin.site.register(Order)
admin.site.register(Sale)
