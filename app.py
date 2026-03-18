import os
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Path
from fastapi.responses import PlainTextResponse
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient
import uvicorn

from models.requests import ImageRequest, MagicRequest, ObjectiveRequest
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
    mongo_uri = os.environ["MONGO_URI"]
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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    tags=["Health"],
    summary="Health check",
    description="Verifica que la API esté en línea y respondiendo correctamente.",
    response_description="Estado del servicio.",
)
def read_health():
    logger.debug("Health check requested")
    return {"status": "healthy"}


@app.post(
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


@app.post(
    "/image/{phone}",
    tags=["Nutrition"],
    summary="Analizar imagen de platillo",
    description=(
        "Recibe una imagen de un platillo de comida codificada en Base64, la envía a "
        "Google Gemini Vision para análisis nutricional y guarda el resultado en la "
        "base de datos vinculado al usuario. "
        "Retorna un JSON con el nombre del plato, calorías totales, macronutrientes y micronutrientes."
    ),
    response_description="Datos nutricionales del platillo analizados por la IA.",
)
async def analyze_image(
    phone: str = Path(..., description="Número de teléfono del usuario."),
    body: ImageRequest = ...,
):
    logger.info(f"Analyzing food image for user {phone} (mime_type: {body.mime_type})")
    db = app.state.db
    try:
        nutrition = await ai_service.analyze_food_image(body.image_base64, body.mime_type)
        logger.success(f"AI analysis completed for {phone}: {nutrition.get('nombre_platillo', 'Desconocido')}")
    except Exception as exc:
        logger.error(f"AI service failed for {phone}: {exc}")
        raise HTTPException(status_code=502, detail=f"AI service error: {exc}") from exc

    try:
        await db_service.save_consumption(db, phone, nutrition)
        logger.info(f"Consumption saved for user {phone}")
    except Exception as exc:
        logger.error(f"Failed to save consumption for {phone}: {exc}")
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    return {
        "phone": phone,
        "nutrition": nutrition,
    }


@app.post(
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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)