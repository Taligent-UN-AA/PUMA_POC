"""
PUMA Data Harmonizer - Frontend para procesar Excel de laboreos agrícolas

FastAPI backend con endpoints:
- GET /: Página principal (HTML estático)
- POST /api/upload: Subir y procesar Excel
- POST /api/save: Guardar CSV editado
- WebSocket /ws/{session_id}: Progress updates en tiempo real
- GET /docs: Documentación automática de la API
"""

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import tempfile
import pandas as pd
from pathlib import Path
import traceback
import uuid
from datetime import datetime
import io
import asyncio
import json

from minimal.agents.context_extractor import ContextExtractorAgent
from minimal.agents.laboreo_detail_extractor import LaboreoDetailExtractorAgent
from minimal.agents.merger_agent import MergerAgent

model = "gpt-4o-mini"

app = FastAPI(
    title="PUMA Data Harmonizer",
    description="API para extraer y normalizar datos de laboreos desde Excel",
    version="1.0.0"
)

# Crear carpetas necesarias
Path('static').mkdir(exist_ok=True)
Path('uploads').mkdir(exist_ok=True)

# Servir archivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

# Almacenamiento de conexiones WebSocket activas
active_connections: Dict[str, WebSocket] = {}


# Modelos Pydantic
class ProcessedRecord(BaseModel):
    """Modelo para un registro procesado"""
    Id: str
    Productor: str
    Campaña: str
    Campo: str
    Lote: str
    Ambiente: str
    Cultivo: Optional[str] = ""
    Tipo_Cultivo: Optional[str] = ""
    Laboreo: str
    Hectareas: Optional[float] = None
    Pasadas: Optional[int] = 1
    Fecha: Optional[str] = ""
    Tipo: str
    Insumo: str
    Dosis_Insumo: Optional[float] = None
    Fertilizante: Optional[str] = ""
    Dosis_Fertilizante: Optional[float] = None
    Model_Id: Optional[str] = ""


class SheetResult(BaseModel):
    """Resultado del procesamiento de una hoja"""
    sheet: str
    records: List[Dict[str, Any]]
    total: int
    summary: str
    error: Optional[str] = None


class UploadResponse(BaseModel):
    """Respuesta del endpoint de upload"""
    success: bool
    filename: str
    sheets: List[str]
    results: List[SheetResult]
    total_records: int
    session_id: str
    error: Optional[str] = None


class SaveRequest(BaseModel):
    """Request para guardar CSV"""
    records: List[Dict[str, Any]]
    filename: str = "laboreos_editados.csv"


