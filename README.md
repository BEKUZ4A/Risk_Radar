# Risk Radar

Django REST Framework asosidagi risk scoring, katalog, OTP autentifikatsiya va
Stripe to‘lov API.

## Lokal ishga tushirish

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DJANGO_SETTINGS_MODULE = "config.settings"
python manage.py migrate
python manage.py runserver
```

Testlar:

```powershell
python manage.py test
```

## Muhit sozlamalari

`.env.example` nusxasini `.env` qilib, kamida `SECRET_KEY`, `DEBUG`,
`ALLOWED_HOSTS`, `DB_ENGINE`, Stripe kalitlari va production uchun
`REDIS_URL`, `CELERY_BROKER_URL` hamda email sozlamalarini kiriting.
Production'da `DEBUG=False` bo‘lishi va SQLite ishlatilmasligi kerak.
Docker Compose production PostgreSQL, Redis healthcheck va avtomatik
migratsiya bilan keladi.

## Rollar matritsasi

| Amal | OWNER | EMPLOYEE | CUSTOMER |
|---|---:|---:|---:|
| Dashboard va risk baholash | Ha | Yo‘q | Yo‘q |
| Employee ingest | Yo‘q | Ha | Yo‘q |
| Customer financial ingest | Yo‘q | Yo‘q | Ha |
| Katalogni ko‘rish | Ha | Ha | Ha |
| Katalog obyektini yaratish | Ha | Yo‘q | Ha |
| O‘z katalog obyektini tahrirlash | Ha | Yo‘q | Ha |
| Boshqa customer obyektini tahrirlash | Ha | Yo‘q | Yo‘q |
| Stripe checkout | Ha | Ha | Yo‘q |

`is_staff` yoki `is_superuser` flaglari texnik administrator huquqini beradi.
`root` username'i public ro‘yxatdan o‘tish uchun rezerv qilingan.
Email tasdiqlanmaguncha JWT berilmaydi.
