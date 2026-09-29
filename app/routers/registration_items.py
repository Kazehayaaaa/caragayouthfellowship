"""Routes: registration items."""

from fastapi import Depends
from fastapi import HTTPException
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import APIRouter

from app.database import (
    get_db,
)
from app.models import (
    RegistrationItem,
)
from app.schemas import (
    RegistrationItemCreate,
    RegistrationItemResponse,
    RegistrationItemUpdate,
)

router = APIRouter()

# ============================================================
# CREATE REGISTRATION ITEM
# ============================================================

@router.post(
    "/registration/items",
    response_model=RegistrationItemResponse
)
def create_registration_item(
    data: RegistrationItemCreate,
    db: Session = Depends(get_db)
):

    item_name = data.item_name.strip()

    if not item_name:
        raise HTTPException(
            status_code=400,
            detail="Item name is required."
        )

    if data.price < 0:
        raise HTTPException(
            status_code=400,
            detail="Price cannot be negative."
        )

    # --------------------------------------------------------
    # CHECK DUPLICATE ITEM NAME
    # --------------------------------------------------------

    existing_item = (
        db.query(RegistrationItem)
        .filter(
            func.lower(
                RegistrationItem.item_name
            ) == item_name.lower()
        )
        .first()
    )

    if existing_item:

        raise HTTPException(
            status_code=400,
            detail="Registration item already exists."
        )

    # --------------------------------------------------------
    # CREATE
    # --------------------------------------------------------

    item = RegistrationItem(

        item_name=item_name,

        price=data.price,

        is_active=True

    )

    db.add(item)

    db.commit()

    db.refresh(item)

    return item


# ============================================================
# VIEW ALL REGISTRATION ITEMS
# ============================================================

@router.get(
    "/registration/items",
    response_model=List[RegistrationItemResponse]
)
def view_all_registration_items(
    db: Session = Depends(get_db)
):

    items = (
        db.query(RegistrationItem)
        .order_by(
            RegistrationItem.item_name.asc()
        )
        .all()
    )

    return items

# ============================================================
# VIEW ACTIVE REGISTRATION ITEMS
# ============================================================

@router.get(
    "/registration/items/active",
    response_model=List[RegistrationItemResponse]
)
def view_active_registration_items(
    db: Session = Depends(get_db)
):

    items = (
        db.query(RegistrationItem)
        .filter(
            RegistrationItem.is_active == True
        )
        .order_by(
            RegistrationItem.item_name.asc()
        )
        .all()
    )

    return items

# ============================================================
# VIEW SINGLE REGISTRATION ITEM
# ============================================================

@router.get(
    "/registration/items/{item_id}",
    response_model=RegistrationItemResponse
)
def view_single_registration_item(
    item_id: int,
    db: Session = Depends(get_db)
):

    item = (
        db.query(RegistrationItem)
        .filter(
            RegistrationItem.id == item_id
        )
        .first()
    )

    if not item:

        raise HTTPException(
            status_code=404,
            detail="Registration item not found."
        )

    return item

# ============================================================
# UPDATE REGISTRATION ITEM
# ============================================================

@router.put(
    "/registration/items/{item_id}",
    response_model=RegistrationItemResponse
)
def update_registration_item(
    item_id: int,
    data: RegistrationItemUpdate,
    db: Session = Depends(get_db)
):

    item = (
        db.query(RegistrationItem)
        .filter(
            RegistrationItem.id == item_id
        )
        .first()
    )

    if not item:

        raise HTTPException(
            status_code=404,
            detail="Registration item not found."
        )

    # --------------------------------------------------------
    # UPDATE NAME
    # --------------------------------------------------------

    if data.item_name is not None:

        item_name = data.item_name.strip()

        if not item_name:

            raise HTTPException(
                status_code=400,
                detail="Item name cannot be empty."
            )

        duplicate = (
            db.query(RegistrationItem)
            .filter(
                RegistrationItem.id != item_id,
                func.lower(
                    RegistrationItem.item_name
                ) == item_name.lower()
            )
            .first()
        )

        if duplicate:

            raise HTTPException(
                status_code=400,
                detail="Another registration item already uses this name."
            )

        item.item_name = item_name

    # --------------------------------------------------------
    # UPDATE PRICE
    # --------------------------------------------------------

    if data.price is not None:

        if data.price < 0:

            raise HTTPException(
                status_code=400,
                detail="Price cannot be negative."
            )

        item.price = data.price

    # --------------------------------------------------------
    # UPDATE ACTIVE STATUS
    # --------------------------------------------------------

    if data.is_active is not None:

        item.is_active = data.is_active

    db.commit()

    db.refresh(item)

    return item

# ============================================================
# DEACTIVATE REGISTRATION ITEM
# ============================================================

@router.delete(
    "/registration/items/{item_id}"
)
def deactivate_registration_item(
    item_id: int,
    db: Session = Depends(get_db)
):

    item = (
        db.query(RegistrationItem)
        .filter(
            RegistrationItem.id == item_id
        )
        .first()
    )

    if not item:

        raise HTTPException(
            status_code=404,
            detail="Registration item not found."
        )

    item.is_active = False

    db.commit()

    return {

        "success": True,

        "message":
            "Registration item deactivated.",

        "item_id":
            item.id

    }
    
    
# ============================================================
# ACTIVATE REGISTRATION ITEM
# ============================================================

@router.put(
    "/registration/items/{item_id}/activate"
)
def activate_registration_item(
    item_id: int,
    db: Session = Depends(get_db)
):

    item = (
        db.query(RegistrationItem)
        .filter(
            RegistrationItem.id == item_id
        )
        .first()
    )

    if not item:

        raise HTTPException(
            status_code=404,
            detail="Registration item not found."
        )

    item.is_active = True

    db.commit()

    return {

        "success": True,

        "message":
            "Registration item activated.",

        "item_id":
            item.id

    }
    

# ============================================================
# GET ACTIVE REGISTRATION ITEMS
# ============================================================

@router.get("/registration_items")
def get_registration_items(
    db: Session = Depends(get_db)
):

    items = (
        db.query(RegistrationItem)
        .filter(
            RegistrationItem.is_active == True
        )
        .order_by(
            RegistrationItem.id.asc()
        )
        .all()
    )

    result = []

    for item in items:

        result.append({

            "id":
                item.id,

            "item_name":
                item.item_name,

            # Database value is stored in centavos
            "price":
                item.price,

            "price_display":
                f"₱{item.price / 100:,.2f}",

            "is_active":
                item.is_active
        })

    return result
