from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class OrderItemCreate(BaseModel):
    product_id: int = Field(..., gt=0)
    quantity: int = Field(..., ge=1, le=20)


class OrderCreate(BaseModel):
    customer_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    address: str = Field(..., min_length=5, max_length=300)
    items: list[OrderItemCreate] = Field(..., min_length=1, max_length=20)

    @field_validator("customer_name", "address")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("must not be blank")
        return value

    @field_validator("items")
    @classmethod
    def unique_products(cls, items: list[OrderItemCreate]) -> list[OrderItemCreate]:
        ids = [item.product_id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("each product may appear only once; use quantity instead")
        return items


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    product_name: str
    image_path: str
    quantity: int
    unit_price: float
    line_total: float


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_name: str
    email: str
    address: str
    subtotal: float
    shipping_fee: float
    total_amount: float
    status: str
    created_at: datetime
    items: list[OrderItemOut]


class OrderSummary(BaseModel):
    id: int
    customer_name: str
    total_amount: float
    status: str
    item_count: int
    created_at: datetime
