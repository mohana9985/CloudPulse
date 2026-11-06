from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    price: float
    category: str
    image_path: str
    stock_quantity: int
    in_stock: bool
    created_at: datetime


class ProductList(BaseModel):
    items: list[ProductOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class CategoryOut(BaseModel):
    name: str
    product_count: int
