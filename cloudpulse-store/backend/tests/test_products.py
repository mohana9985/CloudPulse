def test_list_products_returns_seeded_data(client):
    response = client.get("/api/products")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 20
    assert len(body["items"]) == body["total"]
    first = body["items"][0]
    for key in ("id", "name", "description", "price", "category", "image_path",
                "stock_quantity", "in_stock", "created_at"):
        assert key in first


def test_filter_by_category(client):
    body = client.get("/api/products", params={"category": "Books"}).json()
    assert body["total"] > 0
    assert all(p["category"] == "Books" for p in body["items"])


def test_sort_by_price(client):
    asc = [p["price"] for p in client.get("/api/products", params={"sort": "price_asc"}).json()["items"]]
    desc = [p["price"] for p in client.get("/api/products", params={"sort": "price_desc"}).json()["items"]]
    assert asc == sorted(asc)
    assert desc == sorted(desc, reverse=True)


def test_pagination(client):
    body = client.get("/api/products", params={"page": 2, "page_size": 5}).json()
    assert body["page"] == 2
    assert body["page_size"] == 5
    assert len(body["items"]) == 5
    assert body["total_pages"] == -(-body["total"] // 5)


def test_invalid_sort_is_rejected(client):
    assert client.get("/api/products", params={"sort": "random"}).status_code == 422


def test_get_product_by_id(client):
    product = client.get("/api/products").json()["items"][0]
    response = client.get(f"/api/products/{product['id']}")
    assert response.status_code == 200
    assert response.json()["name"] == product["name"]


def test_get_unknown_product_returns_404(client):
    response = client.get("/api/products/999999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_get_product_with_non_integer_id_returns_422(client):
    assert client.get("/api/products/abc").status_code == 422


def test_categories(client):
    response = client.get("/api/categories")
    assert response.status_code == 200
    categories = response.json()
    names = {c["name"] for c in categories}
    assert {"Electronics", "Books", "Fashion"} <= names
    assert sum(c["product_count"] for c in categories) >= 20


def test_search_finds_products(client):
    response = client.get("/api/products/search", params={"q": "keyboard"})
    assert response.status_code == 200
    results = response.json()
    assert len(results) >= 1
    assert any("Keyboard" in p["name"] for p in results)


def test_search_is_case_insensitive(client):
    upper = client.get("/api/products/search", params={"q": "BOOK"}).json()
    lower = client.get("/api/products/search", params={"q": "book"}).json()
    assert len(upper) == len(lower) > 0


def test_search_without_query_returns_422(client):
    assert client.get("/api/products/search").status_code == 422


def test_search_with_no_matches_returns_empty_list(client):
    assert client.get("/api/products/search", params={"q": "zzzz-no-match"}).json() == []
