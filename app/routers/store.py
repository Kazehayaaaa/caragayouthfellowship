"""Routes: store."""

from fastapi import Depends
from fastapi import File
from fastapi import HTTPException
from pathlib import Path
from sqlalchemy.orm import Session
from fastapi import UploadFile
import datetime
import httpx
import json
import shutil
import uuid
from fastapi import APIRouter

from app.config import (
    PAYMONGO_SECRET_KEY,
)
from app.database import (
    get_db,
)
from app.models import (
    Payment,
    StoreItem,
)
from app.schemas import (
    StoreItemCreateSchema,
    StoreItemUpdateSchema,
    StorePurchaseSchema,
)

router = APIRouter()

# ============================================================
# HELPER - STORE ITEM RESPONSE
# ============================================================

# ============================================================
# HELPER - STORE ITEM RESPONSE
# ============================================================

def store_item_response(item):

    item_sizes = []

    if item.sizes:

        try:
            item_sizes = json.loads(item.sizes)

        except Exception:
            item_sizes = []

    return {
        "id": item.id,
        "item_name": item.item_name,
        "description": item.description,
        "category": item.category,
        "quantity": item.quantity,
        "price": item.price,
        "image_url": item.image_url,
        "sizes": item_sizes,
        "available": item.quantity > 0,
        "is_archived": bool(item.is_archived),
        "created_at": item.created_at,
        "updated_at": item.updated_at
    }

# ============================================================
# VIEW ACTIVE STORE
# ============================================================

@router.get("/store")
def view_store(
    db: Session = Depends(get_db)
):

    items = (
        db.query(StoreItem)
        .filter(
            StoreItem.is_archived == False
        )
        .order_by(
            StoreItem.created_at.desc()
        )
        .all()
    )

    return {
        "success": True,
        "items": [
            store_item_response(item)
            for item in items
        ]
    }


# ============================================================
# GET STORE CATEGORIES
# ============================================================

@router.get("/store/categories")
def get_store_categories():

    return {
        "success": True,
        "categories": STORE_CATEGORIES
    }
    
    
    
# ============================================================
# STORE CATEGORIES / SIZES
# ============================================================

STORE_CATEGORIES = [
    "clothes",
    "souvenir",
    "others"
]

STORE_CLOTHING_SIZES = [
    "S",
    "M",
    "L",
    "XL",
    "2XL"
]    


# ============================================================
# CREATE STORE ITEM
# ============================================================

@router.post("/create_store_item")
def create_store_item(
    data: StoreItemCreateSchema,
    db: Session = Depends(get_db)
):

    item_name = (
        data.item_name.strip()
        if data.item_name
        else ""
    )

    if not item_name:
        raise HTTPException(
            status_code=400,
            detail="Item name is required."
        )

    category = (
        data.category.strip().lower()
        if data.category
        else ""
    )

    if category not in STORE_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid store item category. "
                "Allowed categories: "
                + ", ".join(STORE_CATEGORIES)
            )
        )

    if data.quantity < 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity cannot be negative."
        )

    if data.price <= 0:
        raise HTTPException(
            status_code=400,
            detail="Price must be greater than zero."
        )

    # --------------------------------------------------------
    # CLOTHING SIZES
    # --------------------------------------------------------

    sizes = []

    if category == "clothes":

        sizes = data.sizes or []

        sizes = [
            size.strip().upper()
            for size in sizes
            if size and size.strip()
        ]

        if not sizes:
            sizes = STORE_CLOTHING_SIZES

        invalid_sizes = [
            size
            for size in sizes
            if size not in STORE_CLOTHING_SIZES
        ]

        if invalid_sizes:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid clothing size(s): "
                    + ", ".join(invalid_sizes)
                    + ". Allowed sizes: "
                    + ", ".join(STORE_CLOTHING_SIZES)
                )
            )

    else:

        # Souvenir / Others do not need sizes
        sizes = []

    # --------------------------------------------------------
    # CREATE
    # --------------------------------------------------------

    now = datetime.datetime.now()

    item = StoreItem(
        item_name=item_name,

        description=(
            data.description.strip()
            if data.description
            else None
        ),

        category=category,

        quantity=data.quantity,

        price=data.price,

        image_url=(
            data.image_url.strip()
            if data.image_url
            else None
        ),

        sizes=json.dumps(sizes),

        is_archived=False,

        created_at=now,

        updated_at=now
    )

    db.add(item)

    db.commit()

    db.refresh(item)

    return {
        "success": True,
        "message": "Store item created successfully.",
        "item": store_item_response(item)
    }


