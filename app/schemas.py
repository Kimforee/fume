from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


# Product Schemas
class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Product name")
    sku: str = Field(..., min_length=1, max_length=255, description="Product SKU (unique, case-insensitive)")
    description: Optional[str] = Field(None, description="Product description")
    active: bool = Field(True, description="Whether the product is active")


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    sku: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    active: Optional[bool] = None


class ProductResponse(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Webhook Schemas
class WebhookBase(BaseModel):
    url: str = Field(..., max_length=512, description="Webhook URL")
    event_types: List[str] = Field(..., description="List of event types to trigger webhook")
    enabled: bool = Field(True, description="Whether the webhook is enabled")

    @field_validator('event_types')
    @classmethod
    def validate_event_types(cls, v):
        valid_events = {'product.created', 'product.updated', 'product.deleted'}
        if not v:
            raise ValueError("event_types cannot be empty")
        invalid_events = set(v) - valid_events
        if invalid_events:
            raise ValueError(f"Invalid event types: {invalid_events}. Valid types: {valid_events}")
        return v


class WebhookCreate(WebhookBase):
    pass


class WebhookUpdate(BaseModel):
    url: Optional[str] = Field(None, max_length=512)
    event_types: Optional[List[str]] = None
    enabled: Optional[bool] = None

    @field_validator('event_types')
    @classmethod
    def validate_event_types(cls, v):
        if v is not None:
            valid_events = {'product.created', 'product.updated', 'product.deleted'}
            if not v:
                raise ValueError("event_types cannot be empty")
            invalid_events = set(v) - valid_events
            if invalid_events:
                raise ValueError(f"Invalid event types: {invalid_events}. Valid types: {valid_events}")
        return v


class WebhookResponse(WebhookBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Pagination Schemas
class PaginationParams(BaseModel):
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")


class ProductListResponse(BaseModel):
    items: List[ProductResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# Task Progress Schemas
class TaskProgressResponse(BaseModel):
    task_id: str
    status: str  # pending, processing, completed, failed
    progress: float = Field(0.0, ge=0.0, le=100.0, description="Progress percentage")
    total_rows: Optional[int] = None
    processed_rows: int = 0
    successful_rows: int = 0
    failed_rows: int = 0
    errors: List[str] = []
    message: Optional[str] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# CSV Upload Response
class UploadResponse(BaseModel):
    task_id: str
    message: str
    filename: str

