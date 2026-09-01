import asyncio
from app import payment


class FakeResponse:
    def __init__(self, body):
        self.body = body
    def raise_for_status(self):
        return None
    def json(self):
        return self.body


class FakeAsyncClient:
    last_post = None
    last_get = None
    def __init__(self, *args, **kwargs):
        pass
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        return False
    async def post(self, url, **kwargs):
        FakeAsyncClient.last_post = (url, kwargs)
        return FakeResponse({"id":"cs_test_demo","url":"https://checkout.stripe.test/session"})
    async def get(self, url, **kwargs):
        FakeAsyncClient.last_get = (url, kwargs)
        return FakeResponse({"id":"cs_test_demo","payment_status":"paid","metadata":{"booking_id":"12"}})


def test_stripe_checkout_payload_and_retrieval(monkeypatch):
    async def run():
        monkeypatch.setattr(payment.httpx, "AsyncClient", FakeAsyncClient)
        provider = payment.StripeHttpProvider("sk_test_demo", "https://mecaconnect.example")
        created = await provider.create_test_payment(12, 23.80)
        assert created["mode"] == "stripe-test"
        assert created["provider_reference"] == "cs_test_demo"
        url, kwargs = FakeAsyncClient.last_post
        assert url.endswith("/v1/checkout/sessions")
        assert kwargs["data"]["line_items[0][price_data][unit_amount]"] == "2380"
        assert kwargs["data"]["metadata[booking_id]"] == "12"
        assert "{CHECKOUT_SESSION_ID}" in kwargs["data"]["success_url"]
        session = await provider.retrieve_session("cs_test_demo")
        assert session["payment_status"] == "paid"
        assert FakeAsyncClient.last_get[0].endswith("/v1/checkout/sessions/cs_test_demo")
    asyncio.run(run())

def test_provider_selection(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_demo")
    monkeypatch.setenv("APP_BASE_URL", "https://mecaconnect.example")
    assert isinstance(payment.get_payment_provider(), payment.StripeHttpProvider)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "")
    assert isinstance(payment.get_payment_provider(), payment.LocalStripeTestProvider)
