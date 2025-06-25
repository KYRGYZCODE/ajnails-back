import os
import hashlib
import requests
import xml.etree.ElementTree as ET
from django.conf import settings

from .models import Lead

INIT_URL = 'https://api.freedompay.kg/init_payment.php'
SCRIPT_NAME = 'init_payment.php'
MERCHANT_ID = settings.FREEDOMPAY_MERCHANT_ID
SECRET_KEY = settings.FREEDOMPAY_SECRET_KEY


def _make_signature(params: dict) -> str:
    string_parts = [SCRIPT_NAME]
    for key in sorted(k for k in params.keys() if k != 'pg_sig'):
        string_parts.append(str(params[key]))
    string_parts.append(SECRET_KEY)
    sign_str = ';'.join(string_parts)
    return hashlib.md5(sign_str.encode()).hexdigest()


def create_payment_for_lead(lead: Lead) -> str:
    """Create payment via FreedomPay and return redirect url."""
    try:
        total_amount = sum((s.price for s in lead.services.all()), 0)
        params = {
            'pg_merchant_id': MERCHANT_ID,
            'pg_order_id': lead.pk,
            'pg_amount': total_amount,
            'pg_currency': 'KGS',
            'pg_description': f"\u041E\u043F\u043B\u0430\u0442\u0430 \u0437\u0430\u043F\u0438\u0441\u0438 #{lead.pk}",
            'pg_salt': os.urandom(16).hex(),
            'pg_testing_mode': '1',
            'pg_result_url': settings.FREEDOMPAY_RESULT_URL,
            'pg_success_url': settings.FREEDOMPAY_SUCCESS_URL,
            'pg_failure_url': settings.FREEDOMPAY_FAILURE_URL,
            'pg_request_method': 'POST',
        }
        params['pg_sig'] = _make_signature(params)
        response = requests.post(INIT_URL, data=params)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        status = root.findtext('pg_status')
        if status != 'ok':
            error = root.findtext('pg_error_description') or 'Unknown error'
            raise RuntimeError(error)
        redirect_url = root.findtext('pg_redirect_url')
        lead.payment_url = redirect_url
        lead.save(update_fields=['payment_url'])
        return redirect_url
    except Exception as exc:
        print(f"Payment creation failed for lead {lead.pk}: {exc}")
        raise
