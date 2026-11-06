import math

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database.models import Product

SORT_OPTIONS = {
    "price_asc": Product.price.asc(),
    "price_desc": Product.price.desc(),
    "name": Product.name.asc(),
    "newest": Product.id.desc(),
}


def to_dict(product: Product) -> dict:
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "price": product.price,
        "category": product.category,
        "image_path": product.image_path,
        "stock_quantity": product.stock_quantity,
        "in_stock": product.stock_quantity > 0,
        "created_at": product.created_at,
    }


def _search_filter(query: str):
    pattern = f"%{query.strip()}%"
    return or_(
        Product.name.ilike(pattern),
        Product.description.ilike(pattern),
        Product.category.ilike(pattern),
    )


def list_products(
    db: Session,
    category: str | None = None,
    q: str | None = None,
    sort: str = "name",
    page: int = 1,
    page_size: int = 100,
) -> dict:
    stmt = select(Product)
    if category:
        stmt = stmt.where(Product.category == category)
    if q and q.strip():
        stmt = stmt.where(_search_filter(q))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    order_by = SORT_OPTIONS.get(sort, SORT_OPTIONS["name"])
    rows = db.scalars(
        stmt.order_by(order_by, Product.id).offset((page - 1) * page_size).limit(page_size)
    ).all()

    return {
        "items": [to_dict(p) for p in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, math.ceil(total / page_size)),
    }


def search_products(db: Session, q: str, limit: int = 50) -> list[dict]:
    rows = db.scalars(
        select(Product).where(_search_filter(q)).order_by(Product.name).limit(limit)
    ).all()
    return [to_dict(p) for p in rows]


def get_product(db: Session, product_id: int) -> Product | None:
    return db.get(Product, product_id)


def list_categories(db: Session) -> list[dict]:
    rows = db.execute(
        select(Product.category, func.count(Product.id))
        .group_by(Product.category)
        .order_by(Product.category)
    ).all()
    return [{"name": name, "product_count": count} for name, count in rows]


def count_products(db: Session) -> int:
    return db.scalar(select(func.count(Product.id))) or 0
