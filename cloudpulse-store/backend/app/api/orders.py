from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.metrics import ORDERS_CREATED_TOTAL
from app.database.connection import get_db
from app.schemas.order import OrderCreate, OrderOut, OrderSummary
from app.services import order_service

router = APIRouter(prefix="/api", tags=["Orders"])


@router.post("/orders", response_model=OrderOut, status_code=201)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    try:
        order = order_service.create_order(db, payload)
    except order_service.OrderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    ORDERS_CREATED_TOTAL.inc()
    return order_service.order_to_dict(order)


@router.get("/orders", response_model=list[OrderSummary])
def list_orders(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return order_service.list_recent_orders(db, limit)


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = order_service.get_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    return order_service.order_to_dict(order)