# ============================================================
# UPDATE STORE ITEM
# ============================================================

@router.put("/update_store_item/{item_id}")
def update_store_item(
    item_id: int,
    data: StoreItemUpdateSchema,
    db: Session = Depends(get_db)
):

    item = (
        db.query(StoreItem)
        .filter(
            StoreItem.id == item_id,
            StoreItem.is_archived == False
        )
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Store item not found."
        )

    item_name = (
        data.item_name.strip()
        if data.item_name
        else ""
    )

    if not item_name:
        raise HTTPException(
            status_code=400,
            detail="Item name is required."
        )

    category = (
        data.category.strip().lower()
        if data.category
        else ""
    )

    if category not in STORE_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid store item category. "
                "Allowed categories: "
                + ", ".join(STORE_CATEGORIES)
            )
        )

    if data.quantity < 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity cannot be negative."
        )

    if data.price <= 0:
        raise HTTPException(
            status_code=400,
            detail="Price must be greater than zero."
        )

    # --------------------------------------------------------
    # SIZES
    # --------------------------------------------------------

    sizes = []

    if category == "clothes":

        sizes = data.sizes or []

        sizes = [
            size.strip().upper()
            for size in sizes
            if size and size.strip()
        ]

        if not sizes:
            sizes = STORE_CLOTHING_SIZES

        invalid_sizes = [
            size
            for size in sizes
            if size not in STORE_CLOTHING_SIZES
        ]

        if invalid_sizes:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid clothing size(s): "
                    + ", ".join(invalid_sizes)
                )
            )

    # --------------------------------------------------------
    # UPDATE
    # --------------------------------------------------------

    item.item_name = item_name

    item.description = (
        data.description.strip()
        if data.description
        else None
    )

    item.category = category

    item.quantity = data.quantity

    item.price = data.price

    item.image_url = (
        data.image_url.strip()
        if data.image_url
        else None
    )

    item.sizes = json.dumps(sizes)

    item.updated_at = datetime.datetime.now()

    db.commit()

    db.refresh(item)

    return {
        "success": True,
        "message": "Store item updated successfully.",
        "item": store_item_response(item)
    }


# ============================================================
# ARCHIVE STORE ITEM
# ============================================================

@router.delete("/delete_store_item/{item_id}")
def delete_store_item(
    item_id: int,
    db: Session = Depends(get_db)
):

    item = (
        db.query(StoreItem)
        .filter(
            StoreItem.id == item_id,
            StoreItem.is_archived == False
        )
        .first()
    )

    if not item:

        raise HTTPException(
            status_code=404,
            detail="Store item not found."
        )

    item.is_archived = True

    item.updated_at = datetime.datetime.now()

    db.commit()

    return {

        "success": True,

        "message":
            "Store item archived successfully.",

        "item_id":
            item.id

    }
    
















# ============================================================
# CREATE STORE PURCHASE PAYMENT
#
# SUPPORTS:
# - ONE ITEM
# - MULTIPLE ITEMS
# - 1 TO 50 CART ITEMS
#
# ONE CART = ONE PAYMONGO PAYMENT LINK
# ONE CART ITEM = ONE PAYMENT DATABASE ROW
# ALL PAYMENT ROWS SHARE THE SAME store_order_id
# ============================================================

