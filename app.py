import os
import sys
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, RedirectResponse
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient
import uvicorn

from models.requests import ImageRequest, MagicRequest, MealLogRequest, ObjectiveRequest
from services import ai_service, db_service

load_dotenv()

# Configure loguru
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)

# ---------------------------------------------------------------------------
# MongoDB lifespan — connect on startup, close on shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    mongo_uri = os.environ["MONGODB_URI"]
    db_name = os.environ.get("DB_NAME")
    logger.info(f"tarting Health API - connecting to MongoDB: {db_name}")
    try:
        client = AsyncIOMotorClient(mongo_uri)
        # Try to ping the server
        await client.admin.command("ping")
        logger.success(f"MongoDB connected successfully: {db_name}")
    except Exception as e:
        logger.critical(f"Failed to connect to MongoDB: {e}")
        raise SystemExit(1)
    app.state.mongo_client = client
    app.state.db = client[db_name]
    
    # Ensure indexes are created
    try:
        await db_service.ensure_indexes(app.state.db)
    except Exception as e:
        logger.warning(f"Failed to create indexes (non-fatal): {e}")
    
    yield
    logger.info("Shutting down - closing MongoDB connection")
    app.state.mongo_client.close()


# ---------------------------------------------------------------------------
# FastAPI app with Swagger metadata
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Health API",
    description=(
        "API para el seguimiento nutricional de usuarios. "
        "Permite registrar objetivos calóricos, analizar imágenes de platillos "
        "con IA (Google Gemini) y consultar el historial de consumo mediante "
        "preguntas en lenguaje natural.\n\n"
        "**Identificador de usuario:** número de teléfono (path param `{phone}`)."
    ),
    version="1.0.0",
    docs_url="/api",
    contact={"name": "Health API Team"},
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Health", "description": "API status check."},
        {"name": "Objective", "description": "Gestión del objetivo calórico diario del usuario."},
        {"name": "Nutrition", "description": "Análisis nutricional de imágenes de comida con IA."},
        {"name": "Magic", "description": "Consultas de lenguaje natural sobre el historial del usuario."},
    ],
)


# Configuración simplificada de CORS
# El middleware de FastAPI maneja automáticamente las preflight requests (OPTIONS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite todos los orígenes
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

api_router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@api_router.get(
    "/health",
    tags=["Health"],
    summary="Health check",
    description="Verifica que la API esté en línea y respondiendo correctamente.",
    response_description="Estado del servicio.",
)
def read_health():
    logger.debug("Health check requested")
    return {"status": "healthy"}


@api_router.post(
    "/set_objective/{phone}",
    tags=["Objective"],
    summary="Guardar objetivo calórico",
    description=(
        "Registra o actualiza el objetivo calórico diario (en kcal) de un usuario "
        "identificado por su número de teléfono. Si ya existe un objetivo previo, "
        "se sobreescribe (upsert)."
    ),
    response_description="Confirmación del objetivo guardado.",
)
async def set_objective(
    phone: str = Path(..., description="Número de teléfono del usuario (identificador único)."),
    body: ObjectiveRequest = ...,
):
    logger.info(f"Setting objective for user {phone}: {body.objective} kcal")
    db = app.state.db
    try:
        await db_service.save_objective(db, phone, body.objective)
        logger.success(f"Objective saved for user {phone}")
        return {
            "message": "Objective saved successfully",
            "phone": phone,
            "objective_kcal": body.objective,
        }
    except Exception as exc:
        logger.error(f"Failed to save objective for {phone}: {exc}")
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc


@api_router.get(
    "/objective/{phone}",
    tags=["Objective"],
    summary="Obtener objetivo calórico",
    description=(
        "Devuelve el objetivo calórico diario guardado para el usuario, o `objective` nulo "
        "si aún no se ha configurado."
    ),
    response_description="Teléfono del usuario y objetivo en kcal (string) o null.",
)
async def read_objective(
    phone: str = Path(..., description="Número de teléfono del usuario (identificador único)."),
):
    logger.debug(f"Reading objective for user {phone}")
    db = app.state.db
    try:
        doc = await db_service.get_objective(db, phone)
        if not doc:
            return {"phone": phone, "objective": None}
        return {"phone": phone, "objective": doc.get("objective")}
    except Exception as exc:
        logger.error(f"Failed to read objective for {phone}: {exc}")
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc


@api_router.post(
    "/image/{phone}",
    tags=["Nutrition"],
    summary="Analizar imagen de platillo (vista previa)",
    description=(
        "Recibe una imagen en Base64, la analiza con Google Gemini Vision y devuelve "
        "`nutrition` **sin guardar** en base de datos. Para registrar el consumo "
        "y actualizar el diario, usa POST /meal/log/{phone} con el mismo objeto `nutrition`."
    ),
    response_description="Datos nutricionales del platillo (solo lectura / preview).",
)
async def analyze_image(
    phone: str = Path(..., description="Número de teléfono del usuario."),
    body: ImageRequest = ...,
):
    logger.info(f"Analyzing food image for user {phone} (mime_type: {body.mime_type})")
    try:
        nutrition = await ai_service.analyze_food_image(body.image_base64, body.mime_type)
        logger.success(f"AI analysis completed for {phone}: {nutrition.get('nombre_platillo', 'Desconocido')}")
    except Exception as exc:
        logger.error(f"AI service failed for {phone}: {exc}")
        raise HTTPException(status_code=502, detail=f"AI service error: {exc}") from exc

    return {
        "phone": phone,
        "nutrition": nutrition,
    }


