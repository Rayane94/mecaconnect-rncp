import os
import uuid

import httpx


class PaymentProvider:
    async def create_test_payment(self, booking_id: int, amount: float) -> dict:
        raise NotImplementedError


class LocalTestPaymentProvider(PaymentProvider):
    """Paiement simulé uniquement pour pouvoir développer sans compte Stripe."""

    async def create_test_payment(self, booking_id: int, amount: float) -> dict:
        reference = f"local_test_{uuid.uuid4().hex[:20]}"
        return {
            "provider_reference": reference,
            "checkout_url": f"/api/payments/test/{booking_id}/confirm",
            "mode": "local-test",
        }


class StripeTestPaymentProvider(PaymentProvider):
    """Création d'une session Stripe Checkout dans l'environnement Test."""

    def __init__(self, secret_key: str, app_base_url: str):
        self.secret_key = secret_key
        self.app_base_url = app_base_url.rstrip("/")

    async def create_test_payment(self, booking_id: int, amount: float) -> dict:
        amount_in_cents = int(round(amount * 100))
        data = {
            "mode": "payment",
            "line_items[0][price_data][currency]": "eur",
            "line_items[0][price_data][product_data][name]": (
                f"Acompte MecaConnect - réservation #{booking_id}"
            ),
            "line_items[0][price_data][unit_amount]": str(amount_in_cents),
            "line_items[0][quantity]": "1",
            "metadata[booking_id]": str(booking_id),
            "success_url": (
                f"{self.app_base_url}/api/payments/stripe/confirm"
                "?session_id={CHECKOUT_SESSION_ID}"
            ),
            "cancel_url": f"{self.app_base_url}/?payment=cancelled",
        }

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.stripe.com/v1/checkout/sessions",
                data=data,
                auth=(self.secret_key, ""),
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()

        return {
            "provider_reference": payload["id"],
            "checkout_url": payload["url"],
            "mode": "stripe-test",
        }

    async def retrieve_session(self, session_id: str) -> dict:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"https://api.stripe.com/v1/checkout/sessions/{session_id}",
                auth=(self.secret_key, ""),
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            return response.json()


# Alias conservés pour garder des noms simples dans les tests et le dossier.
StripeHttpProvider = StripeTestPaymentProvider
LocalStripeTestProvider = LocalTestPaymentProvider


def get_payment_provider() -> PaymentProvider:
    stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
    app_base_url = os.getenv("APP_BASE_URL", "http://localhost:8000")

    if stripe_key.startswith("sk_test_") and "replace_me" not in stripe_key:
        return StripeTestPaymentProvider(stripe_key, app_base_url)

    return LocalTestPaymentProvider()
