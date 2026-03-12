# Sistema de Logging con Loguru

Este proyecto utiliza **Loguru** para un sistema de logging simple y efectivo.

## 📋 Configuración

Los logs se generan únicamente en **consola (stderr)**:
- **Nivel**: INFO
- **Formato**: Colorizado con timestamp, nivel, ubicación y mensaje
- Ver logs en tiempo real durante desarrollo y producción

## 🔍 Niveles de Log Implementados

### En todos los servicios:
- **DEBUG** 🔧: Detalles técnicos (tamaño de imágenes, queries DB, etc.)
- **INFO** ℹ️: Operaciones normales (requests, procesamiento)
- **SUCCESS** ✅: Operaciones completadas exitosamente
- **ERROR** ❌: Errores capturados con contexto
- **CRITICAL** 🚨: Errores fatales (fallo de conexión DB)

## 📍 Puntos de Logging

### **app.py**
- 🚀 Inicio de aplicación y conexión a MongoDB
- 📝 Todas las peticiones HTTP con parámetros
- ✅ Respuestas exitosas
- ❌ Errores de servicios (AI, DB)

### **ai_service.py**
- 🖼️ Análisis de imágenes (tamaño, mime-type)
- 🔑 Validación de API key de Gemini
- 📤 Requests a Gemini API
- 📥 Respuestas parseadas
- ❌ Errores de decodificación, API, JSON

### **db_service.py**
- 💾 Operaciones CRUD (save/get objectives & consumptions)
- 🔍 Queries ejecutadas
- ✅ Resultados de operaciones (IDs insertados, documentos encontrados)
- ❌ Errores de MongoDB

## 🛠️ Uso en Desarrollo

### Ver logs en tiempo real:
```bash
python app.py
```

Los logs aparecerán coloreados en la consola:
```
2026-03-12 10:30:15 | INFO     | app:lifespan:20 - 🚀 Starting Health API - connecting to MongoDB: health_db
2026-03-12 10:30:15 | SUCCESS  | app:lifespan:26 - ✓ MongoDB connected successfully: health_db
```

## 🐛 Debugging de Errores

Cuando ocurre un error, los logs incluyen:
1. **Contexto completo**: Usuario (phone), operación intentada
2. **Stack trace**: Excepción completa
3. **Datos relevantes**: Parámetros de entrada, respuestas parciales

Ejemplo de error capturado:
```
2026-03-12 10:35:42 | ERROR    | ai_service:analyze_food_image:78 - ❌ Gemini API request failed: [Errno 8] nodename nor servname provided, or not known
2026-03-12 10:35:42 | ERROR    | app:analyze_image:126 - ❌ AI service failed for 12345: [Errno 8] nodename nor servname provided
```

## ⚙️ Personalización

Para cambiar el nivel de logging, edita en `app.py`:

```python
logger.add(
    sys.stderr,
    level="DEBUG"  # Cambiar a "DEBUG" para más detalle en consola
)
```

## 📊 Monitoreo en Producción

En producción, puedes:
1. Integrar con servicios como **Sentry** o **Datadog**
2. Usar `tail -f logs/health_api_*.log` para monitoring en vivo
3. Configurar alertas basadas en logs de nivel ERROR/CRITICAL

## 🔒 Consideraciones de Seguridad

Los logs **NO registran**:
- I