"""
Script de prueba para el frontend web de TALI

Prueba el endpoint /api/upload con un archivo Excel de prueba
"""

import requests
import json
from pathlib import Path


def test_upload_endpoint():
    """Prueba el endpoint de upload con planilla_3.xlsx"""
    
    print("="*80)
    print("🧪 Prueba del endpoint /api/upload")
    print("="*80)
    
    # Verificar que existe el archivo de prueba
    test_file = Path("planilla_3.xlsx")
    if not test_file.exists():
        print("❌ Error: planilla_3.xlsx no encontrado")
        return
    
    # URL del endpoint
    url = "http://localhost:8000/api/upload"
    
    # Preparar archivo
    files = {'file': ('planilla_3.xlsx', open(test_file, 'rb'), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
    
    print(f"\n📤 Enviando {test_file.name}...")
    print("⏳ Esperando respuesta (esto puede tomar 30-60 segundos)...\n")
    
    try:
        response = requests.post(url, files=files, timeout=180)
        
        if response.status_code == 200:
            data = response.json()
            
            print("✅ Upload exitoso!")
            print(f"\n📊 Resultados:")
            print(f"   Archivo: {data['filename']}")
            print(f"   Hojas: {len(data['sheets'])}")
            print(f"   Total registros: {data['total_records']}")
            
            print(f"\n📋 Detalle por hoja:")
            for result in data['results']:
                if result.get('error'):
                    print(f"   ❌ {result['sheet']}: Error - {result['error']}")
                else:
                    print(f"   ✓ {result['sheet']}: {result['total']} registros")
                    print(f"      {result['summary']}")
            
            # Mostrar ejemplo de registro
            if data['results'][0]['records']:
                print(f"\n📝 Ejemplo de registro (primera hoja):")
                first_record = data['results'][0]['records'][0]
                print(f"   Laboreo: {first_record['Laboreo']}")
                print(f"   Insumo: {first_record['Insumo']}")
                print(f"   Tipo: {first_record['Tipo']}")
                print(f"   Dosis: {first_record['Dosis Insumo (Kg o litro/Ha aplicada)']}")
                print(f"   Fecha: {first_record['Fecha']}")
                print(f"   Hectáreas: {first_record['Hectareas (Ha)']}")
            
        else:
            print(f"❌ Error HTTP {response.status_code}")
            print(f"   Respuesta: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Error: No se pudo conectar al servidor")
        print("   ¿Está el servidor corriendo en http://localhost:8000?")
        print("   Ejecuta: python3 app.py")
    except requests.exceptions.Timeout:
        print("❌ Error: Timeout - el servidor tardó más de 180 segundos")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    
    print("\n" + "="*80)


def test_health_endpoint():
    """Prueba el health check"""
    print("\n🏥 Probando health check...")
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ Servidor activo")
            return True
        else:
            print(f"⚠️  Status: {response.status_code}")
            return False
    except:
        print("❌ Servidor no disponible")
        return False


if __name__ == "__main__":
    print("\n" + "="*80)
    print("🌾 TALI - Test del Web Frontend")
    print("="*80)
    
    # Verificar que el servidor esté corriendo
    if not test_health_endpoint():
        print("\n⚠️  El servidor debe estar corriendo en http://localhost:8000")
        print("   Ejecuta en otra terminal: python3 app.py")
        print("   Luego ejecuta este script nuevamente")
        exit(1)
    
    # Probar endpoint de upload
    test_upload_endpoint()
    
    print("\n✅ Test completado")
    print("\n💡 Ahora puedes probar la interfaz web en: http://localhost:8000")