@router.post("/store/purchase")
def create_store_purchase(
    data: StorePurchaseSchema,
    db: Session = Depends(get_db)
):

    # ========================================================
    # VALIDATE CUSTOMER
    # ========================================================

    customer_name = (
        data.customer_name or ""
    ).strip()

    customer_contact = (
        data.customer_contact or ""
    ).strip()

    customer_email = (
        str(data.customer_email or "")
    ).strip()

    if not customer_name:

        raise HTTPException(
            status_code=400,
            detail="Customer name is required."
        )

    if not customer_contact:

        raise HTTPException(
            status_code=400,
            detail="Customer contact number is required."
        )

    if not customer_email:

        raise HTTPException(
            status_code=400,
            detail="Customer email is required."
        )

    # ========================================================
    # VALIDATE CART
    # ========================================================

    if not data.items:

        raise HTTPException(
            status_code=400,
            detail="Your cart is empty."
        )

    # ========================================================
    # MAXIMUM CART ITEMS
    #
    # Supports 1 to 50 items.
    # Change 50 if you want a different maximum.
    # ========================================================

    if len(data.items) > 50:

        raise HTTPException(
            status_code=400,
            detail="Too many items in the cart."
        )

    # ========================================================
    # ALLOWED CATEGORIES
    # ========================================================

    allowed_categories = {
        "clothes",
        "souvenir",
        "others"
    }

    default_clothing_sizes = [
        "S",
        "M",
        "L",
        "XL",
        "2XL"
    ]

    # ========================================================
    # PREPARE
    # ========================================================

    validated_items = []

    total_php = 0.0

    # ========================================================
    # VALIDATE EVERY CART ITEM
    # ========================================================

    for cart_item in data.items:

        # ----------------------------------------------------
        # QUANTITY
        # ----------------------------------------------------

        if cart_item.quantity <= 0:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid quantity for "
                    f"store item #{cart_item.store_item_id}."
                )
            )

        # ----------------------------------------------------
        # FIND ITEM
        # ----------------------------------------------------

        item = (
            db.query(StoreItem)
            .filter(
                StoreItem.id == cart_item.store_item_id,
                StoreItem.is_archived == False
            )
            .first()
        )

        if not item:

            raise HTTPException(
                status_code=404,
                detail=(
                    f"Store item "
                    f"#{cart_item.store_item_id} "
                    f"was not found."
                )
            )

        # ----------------------------------------------------
        # CATEGORY
        # ----------------------------------------------------

        category = (
            item.category or "others"
        ).strip().lower()

        if category not in allowed_categories:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid category for "
                    f"{item.item_name}."
                )
            )

        # ----------------------------------------------------
        # INVENTORY
        # ----------------------------------------------------

        current_quantity = int(
            item.quantity or 0
        )

        if current_quantity <= 0:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"{item.item_name} "
                    f"is currently out of stock."
                )
            )

        if cart_item.quantity > current_quantity:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Only {current_quantity} "
                    f"item(s) of "
                    f"{item.item_name} "
                    f"remaining."
                )
            )

        # ----------------------------------------------------
        # SIZE
        # ----------------------------------------------------

        selected_size = None

        if category == "clothes":

            if not cart_item.size:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Please select a size "
                        f"for {item.item_name}."
                    )
                )

            selected_size = (
                str(cart_item.size)
                .strip()
                .upper()
            )

            available_sizes = []

            if item.sizes:

                try:

                    parsed_sizes = json.loads(
                        item.sizes
                    )

                    if isinstance(
                        parsed_sizes,
                        list
                    ):

                        available_sizes = [
                            str(size)
                            .strip()
                            .upper()
                            for size in parsed_sizes
                            if str(size).strip()
                        ]

                except Exception:

                    raise HTTPException(
                        status_code=500,
                        detail=(
                            f"The size configuration "
                            f"for {item.item_name} "
                            f"is invalid."
                        )
                    )

            if not available_sizes:

                available_sizes = (
                    default_clothing_sizes
                )

            if selected_size not in available_sizes:

                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Invalid size "
                        f"'{selected_size}' "
                        f"for {item.item_name}. "
                        f"Available sizes: "
                        f"{', '.join(available_sizes)}."
                    )
                )

        # ----------------------------------------------------
        # NON-CLOTHING
        # ----------------------------------------------------

        else:

            selected_size = None

        # ----------------------------------------------------
        # PRICE
        # ----------------------------------------------------

        unit_price = float(
            item.price or 0
        )

        if unit_price <= 0:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid price for "
                    f"{item.item_name}."
                )
            )

        item_total = (
            unit_price *
            int(cart_item.quantity)
        )

        total_php += item_total

        # ----------------------------------------------------
        # STORE VALIDATED ITEM
        # ----------------------------------------------------

        validated_items.append({

            "item": item,

            "store_item_id": item.id,

            "item_name": item.item_name,

            "category": category,

            "quantity": int(
                cart_item.quantity
            ),

            "size": selected_size,

            "unit_price": unit_price,

            "item_total": item_total

        })

    # ========================================================
    # TOTAL
    # ========================================================

    if total_php <= 0:

        raise HTTPException(
            status_code=400,
            detail="Invalid total payment amount."
        )

    # ========================================================
    # PAYMONGO AMOUNT
    # ========================================================

    paymongo_amount = int(
        round(
            total_php * 100
        )
    )

    if paymongo_amount <= 0:

        raise HTTPException(
            status_code=400,
            detail="Invalid PayMongo payment amount."
        )

    # ========================================================
    # GENERATE STORE ORDER ID
    #
    # ONE ID FOR THE ENTIRE CART.
    #
    # Example:
    #
    # STORE-20260829153045-ABC12345
    #
    # Whether the cart has:
    #
    # 1 item
    # 2 items
    # 3 items
    # 10 items
    # 50 items
    #
    # they all use ONE store_order_id.
    # ========================================================

    store_order_id = (
        "STORE-"
        + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        + "-"
        + uuid.uuid4().hex[:8].upper()
    )

    # ========================================================
    # PAYMENT DESCRIPTION
    # ========================================================

    description_parts = []

    for validated in validated_items:

        if validated["size"]:

            description_parts.append(
                f'{validated["item_name"]} '
                f'x{validated["quantity"]} '
                f'({validated["size"]})'
            )

        else:

            description_parts.append(
                f'{validated["item_name"]} '
                f'x{validated["quantity"]}'
            )

    payment_description = (
        "Store Order "
        + store_order_id
        + ": "
        + ", ".join(description_parts)
    )

    # ========================================================
    # CREATE PAYMENT RECORDS
    #
    # ONE PAYMENT ROW PER CART ITEM.
    #
    # Example 10-item cart:
    #
    # Payment 1  -> STORE-ABC
    # Payment 2  -> STORE-ABC
    # Payment 3  -> STORE-ABC
    # ...
    # Payment 10 -> STORE-ABC
    #
    # ALL ROWS BELONG TO THE SAME CART.
    # ========================================================

    payments = []

    try:

        for validated in validated_items:

            payment = Payment(

                participant_id=None,

                payment_type="Store",

                # ------------------------------------------------
                # STORE ORDER
                # ------------------------------------------------

                store_order_id=store_order_id,

                # ------------------------------------------------
                # ITEM
                # ------------------------------------------------

                store_item_id=validated["store_item_id"],

                store_quantity=validated["quantity"],

                store_size=validated["size"],

                tshirt_size=validated["size"],

                # ------------------------------------------------
                # PAYMENT
                # ------------------------------------------------

                amount=int(
                    round(
                        validated["item_total"] * 100
                    )
                ),

                currency="PHP",

                status="Pending",

                description=payment_description,

                # ------------------------------------------------
                # CUSTOMER
                # ------------------------------------------------

                customer_name=customer_name,

                customer_contact=customer_contact,

                customer_email=customer_email
            )

            db.add(payment)

            payments.append(
                payment
            )

        db.commit()

        for payment in payments:

            db.refresh(payment)

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to create "
                f"store order: {str(e)}"
            )
        )

    # ========================================================
    # PAYMONGO CONFIG
    # ========================================================

    secret_key = PAYMONGO_SECRET_KEY

    if not secret_key:

        for payment in payments:

            db.delete(payment)

        db.commit()

        raise HTTPException(
            status_code=500,
            detail=(
                "PayMongo secret key "
                "is not configured."
            )
        )

    # ========================================================
    # PAYMONGO METADATA
    # ========================================================

    metadata_items = []

    for validated in validated_items:

        metadata_items.append({

            "store_item_id": str(
                validated["store_item_id"]
            ),

            "item_name": validated["item_name"],

            "category": validated["category"],

            "quantity": str(
                validated["quantity"]
            ),

            "size": validated["size"] or ""

        })

    # ========================================================
    # PAYMONGO PAYLOAD
    # ========================================================

    payload = {

        "amount": paymongo_amount,

        "currency": "PHP",

        "description": payment_description,

        "remarks": (
            f"Store Order {store_order_id}"
        ),

        "metadata": {

            "type": "store_purchase",

            "store_order_id": store_order_id,

            "customer_name": customer_name,

            "customer_contact": customer_contact,

            "customer_email": customer_email,

            "item_count": str(
                len(validated_items)
            ),

            "items": json.dumps(
                metadata_items
            )

        }

    }

    # ========================================================
    # CREATE PAYMONGO PAYMENT LINK
    # ========================================================

    try:

        response = httpx.post(

            "https://api.paymongo.com/v1/payment_links",

            auth=(
                secret_key,
                ""
            ),

            headers={

                "Content-Type": "application/json",

                "Idempotency-Key": (
                    f"store-order-{store_order_id}"
                )

            },

            json=payload,

            timeout=30

        )

    except Exception as e:

        for payment in payments:

            db.delete(payment)

        db.commit()

        raise HTTPException(
            status_code=502,
            detail=(
                "Unable to connect to "
                f"PayMongo: {str(e)}"
            )
        )

    # ========================================================
    # PAYMONGO ERROR
    # ========================================================

    if response.status_code not in (
        200,
        201
    ):

        try:

            error_data = response.json()

        except Exception:

            error_data = {
                "detail": response.text
            }

        for payment in payments:

            db.delete(payment)

        db.commit()

        raise HTTPException(
            status_code=502,
            detail={
                "message": (
                    "PayMongo rejected "
                    "the payment."
                ),
                "paymongo": error_data
            }
        )

    # ========================================================
    # READ RESPONSE
    # ========================================================

    try:

        result = response.json()

    except Exception as exc:

        for payment in payments:

            db.delete(payment)

        db.commit()

        raise HTTPException(
            status_code=502,
            detail=(
                "PayMongo returned "
                "invalid JSON: "
                f"{str(exc)}"
            )
        )

    # ========================================================
    # PAYMENT DATA
    # ========================================================

    payment_data = result.get(
        "data",
        {}
    )

    payment_link_id = payment_data.get(
        "id"
    )

    payment_url = payment_data.get(
        "url"
    )

    reference_number = payment_data.get(
        "reference_number"
    )

    # ========================================================
    # VALIDATE PAYMONGO RESPONSE
    # ========================================================

    if not payment_link_id:

        for payment in payments:

            db.delete(payment)

        db.commit()

        raise HTTPException(
            status_code=502,
            detail=(
                "PayMongo did not return "
                "a payment link ID."
            )
        )

    if not payment_url:

        for payment in payments:

            db.delete(payment)

        db.commit()

        raise HTTPException(
            status_code=502,
            detail=(
                "PayMongo did not return "
                "a payment URL."
            )
        )

    # ========================================================
    # SAVE PAYMONGO INFORMATION
    #
    # EVERY PAYMENT ROW GETS THE SAME:
    #
    # - payment link ID
    # - reference
    # - checkout URL
    # - store order ID
    #
    # ========================================================

    for payment in payments:

        payment.paymongo_link_id = (
            payment_link_id
        )

        payment.paymongo_reference = (
            reference_number
        )

        payment.checkout_url = (
            payment_url
        )

        payment.description = (
            payment_description
        )

    db.commit()

    # ========================================================
    # RESPONSE
    # ========================================================

    return {

        "success": True,

        "message": (
            "Store order created successfully."
        ),

        "store_order_id": store_order_id,

        "payment_id": payments[0].id,

        "payment_ids": [
            payment.id
            for payment in payments
        ],

        "item_count": len(
            validated_items
        ),

        "items": [

            {

                "payment_id": payment.id,

                "store_item_id":
                    validated["store_item_id"],

                "item_name":
                    validated["item_name"],

                "quantity":
                    validated["quantity"],

                "size":
                    validated["size"],

                "unit_price":
                    validated["unit_price"],

                "item_total":
                    validated["item_total"]

            }

            for payment, validated
            in zip(
                payments,
                validated_items
            )

        ],

        "total_amount": float(
            total_php
        ),

        "checkout_url": payment_url,

        "payment_status": "Pending"

    }
    
