async def send_progress(session_id: str, stage: str, progress: int, message: str):
    """Envía actualización de progreso vía WebSocket"""
    print(f"[send_progress] session_id={session_id}, stage={stage}, progress={progress}%, message={message}")
    print(f"[send_progress] Active connections: {list(active_connections.keys())}")
    
    if session_id in active_connections:
        try:
            websocket = active_connections[session_id]
            
            # Verificar que la conexión esté abierta
            if websocket.client_state.name != 'CONNECTED':
                print(f"[send_progress] ✗ WebSocket not connected (state: {websocket.client_state.name})")
                return
            
            payload = {
                "stage": stage,
                "progress": progress,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
            print(f"[send_progress] Sending payload: {payload}")
            await websocket.send_json(payload)
            print(f"[send_progress] ✓ Message sent successfully")
            
            # Pequeño delay para asegurar que el mensaje se envíe antes del siguiente
            await asyncio.sleep(0.01)
        except Exception as e:
            print(f"[send_progress] ✗ Error sending progress: {e}")
            traceback.print_exc()
            # Si hay error, remover la conexión muerta
            if session_id in active_connections:
                del active_connections[session_id]
    else:
        print(f"[send_progress] ✗ session_id '{session_id}' NOT found in active_connections")


def allowed_file(filename: str) -> bool:
    """Verifica si el archivo tiene extensión permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_excel_sheets(file_path: str) -> List[str]:
    """Obtiene la lista de hojas de un Excel"""
    import openpyxl
    wb = openpyxl.load_workbook(file_path, read_only=True)
    return wb.sheetnames


async def process_excel_sheet(file_path: str, sheet_name: str, session_id: str, sheet_index: int, total_sheets: int) -> SheetResult:
    """
    Procesa una hoja de Excel con el pipeline minimal
    Envía actualizaciones de progreso vía WebSocket
    
    Returns:
        SheetResult con los registros procesados
    """
    try:
        # Calcular progreso base para esta hoja
        base_progress = (sheet_index / total_sheets) * 100
        step_progress = 100 / total_sheets / 3  # 3 agentes
        
        # Agent 1: Extract context
        await send_progress(
            session_id, 
            "context", 
            int(base_progress), 
            f"📋 Analizando estructura de '{sheet_name}'..."
        )
        
        await send_progress(
            session_id,
            "context",
            int(base_progress + step_progress * 0.2),
            f"⏳ Llamando a GPT-4o para analizar contexto (esto puede tomar 15-20s)..."
        )
        
        context_agent = ContextExtractorAgent(session_id=session_id, model=model)
        context = context_agent.extract(file_path, sheet_name)
        
        await send_progress(
            session_id,
            "context",
            int(base_progress + step_progress),
            f"✓ Contexto extraído: Campo '{context.campo}', {len(context.laboreos)} laboreos identificados"
        )
        
        # Agent 2: Extract details
        await send_progress(
            session_id,
            "details",
            int(base_progress + step_progress),
            f"🔍 Preparando extracción de insumos para {len(context.laboreos)} laboreos..."
        )
        
        await send_progress(
            session_id,
            "details",
            int(base_progress + step_progress * 1.2),
            f"⏳ Llamando a GPT-4o para extraer detalles (esto puede tomar 20-30s)..."
        )
        
        detail_agent = LaboreoDetailExtractorAgent(session_id=session_id, model=model)
        details = detail_agent.extract_details(file_path, sheet_name, context)
        
        total_insumos = sum(len(lab.insumos) for lab in details.laboreos)
        
        await send_progress(
            session_id,
            "details",
            int(base_progress + step_progress * 2),
            f"✓ Detalles extraídos: {len(details.laboreos)} laboreos con {total_insumos} insumos totales"
        )
        
        # Agent 3: Merge
        await send_progress(
            session_id,
            "merge",
            int(base_progress + step_progress * 2),
            f"🔗 Preparando normalización de {total_insumos} registros..."
        )
        
        await send_progress(
            session_id,
            "merge",
            int(base_progress + step_progress * 2.2),
            f"⏳ Llamando a GPT-4o para generar CSV normalizado (esto puede tomar 10-20s)..."
        )
        
        merger = MergerAgent(session_id=session_id, model=model)
        
        # Generar output temporal
        temp_output = os.path.join(
            tempfile.gettempdir(), 
            f"tali_{uuid.uuid4().hex[:8]}.csv"
        )
        
        result = merger.merge_and_export(
            context, 
            details, 
            temp_output,
            productor=f"web-upload-{datetime.now().strftime('%Y%m%d')}"
        )
        
        await send_progress(
            session_id,
            "merge",
            int(base_progress + step_progress * 2.7),
            f"📊 Validando y formateando registros..."
        )
        
        # Convertir FinalRecord objects a dicts
        records = []
        for rec in result.records:
            records.append({
                'Id': rec.Id,
                'Productor': rec.Productor,
                'Campaña': rec.Campania,
                'Campo': rec.Campo,
                'Lote': rec.Lote,
                'Ambiente': rec.Ambiente,
                'Cultivo': rec.Cultivo or "",
                'Tipo Cultivo': rec.Tipo_Cultivo or "",
                'Laboreo': rec.Laboreo,
                'Hectareas (Ha)': rec.Hectareas,
                'Pasadas (cant.)': rec.Pasadas,
                'Fecha': rec.Fecha or "",
                'Tipo': rec.Tipo,
                'Insumo': rec.Insumo,
                'Dosis Insumo (Kg o litro/Ha aplicada)': rec.Dosis_Insumo,
                'Fertilizante': rec.Fertilizante or "",
                'Dosis Fertilizantes (Kg o litro/Ha aplicada)': rec.Dosis_Fertilizante,
                'Model Id': rec.Model_Id or ""
            })
        
        # Limpiar archivo temporal
        if os.path.exists(temp_output):
            os.remove(temp_output)
        
        await send_progress(
            session_id,
            "merge",
            int(base_progress + step_progress * 3),
            f"✅ Hoja '{sheet_name}' completada: {result.total_records} registros generados"
        )
        
        return SheetResult(
            sheet=sheet_name,
            records=records,
            total=result.total_records,
            summary=result.summary
        )
        
    except Exception as e:
        traceback.print_exc()
        await send_progress(
            session_id,
            "error",
            int(base_progress),
            f"❌ Error en '{sheet_name}': {str(e)}"
        )
        return SheetResult(
            sheet=sheet_name,
            records=[],
            total=0,
            summary="",
            error=str(e)
        )


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint para actualizaciones de progreso en tiempo real
    """
    print(f"[WebSocket] New connection request for session_id: {session_id}")
    await websocket.accept()
    active_connections[session_id] = websocket
    print(f"[WebSocket] Connection accepted. Active connections: {list(active_connections.keys())}")
    
    # ENVIAR MENSAJE DE PRUEBA INMEDIATAMENTE
    try:
        test_message = {
            "stage": "test",
            "progress": 0,
            "message": "🧪 TEST: WebSocket conectado correctamente",
            "timestamp": datetime.now().isoformat()
        }
        print(f"[WebSocket] Sending test message: {test_message}")
        await websocket.send_json(test_message)
        print(f"[WebSocket] Test message sent successfully")
    except Exception as e:
        print(f"[WebSocket] Error sending test message: {e}")
        traceback.print_exc()
    
    try:
        # Mantener conexión abierta sin bloquear
        # Usar receive() en lugar de receive_text() para no bloquear el envío
        while True:
            try:
                # Esperar mensaje con timeout muy corto para no bloquear
                # Usar receive() que puede recibir cualquier tipo de mensaje
                message = await asyncio.wait_for(websocket.receive(), timeout=0.1)
                
                if "text" in message:
                    data = message["text"]
                    if data == "ping":
                        await websocket.send_text("pong")
                        print(f"[WebSocket] Pong sent to {session_id}")
                elif "bytes" in message:
                    # Ignorar mensajes binarios por ahora
                    pass
            except asyncio.TimeoutError:
                # Timeout es normal, continuar el loop para mantener conexión viva
                continue
            except WebSocketDisconnect:
                print(f"[WebSocket] Disconnected: {session_id}")
                break
    except Exception as e:
        print(f"[WebSocket] Error for {session_id}: {e}")
        traceback.print_exc()
    finally:
        if session_id in active_connections:
            del active_connections[session_id]
            print(f"[WebSocket] Removed {session_id} from active connections")


@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Página principal"""
    html_path = Path("static/index.html")
    if html_path.exists():
        return html_path.read_text(encoding='utf-8')
    else:
        return """
        <html>
            <body>
                <h1>PUMA Data Harmonizer</h1>
                <p>La interfaz web está en construcción.</p>
                <p>Documentación de la API: <a href="/docs">/docs</a></p>
            </body>
        </html>
        """


@app.post("/api/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...), session_id: str = Form(None)):
    """
    Endpoint para subir y procesar Excel
    
    - Acepta archivos .xlsx o .xls
    - Acepta session_id opcional para tracking de progreso
    - Procesa todas las hojas del Excel
    - Envía progreso en tiempo real vía WebSocket
    - Retorna los registros normalizados listos para editar
    """
    try:
        # Registrar tiempo de inicio
        start_time = datetime.now()
        
        # Validar archivo
        if not allowed_file(file.filename):
            raise HTTPException(
                status_code=400, 
                detail="Formato no permitido. Solo .xlsx o .xls"
            )
        
        # Usar session_id del frontend o generar uno nuevo
        if not session_id:
            session_id = f"session_{uuid.uuid4().hex[:12]}"
        
        print(f"[upload_file] Processing file with session_id: {session_id}")
        print(f"[upload_file] Active connections before sleep: {list(active_connections.keys())}")
        
        # Dar tiempo para que el WebSocket se conecte
        await asyncio.sleep(0.5)
        
        print(f"[upload_file] Active connections after sleep: {list(active_connections.keys())}")
        
        # Guardar archivo temporalmente
        temp_path = os.path.join(
            tempfile.gettempdir(), 
            f"upload_{uuid.uuid4().hex[:8]}_{file.filename}"
        )
        
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Obtener hojas
        sheets = get_excel_sheets(temp_path)
        
        # Enviar inicio
        await send_progress(
            session_id,
            "start",
            0,
            f"🚀 Iniciando procesamiento de {len(sheets)} hoja(s)..."
        )
        
        # Procesar cada hoja
        results = []
        total_records = 0
        
        for index, sheet_name in enumerate(sheets):
            result = await process_excel_sheet(temp_path, sheet_name, session_id, index, len(sheets))
            results.append(result)
            total_records += result.total
        
        # Limpiar archivo temporal
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        # Calcular tiempo total
        end_time = datetime.now()
        total_seconds = int((end_time - start_time).total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        
        # Formatear mensaje de tiempo
        if minutes > 0:
            time_str = f"{total_seconds} segundos ({minutes}m {seconds}s)"
        else:
            time_str = f"{total_seconds} segundos"
        
        # Enviar finalización con tiempo
        await send_progress(
            session_id,
            "complete",
            100,
            f"✅ Procesamiento completado en {time_str}: {total_records} registros totales"
        )
        
        return UploadResponse(
            success=True,
            filename=file.filename,
            sheets=sheets,
            results=results,
            total_records=total_records,
            session_id=session_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"Error procesando archivo: {str(e)}"
        )


@app.post("/api/save")
async def save_csv(request: SaveRequest):
    """
    Endpoint para guardar CSV editado
    
    - Recibe los registros editados
    - Genera un CSV con formato estándar (separador ;)
    - Retorna el archivo para descarga
    """
    try:
        if not request.records:
            raise HTTPException(
                status_code=400, 
                detail="No hay datos para guardar"
            )
        
        # Convertir a DataFrame
        df = pd.DataFrame(request.records)
        
        # Generar CSV en memoria
        output = io.StringIO()
        df.to_csv(output, sep=';', index=False, encoding='utf-8')
        output.seek(0)
        
        # Retornar como descarga
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename="{request.filename}"'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error guardando CSV: {str(e)}"
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok", 
        "service": "PUMA Data Harmonizer API",
        "active_connections": len(active_connections)
    }


if __name__ == "__main__":
    import uvicorn
    
    print("="*80)
    print("🚀 PUMA Data Harmonizer - FastAPI")
    print("="*80)
    print("Servidor corriendo en: http://localhost:8000")
    print("Documentación API: http://localhost:8000/docs")
    print("Presiona Ctrl+C para detener")
    print("="*80)
    print()
    
    # Usar reload=False para evitar problemas
    # Si quieres auto-reload, usa: uvicorn app:app --reload
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False, log_level="info")
