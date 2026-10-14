#!/bin/bash
# Script para iniciar TALI Web Application

echo "================================================"
echo "🌾 TALI - Extractor de Laboreos Agrícolas"
echo "================================================"
echo ""
echo "Iniciando servidor FastAPI..."
echo ""

# Verificar que .env existe
if [ ! -f .env ]; then
    echo "❌ Error: Archivo .env no encontrado"
    echo "Crea un archivo .env con tu OPENAI_API_KEY"
    exit 1
fi

# Verificar dependencias
echo "Verificando dependencias..."
python3 -c "import fastapi, uvicorn" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Instalando dependencias..."
    pip3 install fastapi uvicorn python-multipart --quiet
fi

echo ""
echo "================================================"
echo "✓ Servidor iniciando en: http://localhost:8000"
echo "✓ Documentación API: http://localhost:8000/docs"
echo "================================================"
echo ""
echo "Presiona Ctrl+C para detener el servidor"
echo ""

# Iniciar servidor
python3 app.py