# ============================================================
# STORE PURCHASE STATUS
# ============================================================

@router.get("/store/purchase/status/{payment_id}")
def store_purchase_status(
    payment_id: int,
    db: Session = Depends(get_db)
):

    payment = (
        db.query(Payment)
        .filter(
            Payment.id == payment_id,
            Payment.payment_type == "Store"
        )
        .first()
    )

    if not payment:

        raise HTTPException(
            status_code=404,
            detail="Store payment not found."
        )

    # ========================================================
    # GET WHOLE STORE ORDER
    # ========================================================

    if payment.store_order_id:

        order_payments = (
            db.query(Payment)
            .filter(
                Payment.store_order_id ==
                    payment.store_order_id,

                Payment.payment_type ==
                    "Store"
            )
            .all()
        )

    else:

        order_payments = [
            payment
        ]

    # ========================================================
    # DETERMINE ORDER STATUS
    # ========================================================

    statuses = [
        str(
            p.status or "Pending"
        ).lower()
        for p in order_payments
    ]

    if all(
        status in (
            "paid",
            "success",
            "successful",
            "completed"
        )
        for status in statuses
    ):

        order_status = "Paid"

    elif any(
        status in (
            "failed",
            "cancelled",
            "canceled"
        )
        for status in statuses
    ):

        order_status = "Failed"

    else:

        order_status = "Pending"

    # ========================================================
    # RETURN
    # ========================================================

    return {

        "success":
            True,

        "payment_id":
            payment.id,

        "store_order_id":
            payment.store_order_id,

        "status":
            order_status,

        "payment_status":
            order_status,

        "paymongo_reference":
            payment.paymongo_reference,

        "item_count":
            len(order_payments),

        "items": [

            {

                "payment_id":
                    p.id,

                "store_item_id":
                    p.store_item_id,

                "quantity":
                    p.store_quantity,

                "size":
                    p.store_size,

                "status":
                    p.status

            }

            for p in order_payments

        ]

    }














