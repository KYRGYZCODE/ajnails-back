import os
import hashlib
import requests
import xml.etree.ElementTree as ET
from celery import shared_task
from django.conf import settings
from .models import Lead

INIT_URL      = 'https://api.freedompay.kg/init_payment.php'
STATUS_URL    = 'https://api.freedompay.kg/get_status3.php'
SCRIPT_INIT   = 'init_payment.php'
SCRIPT_STATUS = 'get_status3.php'
MERCHANT_ID   = settings.FREEDOMPAY_MERCHANT_ID
SECRET_KEY    = settings.FREEDOMPAY_SECRET_KEY

def _make_signature(script_name: str, params: dict) -> str:
    items = {k: v for k, v in params.items() if k != 'pg_sig'}
    sorted_keys = sorted(items.keys())
    parts = [script_name] + [str(items[k]) for k in sorted_keys] + [SECRET_KEY]
    return hashlib.md5(';'.join(parts).encode('utf-8')).hexdigest()

@shared_task(bind=True, max_retries=None)
def check_payment_status(self, lead_pk: int):
    """
    Task: проверяет статус предоплаты для конкретного лида.
    Если статус НЕ финальный — перезапускает себя через 15 секунд.
    Если финальный (success/ok) — помечает lead.prepayment_paid=True и шлёт уведомление.
    """
    try:
        lead = Lead.objects.get(pk=lead_pk)
    except Lead.DoesNotExist:
        return

    if lead.prepayment_paid:
        return

    salt = os.urandom(16).hex()
    params = {
        'pg_merchant_id': MERCHANT_ID,
        'pg_order_id':    str(lead.pk),
        'pg_salt':        salt,
    }
    params['pg_sig'] = _make_signature(SCRIPT_STATUS, params)

    resp = requests.post(STATUS_URL, data=params)
    resp.raise_for_status()

    root = ET.fromstring(resp.text)
    if root.findtext('pg_status') != 'ok':
        error = root.findtext('pg_error_description') or 'Unknown error'
        raise RuntimeError(f"FP status error: {error}")

    status = root.findtext('pg_payment_status')
    if status in ('success', 'ok'):
        lead.prepayment_paid = True
        lead.is_confirmed = True
        lead.save(update_fields=['prepayment_paid', 'is_confirmed'])
    elif status in ('failed', 'error'):
        pass
    else:
        self.retry(countdown=15)
