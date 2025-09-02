from django.db.models import Q
from pharmacy.models import Medicine
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
from .models import Admin_Information


def searchMedicines(request):
    
    search_query = ''
    
    if request.GET.get('search_query'):
        search_query = request.GET.get('search_query')
            
    medicine = Medicine.objects.filter(Q(name__icontains=search_query))
    
    return medicine, search_query


def notify_admins_medicine_expiring(medicine: Medicine) -> int:
    """
    Send an email notification to pharmacy admins if the given medicine is
    expiring within the next 90 days or already expired.

    Returns number of emails attempted to send.
    """
    if not getattr(medicine, 'expiry_date', None):
        return 0

    today = timezone.now().date()
    threshold = today + timedelta(days=90)
    if medicine.expiry_date > threshold:
        return 0

    status_text = 'Expired' if medicine.expiry_date <= today else 'Expiring soon'

    recipients = list(
        Admin_Information.objects
        .filter(role='pharmacy')
        .exclude(email__isnull=True)
        .exclude(email__exact='')
        .values_list('email', flat=True)
    )
    if not recipients:
        return 0

    subject = f"Medicine {status_text}: {medicine.name}"
    message = (
        f"Hello Admin,\n\n"
        f"The following medicine is {status_text.lower()}:\n"
        f"- Name: {medicine.name}\n"
        f"- Category: {medicine.medicine_category or '-'}\n"
        f"- Type: {medicine.medicine_type or '-'}\n"
        f"- Stock: {medicine.stock_quantity or 0}\n"
        f"- Expiry Date: {medicine.expiry_date}\n\n"
        f"Please review inventory and take necessary actions.\n"
    )

    try:
        send_mail(subject, message, None, recipients, fail_silently=True)
    except Exception:
        # Fail silently; we don't want to block saves.
        return 0

    return len(recipients)


def notify_admins_medicine_low_stock(medicine: Medicine) -> int:
    """
    Notify pharmacy admins when a medicine reaches low stock (<=10).
    Returns number of recipient emails attempted.
    """
    if (getattr(medicine, 'stock_quantity', 0) or 0) > 10:
        return 0

    recipients = list(
        Admin_Information.objects
        .filter(role='pharmacy')
        .exclude(email__isnull=True)
        .exclude(email__exact='')
        .values_list('email', flat=True)
    )
    if not recipients:
        return 0

    subject = f"Medicine Low Stock: {medicine.name}"
    message = (
        f"Hello Admin,\n\n"
        f"The following medicine stock is low (≤10):\n"
        f"- Name: {medicine.name}\n"
        f"- Category: {medicine.medicine_category or '-'}\n"
        f"- Type: {medicine.medicine_type or '-'}\n"
        f"- Current Stock: {medicine.stock_quantity or 0}\n"
        f"- Expiry Date: {getattr(medicine, 'expiry_date', '-') or '-'}\n\n"
        f"Please restock as needed.\n"
    )

    try:
        send_mail(subject, message, None, recipients, fail_silently=True)
    except Exception:
        return 0

    return len(recipients)