from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.product import CategoryOut, ProductList, ProductOut
from app.services import product_service

router = APIRouter(prefix="/api", tags=["Products"])


@router.get("/products", response_model=ProductList)
def list_products(
    category: str | None = Query(None, max_length=80, description="Exact category name"),
    q: str | None = Query(None, max_length=100, description="Optional text filter"),
    sort: Literal["name", "price_asc", "price_desc", "newest"] = "name",
    page: int = Query(1, ge=1, le=1000),
    page_size: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return product_service.list_products(db, category, q, sort, page, page_size)


# Declared before /products/{product_id} so "search" is not parsed as an ID.
@router.get("/products/search", response_model=list[ProductOut])
def search_products(
    q: str = Query(..., min_length=1, max_length=100, description="Search text"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return product_service.search_products(db, q, limit)


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = product_service.get_product(db, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return product_service.to_dict(product)


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return product_service.list_categories(db)
