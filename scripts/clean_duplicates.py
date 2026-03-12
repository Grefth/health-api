"""
Script para limpiar consumos duplicados en la base de datos.

Este script identifica y elimina registros duplicados en la colección 'consumptions',
manteniendo solo el registro más reciente de cada duplicado.

Uso:
    python scripts/clean_duplicates.py
"""

import asyncio
import os
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()


async def clean_duplicates():
    """Elimina consumos duplicados basándose en phone, nombre_platillo y calorías."""
    
    mongo_uri = os.environ["MONGO_URI"]
    db_name = os.environ.get("DB_NAME", "health_db")
    
    print(f"🔌 Conectando a MongoDB: {db_name}...")
    client = AsyncIOMotorClient(mongo_uri)
    db = client[db_name]
    
    try:
        # Obtener todos los consumos
        consumptions = await db.consumptions.find().to_list(length=None)
        print(f"📊 Total de consumos encontrados: {len(consumptions)}")
        
        # Agrupar por (phone, nombre_platillo, calorías)
        groups = {}
        for doc in consumptions:
            phone = doc.get("phone")
            data = doc.get("data", {})
            nombre = data.get("nombre_platillo", "")
            calorias = data.get("calorias_totales_kcal", 0)
            timestamp = doc.get("timestamp")
            
            key = (phone, nombre, calorias)
            
            if key not in groups:
                groups[key] = []
            groups[key].append({
                "_id": doc["_id"],
                "timestamp": timestamp
            })
        
        # Encontrar grupos con duplicados
        duplicates_count = 0
        deleted_count = 0
        
        for key, docs in groups.items():
            if len(docs) > 1:
                duplicates_count += 1
                # Ordenar por timestamp (más reciente primero)
                docs.sort(key=lambda x: x["timestamp"], reverse=True)
                
                # Mantener el más reciente, eliminar los demás
                to_keep = docs[0]
                to_delete = docs[1:]
                
                print(f"\n🔍 Duplicados encontrados para: {key[0]} - {key[1]}")
                print(f"   Manteniendo: ID={to_keep['_id']}, timestamp={to_keep['timestamp']}")
                
                for doc in to_delete:
                    result = await db.consumptions.delete_one({"_id": doc["_id"]})
                    if result.deleted_count > 0:
                        deleted_count += 1
                        print(f"   ❌ Eliminado: ID={doc['_id']}, timestamp={doc['timestamp']}")
        
        print(f"\n✅ Limpieza completada:")
        print(f"   - Grupos de duplicados encontrados: {duplicates_count}")
        print(f"   - Documentos eliminados: {deleted_count}")
        print(f"   - Documentos restantes: {len(consumptions) - deleted_count}")
        
    except Exception as e:
        print(f"❌ Error durante la limpieza: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    print("🧹 Iniciando limpieza de duplicados...\n")
    asyncio.run(clean_duplicates())
    print("\n✨ Proceso completado!")
