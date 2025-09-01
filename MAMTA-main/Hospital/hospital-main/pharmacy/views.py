import email
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
# from django.contrib.auth.models import User
# from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from datetime import timedelta
from django.db import transaction

from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from hospital.models import Patient
from pharmacy.models import Medicine, Cart, Order
from .utils import searchMedicines
from django.views.decorators.csrf import csrf_exempt
from pharmacy.models import Medicine, Cart, Order, Sale


# from django.db.models.signals import post_save, post_delete
# from django.dispatch import receiver


# Create your views here.

# function to return views for the urls

@csrf_exempt
@login_required(login_url="login")
def pharmacy_single_product(request,pk):
     if request.user.is_authenticated and request.user.is_patient:

        patient = Patient.objects.get(user=request.user)
        medicines = Medicine.objects.get(serial_number=pk)
        orders = Order.objects.filter(user=request.user, ordered=False)
        carts = Cart.objects.filter(user=request.user, purchased=False)
        if carts.exists() and orders.exists():
            order = orders[0]
            context = {'patient': patient, 'medicines': medicines,'carts': carts,'order': order, 'orders': orders}
            return render(request, 'pharmacy/product-single.html',context)
        else:
            context = {'patient': patient, 'medicines': medicines,'carts': carts,'orders': orders}
            return render(request, 'pharmacy/product-single.html',context)
     else:
        logout(request)
        messages.error(request, 'Not Authorized')
        return render(request, 'patient-login.html')

@csrf_exempt
@login_required(login_url="login")
def pharmacy_shop(request):
    if request.user.is_authenticated and request.user.is_patient:

        patient = Patient.objects.get(user=request.user)
        medicines = Medicine.objects.all()
        orders = Order.objects.filter(user=request.user, ordered=False)
        carts = Cart.objects.filter(user=request.user, purchased=False)

        medicines, search_query = searchMedicines(request)

        if carts.exists() and orders.exists():
            order = orders[0]
            context = {'patient': patient, 'medicines': medicines,'carts': carts,'order': order, 'orders': orders, 'search_query': search_query}
            return render(request, 'Pharmacy/shop.html', context)
        else:
            context = {'patient': patient, 'medicines': medicines,'carts': carts,'orders': orders, 'search_query': search_query}
            return render(request, 'Pharmacy/shop.html', context)

    else:
        logout(request)
        messages.error(request, 'Not Authorized')
        return render(request, 'patient-login.html')

@csrf_exempt
@login_required(login_url="login")
def checkout(request):
    return render(request, 'pharmacy/checkout.html')

@csrf_exempt
@login_required(login_url="login")
# ---------- ADD TO CART (with stock check) ----------
@login_required(login_url="login")
def add_to_cart(request, pk):
    if request.user.is_authenticated and request.user.is_patient:
        patient = Patient.objects.get(user=request.user)
        medicines = Medicine.objects.all()
        item = get_object_or_404(Medicine, pk=pk)

        # Check if stock is available
        if (item.stock_quantity or 0) < 1:
            messages.warning(request, f"Sorry, '{item.name}' is out of stock.")
            return redirect('pharmacy_shop')

        order_item, created = Cart.objects.get_or_create(item=item, user=request.user, purchased=False)
        order_qs = Order.objects.filter(user=request.user, ordered=False)
        if order_qs.exists():
            order = order_qs[0]
            if order.orderitems.filter(item=item).exists():
                # increase quantity only if stock allows
                if item.stock_quantity >= order_item.quantity + 1:
                    order_item.quantity += 1
                    order_item.save()
                else:
                    messages.warning(request, f"Cannot add more. Only {item.stock_quantity} available.")
                context = {'patient': patient,'medicines': medicines, 'order': order}
                return render(request, 'pharmacy/shop.html', context)
            else:
                order.orderitems.add(order_item)
                context = {'patient': patient,'medicines': medicines,'order': order}
                return render(request, 'pharmacy/shop.html', context)
        else:
            order = Order(user=request.user)
            order.save()
            order.orderitems.add(order_item)
            context = {'patient': patient,'medicines': medicines,'order': order}
            return render(request, 'pharmacy/shop.html', context)
    else:
        logout(request)
        messages.error(request, 'Not Authorized')
        return render(request, 'patient-login.html')

