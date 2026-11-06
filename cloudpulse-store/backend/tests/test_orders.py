def test_create_order_success(client, valid_order):
    product_id = valid_order["items"][0]["product_id"]
    before = client.get(f"/api/products/{product_id}").json()

    response = client.post("/api/orders", json=valid_order)
    assert response.status_code == 201
    order = response.json()
    assert order["status"] == "CONFIRMED"
    assert order["customer_name"] == valid_order["customer_name"]
    subtotal = round(before["price"] * 2, 2)
    expected_shipping = 0.0 if subtotal >= 999 else 99.0
    assert order["subtotal"] == subtotal
    assert order["shipping_fee"] == expected_shipping
    assert order["total_amount"] == subtotal + expected_shipping
    assert order["items"][0]["product_name"] == before["name"]

    after = client.get(f"/api/products/{product_id}").json()
    assert after["stock_quantity"] == before["stock_quantity"] - 2


def test_get_order_by_id(client, valid_order):
    created = client.post("/api/orders", json=valid_order).json()
    response = client.get(f"/api/orders/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert len(response.json()["items"]) == 1


def test_get_unknown_order_returns_404(client):
    assert client.get("/api/orders/999999").status_code == 404


def test_list_recent_orders(client, valid_order):
    client.post("/api/orders", json=valid_order)
    response = client.get("/api/orders", params={"limit": 5})
    assert response.status_code == 200
    orders = response.json()
    assert 1 <= len(orders) <= 5
    ids = [o["id"] for o in orders]
    assert ids == sorted(ids, reverse=True)


def test_order_with_unknown_product_returns_404(client, valid_order):
    valid_order["items"] = [{"product_id": 999999, "quantity": 1}]
    response = client.post("/api/orders", json=valid_order)
    assert response.status_code == 404


def test_order_with_insufficient_stock_returns_409_and_rolls_back(client, valid_order):
    # Quantity per line is capped at 20, so drain the lowest-stock product with
    # repeated orders until less than 20 units remain.
    products = client.get("/api/products", params={"sort": "name"}).json()["items"]
    product = min(products, key=lambda p: p["stock_quantity"])
    second = next(p for p in products if p["id"] != product["id"])
    second_before = client.get(f"/api/products/{second['id']}").json()["stock_quantity"]

    remaining = product["stock_quantity"]
    while remaining >= 20:
        valid_order["items"] = [{"product_id": product["id"], "quantity": 20}]
        assert client.post("/api/orders", json=valid_order).status_code == 201
        remaining -= 20

    # The second product line would succeed on its own, but the first fails,
    # so the whole transaction must be rolled back.
    valid_order["items"] = [
        {"product_id": second["id"], "quantity": 1},
        {"product_id": product["id"], "quantity": remaining + 1},
    ]
    response = client.post("/api/orders", json=valid_order)
    assert response.status_code == 409
    assert "Insufficient stock" in response.json()["detail"]
    assert client.get(f"/api/products/{second['id']}").json()["stock_quantity"] == second_before


def test_order_validation_errors(client, valid_order):
    bad_email = {**valid_order, "email": "not-an-email"}
    assert client.post("/api/orders", json=bad_email).status_code == 422

    no_items = {**valid_order, "items": []}
    assert client.post("/api/orders", json=no_items).status_code == 422

    zero_qty = {**valid_order, "items": [{"product_id": 1, "quantity": 0}]}
    assert client.post("/api/orders", json=zero_qty).status_code == 422

    blank_name = {**valid_order, "customer_name": "   "}
    assert client.post("/api/orders", json=blank_name).status_code == 422

    duplicate = {**valid_order, "items": [{"product_id": 1, "quantity": 1}] * 2}
    assert client.post("/api/orders", json=duplicate).status_code == 422


def test_contact_submission(client):
    payload = {
        "name": "Asha Verma",
        "email": "asha@example.com",
        "subject": "Delivery question",
        "message": "When will my demonstration order arrive?",
    }
    response = client.post("/api/contact", json=payload)
    assert response.status_code == 201
    assert response.json()["id"] > 0


def test_contact_validation(client):
    response = client.post(
        "/api/contact",
        json={"name": "A", "email": "bad", "subject": "", "message": "short"},
    )
    assert response.status_code == 422


def test_small_order_pays_shipping(client, valid_order):
    products = client.get("/api/products", params={"sort": "price_asc"}).json()["items"]
    cheapest = products[0]
    assert cheapest["price"] < 999
    valid_order["items"] = [{"product_id": cheapest["id"], "quantity": 1}]
    order = client.post("/api/orders", json=valid_order).json()
    assert order["shipping_fee"] == 99.0
    assert order["total_amount"] == round(cheapest["price"] + 99.0, 2)


def test_timestamps_include_utc_offset(client, valid_order):
    order = client.post("/api/orders", json=valid_order).json()
    assert order["created_at"].endswith(("+00:00", "Z"))
    product = client.get("/api/products/1").json()
    assert product["created_at"].endswith(("+00:00", "Z"))
