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

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase


def _parse_calendar_day(day_str: str) -> Optional[date]:
    try:
        parts = day_str.strip().split("-")
        if len(parts) != 3:
            return None
        y, mo, d = (int(parts[0]), int(parts[1]), int(parts[2]))
        return date(y, mo, d)
    except (TypeError, ValueError, OSError):
        return None


def consumption_day_window_utc(
    tz_name: Optional[str],
    local_day: Optional[str],
) -> Tuple[datetime, datetime]:
    """
    Intervalo [start, end) en UTC para consultar consumos de un día civil local.

    Si `tz_name` es una zona IANA válida, se usa ese huso; si además `local_day`
    es YYYY-MM-DD, ese día en esa zona. Si falta o es inválido el día, se usa
    «hoy» en esa zona. Si la zona es inválida o vacía, se conserva el
    comportamiento anterior (medianoche a medianoche UTC del día UTC actual).
    """
    name = (tz_name or "").strip()
    if not name or len(name) > 120:
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=1)

    try:
        tz = ZoneInfo(name)
    except Exception:
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=1)

    parsed = _parse_calendar_day(local_day) if local_day else None
    if parsed is None:
        parsed = datetime.now(tz).date()

    start_local = datetime(
        parsed.year,
        parsed.month,
        parsed.day,
        0,
        0,
        0,
        0,
        tzinfo=tz,
    )
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    return start_utc, end_utc


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


async def get_today_consumed_kcal(
    db: AsyncIOMotorDatabase,
    phone: str,
    *,
    tz_name: Optional[str] = None,
    local_day: Optional[str] = None,
) -> float:
    """
    Suma `calorias_totales_kcal` de consumos cuyo timestamp cae en el día civil
    indicado (zona IANA + fecha local), o en el día UTC actual si no hay zona válida.
    """
    start, end = consumption_day_window_utc(tz_name, local_day)
    logger.debug(f"Today's kcal window for {phone}: {start} .. {end} (tz={tz_name!r}, day={local_day!r})")
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


async def get_today_meals(
    db: AsyncIOMotorDatabase,
    phone: str,
    *,
    tz_name: Optional[str] = None,
    local_day: Optional[str] = None,
) -> List[dict]:
    """
    Consumos del día civil local (o UTC si no hay zona válida), orden cronológico.
    Cada ítem: id (Mongo _id como string), logged_at (ISO UTC), nutrition (data).
    """
    start, end = consumption_day_window_utc(tz_name, local_day)
    logger.debug(f"Today's meals window for {phone}: {start} .. {end} (tz={tz_name!r}, day={local_day!r})")
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
