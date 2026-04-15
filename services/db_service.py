"""
Database service — MongoDB Atlas via Motor (async).

Collections:
  - objectives   : { _id: phone, objective: str }
  - consumptions : { phone: str, data: dict, timestamp: datetime }
"""

"""
Database service — MongoDB Atlas via Motor (async).

Collections:
  - objectives   : { _id: phone, objective: str }
  - consumptions : { phone: str, data: dict, timestamp: datetime }
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from loguru import logger


# ---------------------------------------------------------------------------
# Objectives
# ---------------------------------------------------------------------------

async def save_objective(db: AsyncIOMotorDatabase, phone: str, objective: str) -> None:
    """Upsert the caloric objective for a user identified by phone number."""
    logger.debug(f"Saving objective for {phone}: {objective}")
    try:
        result = await db.objectives.update_one(
            {"_id": phone},
            {"$set": {"objective": objective, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
        logger.debug(f"DB result: matched={result.matched_count}, modified={result.modified_count}, upserted={result.upserted_id}")
    except Exception as e:
        logger.error(f"Failed to save objective for {phone}: {e}")
        raise


async def get_objective(db: AsyncIOMotorDatabase, phone: str) -> Optional[dict]:
    """Return the objective document for a user, or None if not found."""
    logger.debug(f"Fetching objective for {phone}")
    try:
        doc = await db.objectives.find_one({"_id": phone})
        if doc:
            doc["phone"] = doc.pop("_id")
            logger.debug(f"Found objective for {phone}: {doc.get('objective')}")
        else:
            logger.debug(f"No objective found for {phone}")
        return doc
    except Exception as e:
        logger.error(f"Failed to fetch objective for {phone}: {e}")
        raise


# ---------------------------------------------------------------------------
# Consumptions
# ---------------------------------------------------------------------------

async def save_consumption(
    db: AsyncIOMotorDatabase, phone: str, nutrition_data: dict
) -> None:
    """Insert a new consumption record linked to a user's phone number."""
    logger.debug(f"Saving consumption for {phone}: {nutrition_data.get('nombre_platillo', 'Desconocido')}")
    
    # Verificar si existe un consumo idéntico reciente (últimos 5 minutos)
    five_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
    recent_duplicate = await db.consumptions.find_one({
        "phone": phone,
        "data.nombre_platillo": nutrition_data.get("nombre_platillo"),
        "data.calorias_totales_kcal": nutrition_data.get("calorias_totales_kcal"),
        "timestamp": {"$gte": five_minutes_ago}
    })
    
    if recent_duplicate:
        logger.warning(f"Duplicate consumption detected for {phone}, skipping save")
        return
    
    try:
        result = await db.consumptions.insert_one(
            {
                "phone": phone,
                "data": nutrition_data,
                "timestamp": datetime.now(timezone.utc),
            }
        )
        logger.debug(f"Consumption saved with ID: {result.inserted_id}")
    except Exception as e:
        logger.error(f"Failed to save consumption for {phone}: {e}")
        raise


async def get_consumptions(db: AsyncIOMotorDatabase, phone: str) -> List[dict]:
    """Return all consumption records for a user, sorted newest-first."""
    logger.debug(f"Fetching consumptions for {phone}")
    try:
        cursor = db.consumptions.find(
            {"phone": phone}, {"_id": 0}
        ).sort("timestamp", -1)
        results = await cursor.to_list(length=None)
        logger.debug(f"✓ Found {len(results)} consumptions for {phone}")
        return results
    except Exception as e:
        logger.error(f"Failed to fetch consumptions for {phone}: {e}")
        raise


async def get_today_consumed_kcal(db: AsyncIOMotorDatabase, phone: str) -> float:
    """
    Suma `calorias_totales_kcal` de consumos con timestamp entre medianoche UTC
    de hoy y el siguiente medianoche UTC.
    """
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    logger.debug(f"Today's kcal window (UTC) for {phone}: {start} .. {end}")
    try:
        cursor = db.consumptions.find(
            {"phone": phone, "timestamp": {"$gte": start, "$lt": end}},
            {"_id": 0, "data": 1},
        )
        docs = await cursor.to_list(length=None)
        total = 0.0
        for doc in docs:
            raw = (doc.get("data") or {}).get("calorias_totales_kcal")
            if raw is None:
                continue
            try:
                total += float(raw)
            except (TypeError, ValueError):
                continue
        logger.debug(f"Today's consumed kcal for {phone}: {total}")
        return total
    except Exception as e:
        logger.error(f"Failed to sum today's kcal for {phone}: {e}")
        raise


async def get_today_meals(db: AsyncIOMotorDatabase, phone: str) -> List[dict]:
    """
    Consumos del día (medianoche UTC → siguiente medianoche), orden cronológico.
    Cada ítem: id (Mongo _id como string), logged_at (ISO UTC), nutrition (data).
    """
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    logger.debug(f"Today's meals window (UTC) for {phone}: {start} .. {end}")
    try:
        cursor = db.consumptions.find(
            {"phone": phone, "timestamp": {"$gte": start, "$lt": end}},
            {"data": 1, "timestamp": 1},
        ).sort("timestamp", 1)
        docs = await cursor.to_list(length=None)
        out: List[dict] = []
        for doc in docs:
            oid = doc.get("_id")
            ts = doc.get("timestamp")
            out.append(
                {
                    "id": str(oid) if oid is not None else "",
                    "logged_at": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                    "nutrition": doc.get("data") or {},
                }
            )
        logger.debug(f"Today's meals for {phone}: {len(out)} items")
        return out
    except Exception as e:
        logger.error(f"Failed to list today's meals for {phone}: {e}")
        raise


# ---------------------------------------------------------------------------
# Database initialization
# ---------------------------------------------------------------------------

async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create indexes for better query performance."""
    logger.info("Ensuring database indexes...")
    try:
        # Index for consumption queries (phone + timestamp)
        await db.consumptions.create_index([("phone", 1), ("timestamp", -1)])
        # Index for duplicate detection
        await db.consumptions.create_index([
            ("phone", 1), 
            ("data.nombre_platillo", 1), 
            ("timestamp", -1)
        ])
        logger.success("Database indexes created/verified")
    except Exception as e:
        logger.error(f"Failed to create indexes: {e}")
        raise
