# Prevención de Duplicados en Consumos

## 🔍 Problema Original

Los consumos se guardaban sin validación, permitiendo que el mismo análisis se guardara múltiples veces si:
- El usuario enviaba el mismo request dos veces
- Había un doble-click en la aplicación cliente
- Se ejecutaba el mismo curl varias veces

Esto resultaba en:
- Múltiples documentos con el mismo `phone` pero diferentes `_id` de MongoDB
- Historial inflado con datos duplicados
- Estadísticas incorrectas

## ✅ Solución Implementada

### 1. **Detección de Duplicados** ([db_service.py](services/db_service.py))

Antes de guardar un nuevo consumo, se verifica si existe uno idéntico en los **últimos 5 minutos**:

```python
# Validación por:
- phone (mismo usuario)
- nombre_platillo (mismo platillo)
- calorias_totales_kcal (mismas calorías)
- timestamp (últimos 5 minutos)
```

Si se detecta un duplicado, se **omite el guardado** y se registra un warning en los logs.

### 2. **Índices de Base de Datos**

Se crearon índices para optimizar las consultas de detección:

```python
await db.consumptions.create_index([("phone", 1), ("timestamp", -1)])
await db.consumptions.create_index([
    ("phone", 1), 
    ("data.nombre_platillo", 1), 
    ("timestamp", -1)
])
```

Estos índices se crean automáticamente al iniciar la aplicación.

### 3. **Logs Mejorados**

Ahora verás en los logs cuando se detecta un duplicado:

```
⚠️ Duplicate consumption detected for 12345, skipping save
```

## 🧹 Limpieza de Duplicados Existentes

Si ya tienes duplicados en tu base de datos, usa el script de limpieza:

```bash
python scripts/clean_duplicates.py
```

Este script:
1. Encuentra todos los grupos de consumos duplicados
2. Mantiene el registro **más reciente** de cada grupo
3. Elimina los duplicados antiguos
4. Muestra un resumen de la limpieza

### Ejemplo de salida:

```
🧹 Iniciando limpieza de duplicados...

🔌 Conectando a MongoDB: health_db...
📊 Total de consumos encontrados: 10

🔍 Duplicados encontrados para: 12345 - Pizza Margarita
   Manteniendo: ID=507f1f77bcf86cd799439011, timestamp=2026-03-12 14:30:00
   ❌ Eliminado: ID=507f1f77bcf86cd799439012, timestamp=2026-03-12 14:25:00

✅ Limpieza completada:
   - Grupos de duplicados encontrados: 3
   - Documentos eliminados: 5
   - Documentos restantes: 5

✨ Proceso completado!
```

## ⚙️ Personalización

### Ajustar ventana de tiempo para duplicados

En [db_service.py](services/db_service.py), línea ~70:

```python
# Cambiar de 5 minutos a otro valor
five_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=5)
```

### Criterios de duplicación más estrictos

Puedes agregar más campos a la validación:

```python
recent_duplicate = await db.consumptions.find_one({
    "phone": phone,
    "data.nombre_platillo": nutrition_data.get("nombre_platillo"),
    "data.calorias_totales_kcal": nutrition_data.get("calorias_totales_kcal"),
    "data.macronutrientes.proteina_g": nutrition_data.get("macronutrientes", {}).get("proteina_g"),  # Nuevo
    "timestamp": {"$gte": five_minutes_ago}
})
```

## 📊 Comportamiento Esperado

### ✅ Casos permitidos (NO son duplicados):

1. **Mismo usuario, distinto platillo**:
   ```
   12345 - Pizza (14:00)
   12345 - Ensalada (14:30) ✓
   ```

2. **Mismo usuario, mismo platillo, pero distinto tiempo** (>5 min):
   ```
   12345 - Pizza (14:00)
   12345 - Pizza (14:10) ✓ (más de 5 minutos)
   ```

3. **Distinto usuario, mismo platillo**:
   ```
   12345 - Pizza (14:00)
   67890 - Pizza (14:01) ✓
   ```

### ❌ Casos bloqueados (duplicados):

1. **Request duplicado inmediato**:
   ```
   12345 - Pizza 650 kcal (14:00:00)
   12345 - Pizza 650 kcal (14:00:02) ✗ (mismo platillo, mismo usuario, <5min)
   ```

## 🔒 Consideraciones

- La ventana de 5 minutos es un balance entre prevenir duplicados y permitir consumos legítimos
- Si un usuario realmente come el mismo platillo dos veces en 5 minutos, deberá esperar
- Los duplicados se detectan **antes** de guardar, no usando bases de datos únicas, para mayor flexibilidad

## 📝 Estructura de Datos

Cada consumo en MongoDB tiene:

```json
{
  "_id": ObjectId("..."),           // Único generado por MongoDB
  "phone": "12345",                 // Puede repetirse (múltiples consumos)
  "data": {
    "nombre_platillo": "Pizza",
    "calorias_totales_kcal": 650,
    ...
  },
  "timestamp": ISODate("2026-03-12T14:00:00Z")
}
```

**Es correcto** que múltiples documentos tengan el mismo `phone` - representa el historial del usuario.
**No es correcto** que documentos idénticos se guarden múltiples veces en corto tiempo.
