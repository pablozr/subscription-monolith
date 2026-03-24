from datetime import date
from typing import TypedDict
from pydantic import BaseModel, Field, field_validator


BILLING_CYCLE_VALUES = {"WEEKLY", "MONTHLY", "YEARLY"}


class SubscriptionCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    price: float = Field(gt=0)
    billing_cycle: str = Field(alias="billingCycle")
    start_date: date = Field(alias="startDate")
    reminder_days_before: int = Field(alias="reminderDaysBefore", ge=0)

    model_config = {"populate_by_name": True}

    @field_validator("billing_cycle")
    @classmethod
    def normalize_billing_cycle(cls, v: str) -> str:
        value = v.upper()
        if value not in BILLING_CYCLE_VALUES:
            raise ValueError(f"billing_cycle must be one of: {', '.join(BILLING_CYCLE_VALUES)}")
        return value


class SubscriptionUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    price: float | None = Field(default=None, gt=0)
    billing_cycle: str | None = Field(default=None, alias="billingCycle")
    status: str | None = None
    next_payment_date: date | None = Field(default=None, alias="nextPaymentDate")
    reminder_days_before: int | None = Field(default=None, alias="reminderDaysBefore", ge=0)

    model_config = {"populate_by_name": True}

    @field_validator("billing_cycle")
    @classmethod
    def normalize_billing_cycle(cls, v: str | None) -> str | None:
        return v.upper() if v else v

    @field_validator("status")
    @classmethod
    def normalize_status(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class SubscriptionGetDataResponse(TypedDict):
    id: int
    user_id: int
    name: str
    price: float
    billing_cycle: str
    status: str
    start_date: str
    next_payment_date: str
    reminder_days_before: int


class SubscriptionGetResponse(TypedDict):
    status: bool
    message: str
    data: dict[str, list[SubscriptionGetDataResponse] | SubscriptionGetDataResponse]
