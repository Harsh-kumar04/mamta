# pharmacy/models.py
from django.db import models
from django.conf import settings
import uuid
from doctor.models import Prescription
from hospital.models import User, Patient

from django.db.models import F
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

# Pharmacist unchanged (kept as-is)
class Pharmacist(models.Model):
    pharmacist_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, related_name='pharmacist')
    name = models.CharField(max_length=200, null=True, blank=True)
    username = models.CharField(max_length=200, null=True, blank=True)
    degree = models.CharField(max_length=200, null=True, blank=True)
    featured_image = models.ImageField(upload_to='doctors/', default='pharmacist/user-default.png', null=True, blank=True)
    email = models.EmailField(max_length=200, null=True, blank=True)
    phone_number = models.IntegerField(null=True, blank=True)
    age = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return str(self.user.username)


class Medicine(models.Model):
    MEDICINE_TYPE = (
        ('tablets', 'tablets'),
        ('syrup', 'syrup'),
        ('capsule', 'capsule'),
        ('general', 'general'),
    )
    REQUIREMENT_TYPE = (
        ('yes', 'yes'),
        ('no', 'no'),
    )

    MEDICINE_CATEGORY = (
        ('fever', 'fever'),
        ('pain', 'pain'),
        ('cough', 'cough'),
        ('cold', 'cold'),
        ('flu', 'flu'),
        ('diabetes', 'diabetes'),
        ('eye', 'eye'),
        ('ear', 'ear'),
        ('allergy', 'allergy'),
        ('asthma', 'asthma'),
        ('bloodpressure', 'bloodpressure'),
        ('heartdisease', 'heartdisease'),
        ('vitamins', 'vitamins'),
        ('digestivehealth', 'digestivehealth'),
        ('skin', 'skin'),
        ('infection', 'infection'),
        ('nurological', 'nurological'),
    )

    serial_number = models.AutoField(primary_key=True)
    medicine_id = models.CharField(max_length=200, null=True, blank=True)
    name = models.CharField(max_length=200, null=True, blank=True)
    weight = models.CharField(max_length=200, null=True, blank=True)
    quantity = models.IntegerField(null=True, blank=True, default=0)
    featured_image = models.ImageField(upload_to='medicines/', default='medicines/default.png', null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    medicine_type = models.CharField(max_length=200, choices=MEDICINE_TYPE, null=True, blank=True)
    medicine_category = models.CharField(max_length=200, choices=MEDICINE_CATEGORY, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    stock_quantity = models.IntegerField(null=True, blank=True, default=0)
    expiry_date = models.DateField(null=True, blank=True)   # NEW: expiry date
    Prescription_reqiuired = models.CharField(max_length=200, choices=REQUIREMENT_TYPE, null=True, blank=True)

    def __str__(self):
        return str(self.name)

    def is_expiring_soon(self):
        """Return True if expiry_date is within next 90 days (<= 3 months)."""
        if self.expiry_date:
            return self.expiry_date <= timezone.now().date() + timedelta(days=90)
        return False
    is_expiring_soon.boolean = True
    is_expiring_soon.short_description = 'Expiring ≤ 3 months'

    def is_low_stock(self) -> bool:
        """Return True if stock is at or below low-stock threshold (10)."""
        try:
            return (self.stock_quantity or 0) <= 10
        except Exception:
            return False
    is_low_stock.boolean = True
    is_low_stock.short_description = 'Low stock (≤10)'


class Cart(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart')
    item = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    purchased = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.quantity} X {self.item}'

    # Each product total
    def get_total(self):
        total = (self.item.price or Decimal('0.00')) * self.quantity
        float_total = format(total, '0.2f')
        return float_total


class Sale(models.Model):
    """
    Sales record: created when an Order is finalized.
    """
    sale_id = models.AutoField(primary_key=True)
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name='sales')
    quantity = models.PositiveIntegerField()
    price_at_sale = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    sold_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    sold_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.medicine.name} x{self.quantity} @ {self.sold_at.date()}"


class Order(models.Model):
    # id
    orderitems = models.ManyToManyField(Cart)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ordered = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    payment_status = models.CharField(max_length=200, blank=True, null=True)
    trans_ID = models.CharField(max_length=200, blank=True, null=True)

    # Subtotal
    def get_totals(self):
        total = 0
        for order_item in self.orderitems.all():
            total += float(order_item.get_total())
        return total

    # Count Cart Items
    def count_cart_items(self):
        return self.orderitems.count()

    def stock_quantity_decrease(self):
        """
        Safe stock decrease (uses F expression).
        Use when you want to decrement stock only.
        """
        for order_item in self.orderitems.select_related('item').all():
            # Use F expression to avoid race-conditions
            Medicine.objects.filter(pk=order_item.item.pk).update(stock_quantity=F('stock_quantity') - order_item.quantity)
        # refresh cached objects
        for order_item in self.orderitems.select_related('item').all():
            order_item.item.refresh_from_db()

    def finalize_order(self):
        """
        Mark the order as finalized:
         - check stock
         - deduct stock
         - create Sale records
         - mark carts purchased
         - mark order.ordered = True
        Call this when payment succeeds.
        """
        from django.db import transaction
        with transaction.atomic():
            if self.ordered:
                return False
            # First check all stock availability
            for cart_item in self.orderitems.select_related('item').all():
                med = cart_item.item
                med.refresh_from_db()
                if (med.stock_quantity or 0) < cart_item.quantity:
                    raise ValueError(f"Not enough stock for {med.name}. Available: {med.stock_quantity}, requested: {cart_item.quantity}")

            # Decrement stock and create Sale rows
            for cart_item in self.orderitems.select_related('item').all():
                med = cart_item.item
                # Use F to update safely
                Medicine.objects.filter(pk=med.pk).update(stock_quantity=F('stock_quantity') - cart_item.quantity)
                # create Sale record
                Sale.objects.create(
                    medicine=med,
                    quantity=cart_item.quantity,
                    price_at_sale=med.price or Decimal('0.00'),
                    total_price=(med.price or Decimal('0.00')) * cart_item.quantity,
                    sold_by=self.user
                )
                cart_item.purchased = True
                cart_item.save(update_fields=['purchased'])

            # refresh items to reflect correct stock numbers
            for cart_item in self.orderitems.select_related('item').all():
                cart_item.item.refresh_from_db()

            # finalize order
            self.ordered = True
            self.save(update_fields=['ordered'])
            # After finalizing, notify admins for any low stock items
            try:
                from hospital_admin.utils import notify_admins_medicine_low_stock
                for cart_item in self.orderitems.select_related('item').all():
                    med = cart_item.item
                    med.refresh_from_db()
                    if (med.stock_quantity or 0) <= 10:
                        try:
                            notify_admins_medicine_low_stock(med)
                        except Exception:
                            pass
            except Exception:
                pass
            return True

    # TOTAL
    def final_bill(self):
        delivery_price= 40.00
        Bill = self.get_totals()+ delivery_price
        float_Bill = format(Bill, '0.2f')
        return float_Bill
