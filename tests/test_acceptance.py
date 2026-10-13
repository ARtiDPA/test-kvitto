"""Five acceptance tests covering the required TZ scenarios."""

import asyncio
from uuid import uuid4

from sqlalchemy import func, select

from app.models import Payment

BASE = {"tariff_id": "standard", "email": "buyer@example.com", "method": "card"}
PRICES = {"basic": 990000, "standard": 1990000, "premium": 2990000}


async def payment_count(sessions):
    async with sessions() as session:
        return await session.scalar(select(func.count()).select_from(Payment))


async def test_amounts_and_promos(client, sessions):
    for tariff, price in PRICES.items():
        for method in ["card", "sbp"]:
            for promo in [None, "KVITTO10", "kvitto10"]:
                response = await client.post(
                    "/payments", json=BASE | dict(tariff_id=tariff, method=method, promo_code=promo)
                )
                assert response.status_code == 201
                body = response.json()
                discount = price // 10 if promo else 0
                assert body["amount"] == price - discount
                assert body["discount"] == discount
                assert body["status"] == "pending"
                assert body["schedule"] is None and body["installment_months"] is None
                stored = await client.get("/payments/" + body["id"])
                assert stored.status_code == 200 and stored.json() == body
    before = await payment_count(sessions)
    for change in [
        {"promo_code": "unknown"}, {"email": "invalid"}, {"method": "cash"},
        {"method": "installment"}, {"method": "installment", "installment_months": 4},
    ]:
        response = await client.post("/payments", json=BASE | change)
        assert response.status_code == 422
        assert isinstance(response.json()["detail"], list)
    assert await payment_count(sessions) == before


async def test_installment_schedules(client):
    for tariff, price in PRICES.items():
        for months in [3, 6, 12]:
            for promo in [None, "kvitto10"]:
                response = await client.post(
                    "/payments", json=BASE | dict(
                        tariff_id=tariff, method="installment",
                        installment_months=months, promo_code=promo,
                    )
                )
                assert response.status_code == 201
                body = response.json()
                assert body["amount"] == price - (price // 10 if promo else 0)
                assert body["installment_months"] == months
                schedule = body["schedule"]
                assert len(schedule) == months
                assert sum(schedule) == body["amount"]
                assert all(type(value) is int for value in schedule)
                assert max(schedule) - min(schedule) <= 1
                assert schedule == sorted(schedule, reverse=True)
                if tariff == "standard" and months == 3 and promo is None:
                    assert schedule == [663334, 663333, 663333]


async def test_idempotency(client, sessions):
    headers = {"Idempotency-Key": "repeat"}
    first = await client.post("/payments", json=BASE, headers=headers)
    second = await client.post("/payments", json=BASE, headers=headers)
    assert first.status_code == 201 and second.status_code == 200
    assert first.json() == second.json()
    assert await payment_count(sessions) == 1

    concurrent = await asyncio.gather(*[
        client.post("/payments", json=BASE, headers={"Idempotency-Key": "concurrent"})
        for _ in range(20)
    ])
    codes = [response.status_code for response in concurrent]
    assert codes.count(201) == 1 and codes.count(200) == 19
    assert len({response.json()["id"] for response in concurrent}) == 1
    assert await payment_count(sessions) == 2

    independent = [await client.post("/payments", json=BASE) for _ in range(2)]
    assert all(response.status_code == 201 for response in independent)
    assert independent[0].json()["id"] != independent[1].json()["id"]
    assert await payment_count(sessions) == 4


async def test_status_transitions(client):
    allowed = {("pending", "succeeded"), ("pending", "failed"), ("succeeded", "refunded")}
    statuses = ["pending", "succeeded", "failed", "refunded"]
    for old in statuses:
        for new in statuses:
            created = await client.post("/payments", json=BASE)
            assert created.status_code == 201
            payment_id = created.json()["id"]
            steps = {
                "pending": [], "succeeded": ["succeeded"], "failed": ["failed"],
                "refunded": ["succeeded", "refunded"],
            }[old]
            for step in steps:
                response = await client.post("/webhooks/bank", json={"payment_id": payment_id, "status": step})
                assert response.status_code == 200
            before = (await client.get("/payments/" + payment_id)).json()
            response = await client.post("/webhooks/bank", json={"payment_id": payment_id, "status": new})
            after = (await client.get("/payments/" + payment_id)).json()
            if (old, new) in allowed:
                assert response.status_code == 200 and response.json() == {"result": "ok"}
                assert after == before | {"status": new}
            else:
                assert response.status_code == 409
                assert response.json() == {"error": "invalid_transition"}
                assert after == before


async def test_missing_payments(client, sessions):
    missing = str(uuid4())
    assert (await client.get("/payments/" + missing)).status_code == 404
    for status in ["pending", "succeeded", "failed", "refunded"]:
        response = await client.post("/webhooks/bank", json={"payment_id": missing, "status": status})
        assert response.status_code == 404
    assert (await client.get("/payments/not-a-uuid")).status_code == 422
    assert await payment_count(sessions) == 0