# ============================================================
# VIEW STORE ITEMS
# ============================================================

@router.get("/store/items")
def view_store_items(
    db: Session = Depends(get_db)
):

    items = (
        db.query(StoreItem)
        .filter(
            StoreItem.is_archived == False
        )
        .order_by(
            StoreItem.id.desc()
        )
        .all()
    )

    return [

        {
            "id":
                item.id,

            "item_name":
                item.item_name,

            "description":
                item.description,

            "quantity":
                item.quantity,

            "price":
                item.price

        }

        for item in items

    ]
    






# =========================================================
# STORE IMAGE UPLOAD
# =========================================================

STORE_UPLOAD_DIR = Path(
    "/app/data/uploads/store"
)

STORE_UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True
)


ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif"
}


@router.post("/upload_store_image")
async def upload_store_image(
    file: UploadFile = File(...)
):

    # -----------------------------------------------------
    # Validate file type
    # -----------------------------------------------------

    if file.content_type not in ALLOWED_IMAGE_TYPES:

        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid image type. "
                "Only JPG, PNG, WEBP, and GIF are allowed."
            )
        )


    # -----------------------------------------------------
    # Generate unique filename
    # -----------------------------------------------------

    extension = ALLOWED_IMAGE_TYPES[
        file.content_type
    ]

    filename = (
        f"{uuid.uuid4().hex}"
        f"{extension}"
    )


    file_path = (
        STORE_UPLOAD_DIR /
        filename
    )


    # -----------------------------------------------------
    # Save file
    # -----------------------------------------------------

    try:

        with file_path.open("wb") as buffer:

            shutil.copyfileobj(
                file.file,
                buffer
            )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Failed to save image: {str(e)}"
            )
        )

    finally:

        await file.close()


    # -----------------------------------------------------
    # Return URL/path
    # -----------------------------------------------------

    image_url = (
        f"/uploads/store/{filename}"
    )


    return {

        "success": True,

        "message":
            "Store image uploaded successfully.",

        "filename":
            filename,

        "image_url":
            image_url

    }
