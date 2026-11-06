import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Product

logger = logging.getLogger(__name__)

# (name, category, price, stock, image slug, description)
SEED_PRODUCTS = [
    ("Wireless Noise-Cancelling Headphones", "Electronics", 7999.00, 120, "wireless-headphones",
     "Over-ear Bluetooth 5.3 headphones with active noise cancellation, 30-hour battery life and a fold-flat travel design."),
    ("Mechanical Keyboard (TKL)", "Electronics", 4499.00, 150, "mechanical-keyboard",
     "Tenkeyless mechanical keyboard with tactile brown switches, white backlighting and a detachable USB-C cable."),
    ("27-inch QHD Monitor", "Electronics", 18999.00, 60, "qhd-monitor",
     "27-inch 2560x1440 IPS display with 75 Hz refresh rate, thin bezels and a height-adjustable stand."),
    ("Portable Power Bank 20000mAh", "Electronics", 1899.00, 300, "power-bank",
     "High-capacity power bank with 22.5 W fast charging, USB-C input/output and an LED charge indicator."),
    ("Stainless Steel Water Bottle 1L", "Home & Kitchen", 899.00, 400, "steel-bottle",
     "Double-wall vacuum insulated bottle that keeps drinks cold for 24 hours or hot for 12 hours."),
    ("Non-Stick Frying Pan 26cm", "Home & Kitchen", 1299.00, 200, "frying-pan",
     "Induction-compatible aluminium frying pan with a three-layer non-stick coating and a heat-resistant handle."),
    ("Electric Kettle 1.5L", "Home & Kitchen", 1599.00, 180, "electric-kettle",
     "1500 W stainless steel kettle with auto shut-off, boil-dry protection and a 360-degree swivel base."),
    ("Ceramic Dinner Set (16 pieces)", "Home & Kitchen", 3499.00, 80, "dinner-set",
     "Microwave- and dishwasher-safe ceramic set with four dinner plates, side plates, bowls and mugs."),
    ("Cloud Computing: Concepts and Practice", "Books", 649.00, 250, "book-cloud-computing",
     "An introductory textbook covering virtualisation, IaaS/PaaS/SaaS, scalability and cloud cost management."),
    ("Designing Reliable Web Systems", "Books", 799.00, 220, "book-reliable-systems",
     "A practical guide to monitoring, load balancing, caching and failure recovery for web applications."),
    ("Python for Data Engineers", "Books", 599.00, 260, "book-python-data",
     "Hands-on recipes for building data pipelines with Python, SQL and scheduled batch jobs."),
    ("Linux Command Line Handbook", "Books", 449.00, 300, "book-linux-cli",
     "A compact reference for shell navigation, process management, networking tools and shell scripting."),
    ("Yoga Mat 6mm", "Sports & Fitness", 999.00, 350, "yoga-mat",
     "Non-slip TPE yoga mat with alignment lines and a carry strap, suitable for yoga and floor workouts."),
    ("Adjustable Dumbbell Set 20kg", "Sports & Fitness", 3999.00, 90, "dumbbell-set",
     "Pair of adjustable dumbbells with cast-iron plates, chrome handles and secure spin-lock collars."),
    ("Running Shoes - Lightweight", "Sports & Fitness", 2799.00, 160, "running-shoes",
     "Breathable mesh running shoes with a cushioned EVA midsole and a durable rubber outsole."),
    ("Badminton Racket Pair", "Sports & Fitness", 1499.00, 140, "badminton-racket",
     "Two lightweight aluminium-frame rackets with pre-strung nylon and a padded carry cover."),
    ("Classic Cotton T-Shirt", "Fashion", 499.00, 500, "cotton-tshirt",
     "Regular-fit 100% cotton crew-neck T-shirt available in navy blue. Machine washable."),
    ("Denim Jacket", "Fashion", 2499.00, 110, "denim-jacket",
     "Mid-wash denim jacket with button front, chest pockets and a comfortable regular fit."),
    ("Leather Wallet", "Fashion", 999.00, 240, "leather-wallet",
     "Slim bi-fold genuine leather wallet with six card slots and a full-length note compartment."),
    ("Analog Wrist Watch", "Fashion", 3299.00, 100, "analog-watch",
     "Minimalist analog watch with a stainless steel case, mineral glass and a navy leather strap."),
    ("A5 Hardcover Notebook (Pack of 3)", "Office Supplies", 399.00, 450, "notebook-pack",
     "Three ruled A5 notebooks with 200 pages each, acid-free paper and an elastic closure band."),
    ("Ergonomic Office Chair", "Office Supplies", 8999.00, 50, "office-chair",
     "Mesh-back office chair with adjustable lumbar support, armrests and seat height."),
    ("Desk Organizer Set", "Office Supplies", 799.00, 210, "desk-organizer",
     "Five-piece metal mesh organizer with pen holder, letter tray, sticky-note holder and drawer."),
    ("Gel Pen Set (12 colours)", "Office Supplies", 249.00, 600, "gel-pens",
     "Smooth-writing 0.7 mm gel pens in twelve colours with comfortable rubber grips."),
]


def seed_products(db: Session) -> int:
    existing = db.scalar(select(func.count(Product.id)))
    if existing:
        logger.info("Products already present (%s); skipping seed", existing)
        return 0

    products = [
        Product(
            name=name,
            category=category,
            price=price,
            stock_quantity=stock,
            image_path=f"/products/{slug}.svg",
            description=description,
        )
        for name, category, price, stock, slug, description in SEED_PRODUCTS
    ]
    db.add_all(products)
    db.commit()
    logger.info("Seeded %s demo products", len(products))
    return len(products)
