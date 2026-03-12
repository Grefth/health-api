"""
Servicio de IA — Google Gemini vía el SDK `google-genai`.

Funciones:
  - analyze_food_image : envía imagen de comida en base64 y retorna JSON nutricional estructurado
  - get_magic_insights : responde preguntas en lenguaje natural usando datos de salud del usuario
"""

import base64
import json
import os
import re
from typing import List, Optional

from google import genai
from google.genai import types
from loguru import logger


def _get_client() -> genai.Client:
    """Return an authenticated Gemini client."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "your-gemini-api-key-here":
        logger.error("❌ GEMINI_API_KEY not configured or invalid")
        raise ValueError("GEMINI_API_KEY must be set in .env file")
    logger.debug("Creating Gemini client")
    return genai.Client(api_key=api_key)


_MODEL = "gemini-2.5-flash"  # Updated to use available model

# ---------------------------------------------------------------------------
# Food image analysis
# ---------------------------------------------------------------------------

_IMAGE_PROMPT = (
    "Eres una IA nutricionista profesional.\n"
    "Analiza la comida en esta imagen y responde SOLO con un objeto JSON válido.\n"
    "Sin formato markdown, sin texto extra — solo JSON puro.\n\n"
    "Esquema requerido:\n"
    "{\n"
    '  "nombre_platillo": "string",\n'
    '  "calorias_totales_kcal": number,\n'
    '  "tamaño_porcion_g": number,\n'
    '  "macronutrientes": {\n'
    '    "proteina_g": number,\n'
    '    "carbohidratos_g": number,\n'
    '    "grasa_g": number,\n'
    '    "fibra_g": number,\n'
    '    "azucar_g": number\n'
    '  },\n'
    '  "micronutrientes": {\n'
    '    "sodio_mg": number,\n'
    '    "calcio_mg": number,\n'
    '    "hierro_mg": number,\n'
    '    "vitamina_c_mg": number\n'
    '  },\n'
    '  "notas": "string (contexto opcional o advertencias)"\n'
    "}"
)


async def analyze_food_image(image_base64: str, mime_type: str = "image/jpeg") -> dict:
    """
    Envía una imagen de comida codificada en base64 a Gemini Vision y retorna
    datos nutricionales estructurados como un dict de Python.
    """
    logger.info(f"🔍 Analyzing food image (mime_type: {mime_type}, size: {len(image_base64)} chars)")
    try:
        client = _get_client()
        image_bytes = base64.b64decode(image_base64)
        logger.debug(f"Image decoded: {len(image_bytes)} bytes")
    except Exception as e:
        logger.error(f"❌ Failed to decode image or create client: {e}")
        raise

    try:
        logger.debug(f"Sending request to Gemini model: {_MODEL}")
        response = await client.aio.models.generate_content(
            model=_MODEL,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                _IMAGE_PROMPT,
            ],
        )
        logger.debug("Gemini response received")
    except Exception as e:
        logger.error(f"❌ Gemini API request failed: {e}")
        raise

    raw = response.text.strip()
    logger.debug(f"Raw response (first 200 chars): {raw[:200]}")
    
    # Strip accidental markdown fences if the model adds them
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        result = json.loads(raw)
        logger.success(f"✓ Successfully parsed nutrition data: {result.get('nombre_platillo', 'Desconocido')}")
        return result
    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse JSON response: {e}\nRaw: {raw}")
        raise


# ---------------------------------------------------------------------------
# Magic insights
# ---------------------------------------------------------------------------

def _build_context(consumptions: List[dict], objective: Optional[str]) -> str:
    """Construye un bloque de contexto legible con los datos almacenados del usuario."""
    lines = []

    if objective:
        lines.append("Objetivo calórico diario del usuario: {} kcal\n".format(objective))
    else:
        lines.append("Objetivo calórico diario del usuario: no establecido\n")

    if consumptions:
        lines.append("Historial de consumos (más recientes primero):")
        for i, record in enumerate(consumptions, start=1):
            data = record.get("data", {})
            ts = record.get("timestamp", "")
            dish = data.get("nombre_platillo", "Platillo desconocido")
            kcal = data.get("calorias_totales_kcal", "?")
            macros = data.get("macronutrientes", {})
            lines.append(
                "  {}. [{}] {} \u2014 {} kcal | "
                "proteína: {}g, carbohidratos: {}g, grasa: {}g".format(
                    i, ts, dish, kcal,
                    macros.get("proteina_g", "?"),
                    macros.get("carbohidratos_g", "?"),
                    macros.get("grasa_g", "?"),
                )
            )
    else:
        lines.append("Historial de consumos: sin registros aún.")

    return "\n".join(lines)


async def get_magic_insights(
    prompt: str,
    consumptions: List[dict],
    objective: Optional[str],
) -> str:
    """
    Combina los datos de salud del usuario con un prompt de forma libre y pregunta a Gemini
    por una respuesta en texto plano.
    """
    logger.info(f"🔮 Getting magic insights for prompt: '{prompt[:50]}...'")
    logger.debug(f"Context: {len(consumptions)} consumptions, objective: {objective}")
    
    try:
        client = _get_client()
        context = _build_context(consumptions, objective)
        logger.debug(f"Context built: {len(context)} chars")
    except Exception as e:
        logger.error(f"❌ Failed to build context or create client: {e}")
        raise

    full_prompt = (
        "Eres un asistente útil de nutrición y salud. "
        "Usa los siguientes datos del usuario para responder la pregunta.\n\n"
        "--- DATOS DEL USUARIO ---\n{}\n\n"
        "--- PREGUNTA DEL USUARIO ---\n{}"
    ).format(context, prompt)

    try:
        logger.debug(f"Sending magic query to Gemini model: {_MODEL}")
        response = await client.aio.models.generate_content(
            model=_MODEL,
            contents=full_prompt,
        )
        answer = response.text.strip()
        logger.success(f"✓ Magic insights generated: {len(answer)} chars")
        return answer
    except Exception as e:
        logger.error(f"❌ Gemini API request failed for magic query: {e}")
        raise
