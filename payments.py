import os
import time
import hashlib
import requests
import xml.etree.ElementTree as ET

# TODO: заполните своими значениями
MERCHANT_ID = '560458'
SECRET_KEY  = 'nvfKVRhgfS97L5TO'

# Эндпоинты и названия скриптов
INIT_URL      = 'https://api.freedompay.kg/init_payment.php'
STATUS_URL    = 'https://api.freedompay.kg/get_status3.php'
SCRIPT_INIT   = 'init_payment.php'
SCRIPT_STATUS = 'get_status3.php'

def make_signature(script_name: str, params: dict) -> str:
    items = {k: v for k, v in params.items() if k != 'pg_sig'}
    sorted_keys = sorted(items.keys())
    parts = [script_name] + [items[k] for k in sorted_keys] + [SECRET_KEY]
    sign_str = ';'.join(parts)
    return hashlib.md5(sign_str.encode('utf-8')).hexdigest()

def init_payment(order_id: str, amount: float, description: str) -> str:
    salt = os.urandom(16).hex()
    params = {
        'pg_order_id':    order_id,
        'pg_merchant_id': MERCHANT_ID,
        'pg_amount':      str(amount),
        'pg_currency':    'KGS',
        'pg_description': description,
        'pg_salt':        salt,
        'pg_testing_mode': '1',
        'pg_success_url':  'https://c076-212-112-100-101.ngrok-free.app/success',
        'pg_failure_url':  'https://c076-212-112-100-101.ngrok-free.app/failure',
        'pg_request_method': 'POST',
    }
    params['pg_sig'] = make_signature(SCRIPT_INIT, params)
    print("INIT params:", params)

    resp = requests.post(INIT_URL, data=params)
    print("Response:", resp.text)
    resp.raise_for_status()

    root = ET.fromstring(resp.text)
    if root.findtext('pg_status') != 'ok':
        error = root.findtext('pg_error_description') or 'unknown error'
        raise RuntimeError(f'Payment init failed: {error}')

    return root.findtext('pg_redirect_url')

def get_payment_status(order_id: str = None, payment_id: str = None) -> str:
    salt = os.urandom(16).hex()
    params = {
        'pg_merchant_id': MERCHANT_ID,
        'pg_salt':        salt,
    }
    if order_id:
        params['pg_order_id'] = order_id
    elif payment_id:
        params['pg_payment_id'] = payment_id
    else:
        raise ValueError("Нужно указать order_id или payment_id")

    params['pg_sig'] = make_signature(SCRIPT_STATUS, params)

    resp = requests.post(STATUS_URL, data=params)
    resp.raise_for_status()

    root = ET.fromstring(resp.text)
    if root.findtext('pg_status') != 'ok':
        err = root.findtext('pg_error_description') or 'Unknown error'
        raise RuntimeError(f'Status request failed: {err}')

    return root.findtext('pg_payment_status')

if __name__ == "__main__":
    order_id   = 'ORDER123'
    amount     = 1500
    description= 'Запись в салон красоты'

    # 1) Инициация платежа
    try:
        redirect_url = init_payment(order_id, amount, description)
        print('Перейдите на страницу оплаты и завершите платёж:\n', redirect_url)
    except Exception as e:
        print('Ошибка при инициации платежа:', e)
        exit(1)

    # 2) Опрос статуса до финального состояния
    print('\nОжидание завершения платежа… (опрашиваем каждые 5 секунд)')
    final_states = {'success', 'ok', 'failed', 'error'}
    while True:
        try:
            status = get_payment_status(order_id=order_id)
        except Exception as e:
            print('Ошибка при запросе статуса:', e)
            break

        if status in final_states:
            if status in ('success', 'ok'):
                print('✅ Платёж успешно проведён')
            else:
                print('❌ Платёж не прошёл:', status)
            break

        # Если статус ещё "new" или "pending" — ждём и опрашиваем вновь
        print(f'…текущий статус: {status}. Ждём 5 сек…')
        time.sleep(5)