@csrf_exempt
@login_required(login_url="login")
def cart_view(request):
    if request.user.is_authenticated and request.user.is_patient:

        patient = Patient.objects.get(user=request.user)
        medicines = Medicine.objects.all()

        carts = Cart.objects.filter(user=request.user, purchased=False)
        orders = Order.objects.filter(user=request.user, ordered=False)
        if carts.exists() and orders.exists():
            order = orders[0]
            context = {'carts': carts,'order': order}
            return render(request, 'Pharmacy/cart.html', context)
        else:
            messages.warning(request, "You don't have any item in your cart!")
            context = {'patient': patient,'medicines': medicines}
            return render(request, 'pharmacy/shop.html', context)
    else:
        logout(request)
        messages.info(request, 'Not Authorized')
        return render(request, 'patient-login.html')

@csrf_exempt
@login_required(login_url="login")
def remove_from_cart(request, pk):
    if request.user.is_authenticated and request.user.is_patient:

        patient = Patient.objects.get(user=request.user)
        medicines = Medicine.objects.all()
        carts = Cart.objects.filter(user=request.user, purchased=False)

        item = get_object_or_404(Medicine, pk=pk)
        order_qs = Order.objects.filter(user=request.user, ordered=False)
        if order_qs.exists():
            order = order_qs[0]
            if order.orderitems.filter(item=item).exists():
                order_item = Cart.objects.filter(item=item, user=request.user, purchased=False)[0]
                order.orderitems.remove(order_item)
                order_item.delete()
                messages.warning(request, "This item was remove from your cart!")
                context = {'carts': carts,'order': order}
                return render(request, 'Pharmacy/cart.html', context)
            else:
                messages.info(request, "This item was not in your cart")
                context = {'patient': patient,'medicines': medicines}
                return render(request, 'pharmacy/shop.html', context)
        else:
            messages.info(request, "You don't have an active order")
            context = {'patient': patient,'medicines': medicines}
            return render(request, 'pharmacy/shop.html', context)
    else:
        logout(request)
        messages.error(request, 'Not Authorized')
        return render(request, 'patient-login.html')


@csrf_exempt
@login_required(login_url="login")
# ---------- INCREASE CART (with stock check) ----------
@login_required(login_url="login")
def increase_cart(request, pk):
    if request.user.is_authenticated and request.user.is_patient:
        patient = Patient.objects.get(user=request.user)
        medicines = Medicine.objects.all()
        carts = Cart.objects.filter(user=request.user, purchased=False)
        item = get_object_or_404(Medicine, pk=pk)
        order_qs = Order.objects.filter(user=request.user, ordered=False)
        if order_qs.exists():
            order = order_qs[0]
            if order.orderitems.filter(item=item).exists():
                order_item = Cart.objects.filter(item=item, user=request.user, purchased=False)[0]
                # check available stock before increasing
                if item.stock_quantity >= order_item.quantity + 1:
                    order_item.quantity += 1
                    order_item.save()
                    messages.warning(request, f"{item.name} quantity has been updated")
                else:
                    messages.warning(request, f"Cannot increase. Only {item.stock_quantity} available.")
                context = {'carts': carts,'order': order}
                return render(request, 'Pharmacy/cart.html', context)
            else:
                messages.warning(request, f"{item.name} is not in your cart")
                context = {'patient': patient,'medicines': medicines}
                return render(request, 'pharmacy/shop.html', context)
        else:
            messages.warning(request, "You don't have an active order")
            context = {'patient': patient,'medicines': medicines}
            return render(request, 'pharmacy/shop.html', context)
    else:
        logout(request)
        messages.error(request, 'Not Authorized')
        return render(request, 'patient-login.html')
