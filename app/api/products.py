from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import selectinload
from typing import Optional
from app.database import get_db
from app.models.product import Product
from app.schemas import (
    ProductCreate, ProductUpdate, ProductResponse, ProductListResponse, PaginationParams
)
from app.utils.webhook_trigger import trigger_webhooks
import math

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sku: Optional[str] = Query(None, description="Filter by SKU (case-insensitive)"),
    name: Optional[str] = Query(None, description="Filter by name (partial match)"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
    description: Optional[str] = Query(None, description="Filter by description (partial match)"),
    db: AsyncSession = Depends(get_db)
):
    """List products with pagination and filtering."""
    # Build query
    query = select(Product)
    conditions = []
    
    if sku:
        conditions.append(func.lower(Product.sku) == func.lower(sku))
    if name:
        conditions.append(Product.name.ilike(f"%{name}%"))
    if active is not None:
        conditions.append(Product.active == active)
    if description:
        conditions.append(Product.description.ilike(f"%{description}%"))
    
    if conditions:
        query = query.where(and_(*conditions))
    
    # Get total count
    count_query = select(func.count()).select_from(Product)
    if conditions:
        count_query = count_query.where(and_(*conditions))
    
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(Product.id.desc()).offset(offset).limit(page_size)
    
    # Execute query
    result = await db.execute(query)
    products = result.scalars().all()
    
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    
    return ProductListResponse(
        items=[ProductResponse.model_validate(p) for p in products],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single product by ID."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    return ProductResponse.model_validate(product)


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(product: ProductCreate, db: AsyncSession = Depends(get_db)):
    """Create a new product."""
    # Check for duplicate SKU (case-insensitive)
    existing = await db.execute(
        select(Product).where(func.lower(Product.sku) == func.lower(product.sku))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail=f"Product with SKU '{product.sku}' already exists (case-insensitive)"
        )
    
    # Create product
    db_product = Product(
        name=product.name,
        sku=product.sku,
        description=product.description,
        active=product.active
    )
    
    db.add(db_product)
    await db.commit()
    await db.refresh(db_product)
    
    # Trigger webhook
    await trigger_webhooks("product.created", db_product, db)
    
    return ProductResponse.from_orm(db_product)


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product_update: ProductUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update an existing product."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    db_product = result.scalar_one_or_none()
    
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Check for duplicate SKU if SKU is being updated
    if product_update.sku and product_update.sku.lower() != db_product.sku.lower():
        existing = await db.execute(
            select(Product).where(
                and_(
                    func.lower(Product.sku) == func.lower(product_update.sku),
                    Product.id != product_id
                )
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail=f"Product with SKU '{product_update.sku}' already exists (case-insensitive)"
            )
    
    # Update fields
    update_data = product_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_product, field, value)
    
    await db.commit()
    await db.refresh(db_product)
    
    # Trigger webhook
    await trigger_webhooks("product.updated", db_product, db)
    
    return ProductResponse.from_orm(db_product)


@router.delete("/{product_id}", status_code=204)
async def delete_product(product_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a single product."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    await db.delete(product)
    await db.commit()
    
    # Trigger webhook
    await trigger_webhooks("product.deleted", product, db)
    
    return None


@router.delete("/bulk", status_code=200)
async def bulk_delete_products(db: AsyncSession = Depends(get_db)):
    """Delete all products. Returns count of deleted products."""
    result = await db.execute(select(Product))
    products = result.scalars().all()
    
    count = len(products)
    
    for product in products:
        await db.delete(product)
    
    await db.commit()
    
    return {"message": f"Deleted {count} products", "deleted_count": count}

