import random

from locust import HttpUser, between, events, task

# Filled once at test start from the live API so scripts never rely on
# hard-coded IDs. Fallbacks are used only if the API is unreachable.
CATALOG = {"product_ids": list(range(1, 21)), "categories": ["Books", "Electronics"]}

SEARCH_TERMS = [
    "headphones", "keyboard", "bottle", "book", "cloud", "python", "shoes",
    "watch", "chair", "pen", "yoga", "kettle", "linux", "monitor", "jacket",
]
SORT_OPTIONS = ["name", "price_asc", "price_desc", "newest"]
FIRST_NAMES = ["Aarav", "Diya", "Kabir", "Meera", "Rohan", "Ananya", "Vikram", "Isha"]
CITIES = ["Pilani", "Jaipur", "Hyderabad", "Goa", "Pune", "Chennai", "Delhi", "Mumbai"]


@events.test_start.add_listener
def load_catalog(environment, **_kwargs):
    host = environment.host or "http://localhost"
    import urllib.request
    import json

    try:
        with urllib.request.urlopen(f"{host}/api/products?page_size=100", timeout=10) as resp:
            items = json.load(resp)["items"]
        with urllib.request.urlopen(f"{host}/api/categories", timeout=10) as resp:
            categories = [c["name"] for c in json.load(resp)]
        if items:
            CATALOG["product_ids"] = [p["id"] for p in items]
        if categories:
            CATALOG["categories"] = categories
        print(f"[locust] catalog loaded: {len(CATALOG['product_ids'])} products, "
              f"{len(CATALOG['categories'])} categories")
    except Exception as exc:  # pragma: no cover - only when the site is down
        print(f"[locust] WARNING: could not load catalog from {host}: {exc}")


def random_product_id() -> int:
    return random.choice(CATALOG["product_ids"])


def random_customer() -> dict:
    name = random.choice(FIRST_NAMES)
    return {
        "customer_name": f"{name} Loadtest",
        "email": f"{name.lower()}.{random.randint(1, 99999)}@example.com",
        "address": f"{random.randint(1, 999)} Demo Road, {random.choice(CITIES)}, India",
    }


def open_homepage(user):
    user.client.get("/", name="/ (homepage)")
    user.client.get("/api/products?sort=newest&page_size=8", name="/api/products (featured)")
    user.client.get("/api/categories")


def browse_products(user):
    user.client.get("/products", name="/products (page)")
    user.client.get("/api/products", name="/api/products (all)")


def view_product(user):
    pid = random_product_id()
    user.client.get(f"/products/{pid}", name="/products/[id] (page)")
    user.client.get(f"/api/products/{pid}", name="/api/products/[id]")


def search(user):
    term = random.choice(SEARCH_TERMS)
    user.client.get(f"/api/products/search?q={term}", name="/api/products/search")


def filter_listing(user):
    params = f"category={random.choice(CATALOG['categories'])}&sort={random.choice(SORT_OPTIONS)}"
    user.client.get(f"/api/products?{params}", name="/api/products (filtered)")


def place_order(user):
    count = min(len(CATALOG["product_ids"]), random.randint(1, 3))
    items = [
        {"product_id": pid, "quantity": random.randint(1, 2)}
        for pid in random.sample(CATALOG["product_ids"], count)
    ]
    payload = {**random_customer(), "items": items}

    with user.client.post("/api/orders", json=payload, name="/api/orders (create)",
                          catch_response=True) as resp:
        if resp.status_code == 201:
            order_id = resp.json()["id"]
            resp.success()
            user.client.get(f"/api/orders/{order_id}", name="/api/orders/[id]")
        elif resp.status_code == 409:
            # Stock ran out after many orders: a valid business response, not a server fault.
            resp.success()
        else:
            resp.failure(f"unexpected status {resp.status_code}: {resp.text[:200]}")


class BrowsingUser(HttpUser):
    wait_time = between(1, 3)
    weight = 1

    @task(3)
    def homepage(self):
        open_homepage(self)

    @task(4)
    def product_list(self):
        browse_products(self)

    @task(5)
    def product_details(self):
        view_product(self)


class SearchUser(HttpUser):
    wait_time = between(1, 3)
    weight = 1

    @task(5)
    def search_products(self):
        search(self)

    @task(2)
    def categories(self):
        self.client.get("/api/categories")

    @task(4)
    def filtered_listing(self):
        filter_listing(self)


class OrderUser(HttpUser):
    # The cart lives in browser localStorage, so 'add to cart' sends no request.

    wait_time = between(2, 5)
    weight = 1

    @task
    def checkout_flow(self):
        view_product(self)
        view_product(self)
        self.client.get("/checkout", name="/checkout (page)")
        place_order(self)


class MixedWorkloadUser(HttpUser):
    wait_time = between(1, 4)
    weight = 4

    @task(3)
    def homepage(self):
        open_homepage(self)

    @task(3)
    def product_list(self):
        browse_products(self)

    @task(3)
    def searching(self):
        search(self)

    @task(4)
    def product_details(self):
        view_product(self)

    @task(1)
    def health(self):
        self.client.get("/api/health")

    @task(1)
    def order(self):
        place_order(self)
