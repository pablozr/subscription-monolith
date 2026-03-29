from datetime import date
from typing import TypedDict

from pydantic import BaseModel, Field


class PaymentHistoryCreateRequest(BaseModel):
    amount: float | None = Field(default=None, gt=0)
    paid_at: date | None = Field(default=None, alias="paidAt")
    payment_method: str | None = Field(default=None, alias="paymentMethod", min_length=2, max_length=50)
    reference: str | None = Field(default=None, min_length=1, max_length=120)
    notes: str | None = Field(default=None, max_length=500)

    model_config = {"populate_by_name": True}


class PaymentHistoryItem(TypedDict):
    id: int
    subscriptionId: int
    userId: int
    amount: float
    paidAt: str
    paymentMethod: str | None
    reference: str | None
    notes: str | None
    createdAt: str


class PaymentHistoryPagination(TypedDict):
    limit: int
    offset: int


class PaymentHistoryData(TypedDict, total=False):
    payments: list[PaymentHistoryItem]
    pagination: PaymentHistoryPagination


class PaymentHistoryListResponse(TypedDict):
    status: bool
    message: str
    data: PaymentHistoryData
