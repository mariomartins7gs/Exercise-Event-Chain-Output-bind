from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class OrderItem(BaseModel):
    itemId: str
    name: str = Field(min_length=1, max_length=200)
    quantity: int = Field(ge=1, le=999)
    unitPrice: float = Field(ge=0)


class OrderPayload(BaseModel):
    customerName: str = Field(min_length=1, max_length=100)
    customerPhone: str = Field(pattern=r"^\+?[1-9]\d{6,14}$")
    items: list[OrderItem] = Field(min_length=1)
    total: float = Field(ge=0)
    tax: float = Field(ge=0)
    notes: Optional[str] = Field(None, max_length=500)


class CounterDocument(BaseModel):
    id: str = "orderCounter"
    currentValue: int = Field(default=0, ge=0)


class SmsRequest(BaseModel):
    phoneNumber: str
    message: str = Field(min_length=1, max_length=160)
    orderId: str


class SmsResult(BaseModel):
    messageId: str
    status: str
    errorMessage: Optional[str] = None


class OrderStatus(str, Enum):
    SUBMITTED = "submitted"
    VALIDATING = "validating"
    SMS_SENT = "sms_sent"
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    COMPLETED = "completed"
    EXPIRED = "expired"


class StatusUpdate(BaseModel):
    orderId: str
    status: OrderStatus
    timestamp: datetime
    details: Optional[str] = None


class FinalOrder(BaseModel):
    id: str
    instanceId: str
    displayId: int
    displayOrder: str
    customerName: str
    customerPhone: str
    items: list[OrderItem]
    total: float
    tax: float
    notes: Optional[str] = None
    status: OrderStatus
    timeline: list[StatusUpdate] = []
    createdAt: datetime
    expiresAt: Optional[datetime] = None
    confirmedAt: Optional[datetime] = None
    confirmationData: Optional[dict] = None


class OrderStatusResponse(BaseModel):
    orderId: str
    displayId: int
    displayOrder: str
    status: OrderStatus
    timeline: list[StatusUpdate]
    expiresAt: Optional[datetime] = None
    secondsRemaining: Optional[int] = None


class ExpiredOrder(BaseModel):
    PartitionKey: str
    RowKey: str
    orderId: str
    displayOrder: str
    customerName: str
    customerPhone: str
    total: float
    expiresAt: str
    reason: str = "Customer did not confirm within 3 minutes"