@csrf_exempt
@login_required(login_url="login")
@login_required(login_url="login")
def decrease_cart(request, pk):
    if request.user.is_authenticated and request.user.is_patient:
        patient = Patient.objects.get(user=request.user)
        medicines = Medicine.objects.all()
        carts = Cart.objects.filter(user=request.user, purchased=False)
        item = get_object_or_404(Medicine, pk=pk)
        order_qs = Order.objects.filter(user=request.user, ordered=False)
        if order_qs.exists():
            order = order_qs[0]
            if order.orderitems.filter(item=item).exists():
                order_item = Cart.objects.filter(item=item, user=request.user, purchased=False)[0]
                if order_item.quantity > 1:
                    order_item.quantity -= 1
                    order_item.save()
                    messages.warning(request, f"{item.name} quantity has been updated")
                    context = {'carts': carts,'order': order}
                    return render(request, 'Pharmacy/cart.html', context)
                else:
                    order.orderitems.remove(order_item)
                    order_item.delete()
                    messages.warning(request, f"{item.name} item has been removed from your cart")
                    context = {'carts': carts,'order': order}
                    return render(request, 'Pharmacy/cart.html', context)
            else:
                messages.info(request, f"{item.name} is not in your cart")
                context = {'patient': patient,'medicines': medicines}
                return render(request, 'pharmacy/shop.html', context)
        else:
            messages.info(request, "You don't have an active order")
            context = {'patient': patient,'medicines': medicines}
            return render(request, 'pharmacy/shop.html', context)
    else:
        logout(request)
        messages.error(request, 'Not Authorized')
        return render(request, 'patient-login.html')
        # Create your views here.
# ---------- EXPIRY LIST ----------
@csrf_exempt
@login_required(login_url="login")
def expiring_soon(request):
    """List medicines expiring within 90 days."""
    # allow pharmacists/staff or fall back to any logged in user - adjust per your roles
    is_pharmacist = hasattr(request.user, 'pharmacist')
    if request.user.is_authenticated and (request.user.is_superuser or request.user.is_staff or is_pharmacist):
        cutoff = timezone.now().date() + timedelta(days=90)
        expiring = Medicine.objects.filter(expiry_date__lte=cutoff).order_by('expiry_date')
        # put template in same folder as shop.html (see note below)
        return render(request, 'pharmacy/expiring_soon.html', {'expiring': expiring})
    else:
        messages.error(request, "Not Authorized")
        return redirect('pharmacy_shop')
# ---------- SALES HISTORY ----------
@login_required(login_url="login")
def sales_history(request):
    """Show sales (pharmacist/staff see all, others see what they sold)."""
    is_pharmacist = hasattr(request.user, 'pharmacist')
    if request.user.is_superuser or request.user.is_staff or is_pharmacist:
        sales = Sale.objects.select_related('medicine').order_by('-sold_at')
    else:
        sales = Sale.objects.filter(sold_by=request.user).select_related('medicine').order_by('-sold_at')
    return render(request, 'pharmacy/sales_history.html', {'sales': sales})

# ---------- CONFIRM ORDER (finalize) ----------
@login_required(login_url="login")
def confirm_order(request):
    """
    Confirm and finalize the active order for the logged-in user.
    This reduces stock and creates Sale rows using Order.finalize_order()
    """
    try:
        order = Order.objects.filter(user=request.user, ordered=False).first()
        if not order:
            messages.error(request, "No active order to confirm.")
            return redirect('pharmacy_shop')

        try:
            with transaction.atomic():
                order.finalize_order()
                messages.success(request, "Order confirmed. Stock updated and sale recorded.")
                return render(request, 'pharmacy/order_success.html', {'order': order})
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('cart_view')

    except Exception as e:
        messages.error(request, "Something went wrong: " + str(e))
        return redirect('cart_view')