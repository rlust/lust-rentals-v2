"""Property management routes for CRUD operations on properties."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.api.dependencies import get_config

router = APIRouter()
logger = logging.getLogger(__name__)
CONFIG = get_config()


# ============================================================================
# Request/Response Models
# ============================================================================

class PropertyCreate(BaseModel):
    """Request to create a new property."""
    property_name: str = Field(..., min_length=1, max_length=200)
    property_type: str = Field(default="rental", pattern="^(rental|business_entity)$")
    address: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = None
    sort_order: int = Field(default=0, ge=0)


class PropertyUpdate(BaseModel):
    """Request to update a property."""
    property_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    property_type: Optional[str] = Field(default=None, pattern="^(rental|business_entity)$")
    address: Optional[str] = Field(default=None, max_length=500)
    is_active: Optional[bool] = None
    notes: Optional[str] = None
    sort_order: Optional[int] = Field(default=None, ge=0)


class PropertyResponse(BaseModel):
    """Property response model."""
    id: int
    property_name: str
    property_type: str
    address: Optional[str]
    is_active: bool
    sort_order: int
    notes: Optional[str]
    created_at: str
    updated_at: str


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/", response_model=List[PropertyResponse])
def list_properties(
    http_request: Request,
    include_inactive: bool = False,
    property_type: Optional[str] = None
) -> List[PropertyResponse]:
    """
    List all properties.

    Args:
        include_inactive: Include inactive properties in results
        property_type: Filter by type ('rental' or 'business_entity')
    """
    db_path = CONFIG.data_dir / "processed" / "processed.db"

    if not db_path.exists():
        return []

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT * FROM properties WHERE 1=1"
            params = []

            if not include_inactive:
                query += " AND is_active = 1"

            if property_type:
                query += " AND property_type = ?"
                params.append(property_type)

            query += """
                ORDER BY
                    CASE WHEN property_type = 'business_entity' THEN 0 ELSE 1 END,
                    sort_order ASC,
                    property_name ASC
            """

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [
                PropertyResponse(
                    id=row["id"],
                    property_name=row["property_name"],
                    property_type=row["property_type"],
                    address=row["address"],
                    is_active=bool(row["is_active"]),
                    sort_order=row["sort_order"],
                    notes=row["notes"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"]
                )
                for row in rows
            ]

    except sqlite3.Error as e:
        logger.error(f"Database error listing properties: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.get("/{property_id}", response_model=PropertyResponse)
def get_property(http_request: Request, property_id: int) -> PropertyResponse:
    """Get a single property by ID."""
    db_path = CONFIG.data_dir / "processed" / "processed.db"

    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Database not found")

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM properties WHERE id = ?", (property_id,))
            row = cursor.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Property not found")

            return PropertyResponse(
                id=row["id"],
                property_name=row["property_name"],
                property_type=row["property_type"],
                address=row["address"],
                is_active=bool(row["is_active"]),
                sort_order=row["sort_order"],
                notes=row["notes"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )

    except sqlite3.Error as e:
        logger.error(f"Database error getting property: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.post("/", response_model=PropertyResponse, status_code=201)
def create_property(
    http_request: Request,
    property_data: PropertyCreate
) -> PropertyResponse:
    """Create a new property."""
    db_path = CONFIG.data_dir / "processed" / "processed.db"

    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Database not found")

    now = datetime.utcnow().isoformat()

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check for duplicate name
            cursor.execute(
                "SELECT id FROM properties WHERE property_name = ?",
                (property_data.property_name,)
            )
            if cursor.fetchone():
                raise HTTPException(
                    status_code=400,
                    detail=f"Property '{property_data.property_name}' already exists"
                )

            # Insert new property
            cursor.execute(
                """
                INSERT INTO properties
                (property_name, property_type, address, sort_order, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    property_data.property_name,
                    property_data.property_type,
                    property_data.address,
                    property_data.sort_order,
                    property_data.notes,
                    now,
                    now
                )
            )

            property_id = cursor.lastrowid
            conn.commit()

            # Fetch and return the created property
            cursor.execute("SELECT * FROM properties WHERE id = ?", (property_id,))
            row = cursor.fetchone()

            logger.info(f"Created property: {property_data.property_name}")

            return PropertyResponse(
                id=row["id"],
                property_name=row["property_name"],
                property_type=row["property_type"],
                address=row["address"],
                is_active=bool(row["is_active"]),
                sort_order=row["sort_order"],
                notes=row["notes"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )

    except sqlite3.Error as e:
        logger.error(f"Database error creating property: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.put("/{property_id}", response_model=PropertyResponse)
def update_property(
    http_request: Request,
    property_id: int,
    property_data: PropertyUpdate
) -> PropertyResponse:
    """Update an existing property."""
    db_path = CONFIG.data_dir / "processed" / "processed.db"

    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Database not found")

    now = datetime.utcnow().isoformat()

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check if property exists
            cursor.execute("SELECT * FROM properties WHERE id = ?", (property_id,))
            existing = cursor.fetchone()

            if not existing:
                raise HTTPException(status_code=404, detail="Property not found")

            # Build update query dynamically based on provided fields
            updates = []
            params = []

            if property_data.property_name is not None:
                # Check for duplicate name (excluding current property)
                cursor.execute(
                    "SELECT id FROM properties WHERE property_name = ? AND id != ?",
                    (property_data.property_name, property_id)
                )
                if cursor.fetchone():
                    raise HTTPException(
                        status_code=400,
                        detail=f"Property '{property_data.property_name}' already exists"
                    )
                updates.append("property_name = ?")
                params.append(property_data.property_name)

            if property_data.property_type is not None:
                updates.append("property_type = ?")
                params.append(property_data.property_type)

            if property_data.address is not None:
                updates.append("address = ?")
                params.append(property_data.address)

            if property_data.is_active is not None:
                updates.append("is_active = ?")
                params.append(1 if property_data.is_active else 0)

            if property_data.notes is not None:
                updates.append("notes = ?")
                params.append(property_data.notes)

            if property_data.sort_order is not None:
                updates.append("sort_order = ?")
                params.append(property_data.sort_order)

            if not updates:
                # No fields to update, return existing
                return PropertyResponse(
                    id=existing["id"],
                    property_name=existing["property_name"],
                    property_type=existing["property_type"],
                    address=existing["address"],
                    is_active=bool(existing["is_active"]),
                    sort_order=existing["sort_order"],
                    notes=existing["notes"],
                    created_at=existing["created_at"],
                    updated_at=existing["updated_at"]
                )

            # Always update updated_at
            updates.append("updated_at = ?")
            params.append(now)
            params.append(property_id)

            query = f"UPDATE properties SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()

            # Fetch and return updated property
            cursor.execute("SELECT * FROM properties WHERE id = ?", (property_id,))
            row = cursor.fetchone()

            logger.info(f"Updated property ID {property_id}")

            return PropertyResponse(
                id=row["id"],
                property_name=row["property_name"],
                property_type=row["property_type"],
                address=row["address"],
                is_active=bool(row["is_active"]),
                sort_order=row["sort_order"],
                notes=row["notes"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )

    except sqlite3.Error as e:
        logger.error(f"Database error updating property: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.delete("/{property_id}")
def delete_property(http_request: Request, property_id: int) -> dict:
    """
    Soft delete a property (set is_active = 0).

    Properties are never hard-deleted to preserve historical data integrity.
    """
    db_path = CONFIG.data_dir / "processed" / "processed.db"

    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Database not found")

    now = datetime.utcnow().isoformat()

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Check if property exists
            cursor.execute("SELECT property_name FROM properties WHERE id = ?", (property_id,))
            result = cursor.fetchone()

            if not result:
                raise HTTPException(status_code=404, detail="Property not found")

            property_name = result[0]

            # Soft delete
            cursor.execute(
                "UPDATE properties SET is_active = 0, updated_at = ? WHERE id = ?",
                (now, property_id)
            )
            conn.commit()

            logger.info(f"Deactivated property ID {property_id}: {property_name}")

            return {
                "status": "success",
                "message": f"Property '{property_name}' deactivated",
                "property_id": property_id
            }

    except sqlite3.Error as e:
        logger.error(f"Database error deleting property: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.post("/initialize")
def initialize_properties(http_request: Request) -> dict:
    """
    Initialize properties table with default properties and LLC entity.

    This endpoint is idempotent - running it multiple times is safe.
    """
    db_path = CONFIG.data_dir / "processed" / "processed.db"

    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Database not found")

    now = datetime.utcnow().isoformat()

    default_properties = [
        ("Lust Rentals LLC", "business_entity", None, 0),
        ("118 W Shields St", "rental", "118 W Shields St", 1),
        ("41 26th St", "rental", "41 26th St", 2),
        ("966 Kinsbury Court", "rental", "966 Kinsbury Court", 3),
    ]

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            inserted_count = 0
            skipped_count = 0

            for prop_name, prop_type, address, sort_order in default_properties:
                # Check if property already exists
                cursor.execute(
                    "SELECT id FROM properties WHERE property_name = ?",
                    (prop_name,)
                )

                if cursor.fetchone():
                    skipped_count += 1
                    continue

                # Insert property
                cursor.execute(
                    """
                    INSERT INTO properties
                    (property_name, property_type, address, sort_order, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (prop_name, prop_type, address, sort_order, now, now)
                )
                inserted_count += 1

            conn.commit()

            logger.info(f"Initialized properties: {inserted_count} inserted, {skipped_count} skipped")

            return {
                "status": "success",
                "inserted": inserted_count,
                "skipped": skipped_count,
                "message": f"Properties initialized: {inserted_count} new, {skipped_count} already existed"
            }

    except sqlite3.Error as e:
        logger.error(f"Database error initializing properties: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
