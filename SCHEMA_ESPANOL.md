# Esquema de Respuestas en Español

## 📊 Análisis Nutricional (endpoint `/image/{phone}`)

La respuesta de análisis de imágenes ahora retorna todos los campos en **español**:

```json
{
  "nombre_platillo": "Ensalada César con Pollo",
  "calorias_totales_kcal": 450,
  "tamaño_porcion_g": 350,
  "macronutrientes": {
    "proteina_g": 32,
    "carbohidratos_g": 25,
    "grasa_g": 22,
    "fibra_g": 5,
    "azucar_g": 4
  },
  "micronutrientes": {
    "sodio_mg": 850,
    "calcio_mg": 180,
    "hierro_mg": 2.5,
    "vitamina_c_mg": 15
  },
  "notas": "Estimación basada en porción estándar. Los valores pueden variar según ingredientes específicos."
}
```

## 🔮 Consultas Magic (endpoint `/magic/{phone}`)

El contexto y las respuestas ahora están completamente en español:

### Contexto que recibe Gemini:
```
Objetivo calórico diario del usuario: 2000 kcal

Historial de consumos (más recientes primero):
  1. [2026-03-12T14:30:00Z] Ensalada César con Pollo — 450 kcal | proteína: 32g, carbohidratos: 25g, grasa: 22g
  2. [2026-03-12T08:15:00Z] Avena con Frutos Rojos — 320 kcal | proteína: 12g, carbohidratos: 55g, grasa: 8g
```

### Pregunta del usuario:
```
¿Cuántas calorías he consumido hoy?
```

### Respuesta de Gemini (en español):
```
Has consumido un total de 770 calorías hoy. Considerando tu objetivo de 2000 kcal diarias, 
te quedan 1230 calorías disponibles para el resto del día. Vas por buen camino!
```

## 📝 Mapeo de Campos (EN → ES)

| Campo Anterior (inglés) | Campo Nuevo (español)          |
|-------------------------|--------------------------------|
| `dish_name`             | `nombre_platillo`              |
| `total_calories_kcal`   | `calorias_totales_kcal`        |
| `serving_size_g`        | `tamaño_porcion_g`             |
| `macronutrients`        | `macronutrientes`              |
| `protein_g`             | `proteina_g`                   |
| `carbohydrates_g`       | `carbohidratos_g`              |
| `fat_g`                 | `grasa_g`                      |
| `fiber_g`               | `fibra_g`                      |
| `sugar_g`               | `azucar_g`                     |
| `micronutrients`        | `micronutrientes`              |
| `sodium_mg`             | `sodio_mg`                     |
| `calcium_mg`            | `calcio_mg`                    |
| `iron_mg`               | `hierro_mg`                    |
| `vitamin_c_mg`          | `vitamina_c_mg`                |
| `notes`                 | `notas`                        |

## ⚠️ Importante

Si tienes código cliente que consume esta API, necesitas actualizar las referencias a los campos JSON para usar los nombres en español.

### Antes:
```python
platillo = response["nutrition"]["dish_name"]
calorias = response["nutrition"]["total_calories_kcal"]
proteina = response["nutrition"]["macronutrients"]["protein_g"]
```

### Ahora:
```python
platillo = response["nutrition"]["nombre_platillo"]
calorias = response["nutrition"]["calorias_totales_kcal"]
proteina = response["nutrition"]["macronutrientes"]["proteina_g"]
```
