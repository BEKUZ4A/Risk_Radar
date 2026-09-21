# Risk Radar Employee Frontend

This is a standalone React + Three.js employee portal. It does not import or depend on the Django Risk Radar source files.

## Run

```bash
npm install
npm run dev
```

The default development API uses the Vite proxy to reach the local Django backend:

```text
/api -> http://127.0.0.1:8000
```

Copy `.env.example` to `.env` only if the API URL needs to be changed.

## Flow

1. Employee signs in with `POST /api/users/auth/jwt/create/`.
2. Products and categories load from the catalog endpoints.
3. Search and category filtering happen in the browser.
4. Cart checkout calls `POST /api/payments/checkout/`.
5. Payment history loads from `GET /api/payments/my/`.

The checkout input accepts a Stripe PaymentMethod ID. In Stripe test mode the backend uses `pm_card_visa` when the field is empty, as documented by its API contract.
