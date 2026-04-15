"""
Pydantic request models for the Health API.
"""

from typing import Any, Dict

from pydantic import BaseModel, Field


class ObjectiveRequest(BaseModel):
    """Body for POST /set_objective/{phone}"""

    objective: str = Field(
        ...,
        description="Daily caloric objective in kcal, stored as a string (e.g. '2000').",
        examples=["2000"],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{"objective": "2000"}]
        }
    }


class ImageRequest(BaseModel):
    """Body for POST /image/{phone}"""

    image_base64: str = Field(
        ...,
        description="Base64-encoded image of a food dish (JPEG or PNG).",
    )
    mime_type: str = Field(
        default="image/jpeg",
        description="MIME type of the image. Defaults to 'image/jpeg'.",
        examples=["image/jpeg", "image/png"],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "image_base64": "<base64-encoded-image-string>",
                    "mime_type": "image/jpeg",
                }
            ]
        }
    }


class MealLogRequest(BaseModel):
    """Body for POST /meal/log/{phone} — mismo objeto `nutrition` que devuelve POST /image/{phone}."""

    nutrition: Dict[str, Any] = Field(
        ...,
        description="Análisis nutricional del platillo (esquema Gemini / imagen).",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "nutrition": {
                        "nombre_platillo": "Ensalada",
                        "calorias_totales_kcal": 320,
                        "tamaño_porcion_g": 250,
                        "macronutrientes": {
                            "proteina_g": 12,
                            "carbohidratos_g": 28,
                            "grasa_g": 10,
                            "fibra_g": 6,
                            "azucar_g": 8,
                        },
                        "micronutrientes": {
                            "sodio_mg": 400,
                            "calcio_mg": 120,
                            "hierro_mg": 2,
                            "vitamina_c_mg": 45,
                        },
                        "notas": "",
                        "componentes_detectados": [],
                    }
                }
            ]
        }
    }


class MagicRequest(BaseModel):
    """Body for POST /magic/{phone}"""

    prompt: str = Field(
        ...,
        description="Free-form question about the user's nutrition or health data.",
        examples=["¿Cuántas calorías me faltan para llegar a mi objetivo hoy?"],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "prompt": "¿Cuántas calorías me faltan para llegar a mi objetivo hoy?"
                }
            ]
        }
    }