@api_router.post(
    "/meal/log/{phone}",
    tags=["Nutrition"],
    summary="Registrar comida en el diario",
    description=(
        "Persiste en MongoDB el objeto `nutrition` (mismo JSON que devolvió POST /image/{phone}). "
        "Actualiza el historial de consumos del usuario; las calorías del día se reflejan "
        "al consultar GET /today_calories/{phone}."
    ),
    response_description="Confirmación de registro.",
)
async def log_meal(
    phone: str = Path(..., description="Número de teléfono del usuario."),
    body: MealLogRequest = ...,
):
    nutrition = body.nutrition
    if not isinstance(nutrition, dict) or not nutrition:
        raise HTTPException(status_code=400, detail="nutrition debe ser un objeto no vacío.")

    raw_kcal = nutrition.get("calorias_totales_kcal")
    try:
        kcal_val = float(raw_kcal)
    except (TypeError, ValueError) as err:
        raise HTTPException(
            status_code=400,
            detail="calorias_totales_kcal es obligatorio y debe ser numérico.",
        ) from err
    if kcal_val < 0:
        raise HTTPException(status_code=400, detail="calorias_totales_kcal inválido.")

    db = app.state.db
    try:
        await db_service.save_consumption(db, phone, nutrition)
        logger.success(f"Meal logged for {phone}: {nutrition.get('nombre_platillo', 'Desconocido')}")
    except Exception as exc:
        logger.error(f"Failed to log meal for {phone}: {exc}")
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    return {
        "message": "Meal logged successfully",
        "phone": phone,
    }


@api_router.get(
    "/today_calories/{phone}",
    tags=["Nutrition"],
    summary="Calorías consumidas en el día local",
    description=(
        "Suma las calorías (`calorias_totales_kcal`) de consumos cuyo `timestamp` cae "
        "en el día civil local indicado. Envía `tz` (IANA, p. ej. America/Mexico_City) "
        "y opcionalmente `day` (YYYY-MM-DD en esa zona); sin zona válida se usa el día UTC."
    ),
    response_description="Teléfono y total de kcal consumidas hoy.",
)
async def read_today_calories(
    phone: str = Path(..., description="Número de teléfono del usuario."),
    tz: Optional[str] = Query(
        None,
        max_length=120,
        description="Zona horaria IANA del navegador (p. ej. Europe/Madrid).",
    ),
    day: Optional[str] = Query(
        None,
        max_length=10,
        description="Día civil local YYYY-MM-DD; si se omite, «hoy» en `tz`.",
    ),
):
    logger.debug(f"Today's calories sum for {phone}")
    db = app.state.db
    try:
        consumed = await db_service.get_today_consumed_kcal(
            db, phone, tz_name=tz, local_day=day
        )
        return {"phone": phone, "consumed_kcal": consumed}
    except Exception as exc:
        logger.error(f"Failed today's calories for {phone}: {exc}")
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc


@api_router.get(
    "/meals/today/{phone}",
    tags=["Nutrition"],
    summary="Comidas registradas en el día local",
    description=(
        "Lista consumos del día civil local (medianoche a medianoche en `tz`) con "
        "`nutrition` completo. Parámetros `tz` y `day` como en GET /today_calories/{phone}."
    ),
    response_description="Items con id, logged_at y nutrition.",
)
async def read_today_meals(
    phone: str = Path(..., description="Número de teléfono del usuario."),
    tz: Optional[str] = Query(
        None,
        max_length=120,
        description="Zona horaria IANA del navegador (p. ej. Europe/Madrid).",
    ),
    day: Optional[str] = Query(
        None,
        max_length=10,
        description="Día civil local YYYY-MM-DD; si se omite, «hoy» en `tz`.",
    ),
):
    db = app.state.db
    try:
        items = await db_service.get_today_meals(
            db, phone, tz_name=tz, local_day=day
        )
        return {"phone": phone, "items": items}
    except Exception as exc:
        logger.error(f"Failed today's meals for {phone}: {exc}")
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc


@api_router.post(
    "/magic/{phone}",
    tags=["Magic"],
    summary="Consulta IA sobre historial del usuario",
    description=(
        "Recibe una pregunta en lenguaje natural, recupera el historial de consumos "
        "y el objetivo calórico del usuario desde la base de datos, y envía todo el "
        "contexto junto con la pregunta a Google Gemini. "
        "La respuesta se retorna como texto plano."
    ),
    response_description="Respuesta en texto plano generada por la IA.",
    response_class=PlainTextResponse,
)
async def magic_query(
    phone: str = Path(..., description="Número de teléfono del usuario."),
    body: MagicRequest = ...,
):
    logger.info(f"Magic query for user {phone}: '{body.prompt[:50]}...'")
    db = app.state.db
    try:
        consumptions = await db_service.get_consumptions(db, phone)
        objective_doc = await db_service.get_objective(db, phone)
        objective = objective_doc["objective"] if objective_doc else None
        logger.debug(f"Retrieved {len(consumptions)} consumptions for {phone}")
    except Exception as exc:
        logger.error(f"Failed to retrieve data for {phone}: {exc}")
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    try:
        answer = await ai_service.get_magic_insights(body.prompt, consumptions, objective)
        logger.success(f"Magic query completed for {phone}")
    except Exception as exc:
        logger.error(f"AI service failed for magic query {phone}: {exc}")
        raise HTTPException(status_code=502, detail=f"AI service error: {exc}") from exc

    return PlainTextResponse(content=answer)


app.include_router(api_router)


@app.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/api", status_code=302)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)