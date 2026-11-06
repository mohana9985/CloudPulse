import logging

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.database.models import Order, OrderItem, Product
from app.schemas.order import OrderCreate

logger = logging.getLogger(__name__)

# Demo shipping rule (mirrored in frontend/src/utils/format.js):
# free shipping when the subtotal reaches FREE_SHIPPING_THRESHOLD, otherwise a flat fee.
FREE_SHIPPING_THRESHOLD = 999.0
SHIPPING_FEE = 99.0


def shipping_for(subtotal: float) -> float:
    return 0.0 if subtotal >= FREE_SHIPPING_THRESHOLD else SHIPPING_FEE


class OrderError(Exception):
    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ProductNotFoundError(OrderError):
    status_code = 404


class InsufficientStockError(OrderError):
    status_code = 409


def create_order(db: Session, payload: OrderCreate) -> Order:
    try:
        product_ids = [item.product_id for item in payload.items]
        products = {
            p.id: p for p in db.scalars(select(Product).where(Product.id.in_(product_ids)))
        }

        missing = [pid for pid in product_ids if pid not in products]
        if missing:
            raise ProductNotFoundError(f"Product(s) not found: {missing}")

        order = Order(
            customer_name=payload.customer_name,
            email=str(payload.email),
            address=payload.address,
            total_amount=0,
            status="CONFIRMED",
        )
        total = 0.0

        for item in payload.items:
            product = products[item.product_id]
            result = db.execute(
                update(Product)
                .where(Product.id == product.id, Product.stock_quantity >= item.quantity)
                .values(stock_quantity=Product.stock_quantity - item.quantity)
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                raise InsufficientStockError(
                    f"Insufficient stock for '{product.name}' "
                    f"(requested {item.quantity}, available {product.stock_quantity})"
                )
            order.items.append(
                OrderItem(product_id=product.id, quantity=item.quantity, unit_price=product.price)
            )
            total += product.price * item.quantity

        order.total_amount = round(total + shipping_for(total), 2)
        db.add(order)
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(order)
    logger.info("Created order %s (total %.2f)", order.id, order.total_amount)
    return order


def order_to_dict(order: Order) -> dict:
    subtotal = round(sum(i.unit_price * i.quantity for i in order.items), 2)
    return {
        "id": order.id,
        "customer_name": order.customer_name,
        "email": order.email,
        "address": order.address,
        "subtotal": subtotal,
        "shipping_fee": round(order.total_amount - subtotal, 2),
        "total_amount": order.total_amount,
        "status": order.status,
        "created_at": order.created_at,
        "items": [
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_name": item.product.name,
                "image_path": item.product.image_path,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "line_total": round(item.unit_price * item.quantity, 2),
            }
            for item in order.items
        ],
    }


def get_order(db: Session, order_id: int) -> Order | None:
    return db.get(Order, order_id)


def list_recent_orders(db: Session, limit: int = 20) -> list[dict]:
    orders = db.scalars(select(Order).order_by(Order.id.desc()).limit(limit)).all()
    return [
        {
            "id": o.id,
            "customer_name": o.customer_name,
            "total_amount": o.total_amount,
            "status": o.status,
            "item_count": sum(i.quantity for i in o.items),
            "created_at": o.created_at,
        }
        for o in orders
    ]


def count_orders(db: Session) -> int:
    return db.scalar(select(func.count(Order.id))) or 0
