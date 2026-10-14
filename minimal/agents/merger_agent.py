"""
Agent 3 - Merger Agent

Combina el contexto general (Agent 1) con los detalles de laboreos (Agent 2)
y genera el CSV final con 18 columnas.

REGLA CLAVE: 1 laboreo con N insumos = N filas en el CSV
Cada fila tiene: contexto general + datos del laboreo + datos de UN insumo
"""

from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
import json
import csv
from pathlib import Path

from minimal.config import get_settings
from minimal.observability import get_langfuse_callbacks

from minimal.schemas.output_schema import (
    GeneralContext,
    LaboreoDetailsResponse,
    FinalRecord,
    MergedOutput
)


class MergerAgent:
    """
    Agent 3: Hace el merge y genera el CSV final de 18 columnas
    """
    
    def __init__(self, model: str = "gpt-4o", temperature: float = 0, session_id: str = None):
        """
        Args:
            model: Modelo de OpenAI a usar
            temperature: Temperatura para la generación (0 para determinístico)
            session_id: ID de sesión para tracking con Langfuse
        """
        settings = get_settings()
        self.session_id = session_id
        self.llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=settings.openai_api_key,
            model_kwargs={"response_format": {"type": "json_object"}}
        )
    
    def merge_and_export(
        self,
        context: GeneralContext,
        details: LaboreoDetailsResponse,
        output_path: str,
        productor: str = "auto-productor"
    ) -> MergedOutput:
        """
        Combina contexto + detalles y genera CSV final.
        
        Args:
            context: Contexto general del Agent 1
            details: Detalles de laboreos del Agent 2
            output_path: Path donde guardar el CSV
            productor: Nombre del productor (default auto-generado)
            
        Returns:
            MergedOutput con los registros generados
        """
        # Crear prompt para el LLM
        prompt = self._build_prompt(context, details, productor)
        
        # Llamar al LLM con Langfuse tracking
        messages = [
            SystemMessage(content=self._get_system_prompt()),
            HumanMessage(content=prompt)
        ]
        
        # Obtener callbacks de Langfuse si está habilitado
        callbacks = get_langfuse_callbacks(
            agent_name="merger_agent",
            session_id=self.session_id
        )
        
        response = self.llm.invoke(messages, config={"callbacks": callbacks})
        
        # Parse JSON
        result = json.loads(response.content)
        
        # Validar con Pydantic
        merged_output = MergedOutput(**result)
        
        # Exportar a CSV
        self._export_to_csv(merged_output.records, output_path)
        
        return merged_output
    
    def _get_system_prompt(self) -> str:
        """System prompt que define el rol del agente"""
        return """Eres un experto en normalización de datos agrícolas al formato estándar de 18 columnas.

Tu tarea es combinar:
1. Contexto general (Campo, Lote, Campaña, etc.)
2. Detalles de laboreos con sus insumos

Y generar registros individuales siguiendo esta REGLA CRÍTICA:

**1 LABOREO CON N INSUMOS = N REGISTROS EN EL CSV**

Ejemplo:
- Laboreo: "Pulverización Terrestre" del 01/07/2023
- Insumos: Roundup (3L/Ha), 2,4-D (1L/Ha), AR 40 (0.5L/Ha)
- Resultado: 3 FILAS EN EL CSV

Cada fila tiene:
- Contexto general (mismo para todas): Campo, Lote, Campaña, Productor, etc.
- Datos del laboreo (mismo para las 3): Laboreo, Fecha, Hectáreas, Pasadas
- Datos del insumo (diferente): Tipo, Insumo, Dosis Insumo

IMPORTANTE: El campo "Dosis Insumo" debe tomar el valor del campo "dosis" de cada insumo.

**SCHEMA DE SALIDA (18 columnas)**:
1. Id (generar UUID único por registro)
2. Productor
3. Campaña (formato: "2023/2024")
4. Campo
5. Lote
6. Ambiente
7. Cultivo (o vacío)
8. Tipo Cultivo (o vacío)
9. Laboreo (nombre de la actividad)
10. Hectareas (Ha)
11. Pasadas (cant.)
12. Fecha (formato DD/MM/YYYY)
13. Tipo (tipo de insumo: Herbicidas, Insecticidas, etc.)
14. Insumo (nombre del producto)
15. **Dosis Insumo** (tomar del campo "dosis" del insumo) - CRÍTICO
16. Fertilizante (vacío)
17. Dosis Fertilizantes (vacío)
18. Model Id (vacío)

MAPEO CRÍTICO DE CAMPOS:
Para cada insumo en los detalles:
- insumo.nombre_insumo → FinalRecord.Insumo
- insumo.tipo_insumo → FinalRecord.Tipo
- **insumo.dosis → FinalRecord.Dosis_Insumo** (IMPORTANTE: NO dejar en null si existe valor)

Responde SOLO con JSON válido:
{
  "records": [
    {
      "Id": "uuid-...",
      "Productor": "...",
      "Campaña": "2023/2024",
      "Campo": "...",
      "Lote": "...",
      "Ambiente": "...",
      "Cultivo": "...",
      "Tipo Cultivo": "",
      "Laboreo": "...",
      "Hectareas (Ha)": 200.0,
      "Pasadas (cant.)": 1,
      "Fecha": "01/07/2023",
      "Tipo": "Herbicidas",
      "Insumo": "Roundup Top",
      "Dosis Insumo (Kg o litro/Ha aplicada)": 2.0,  // <-- Tomar del campo "dosis" del insumo
      "Fertilizante": "",
      "Dosis Fertilizantes (Kg o litro/Ha aplicada)": null,
      "Model Id": ""
    }
  ],
  "total_records": número,
  "summary": "X laboreos expandidos a Y registros"
}

IMPORTANTE: Si el insumo tiene dosis=2.0, el campo "Dosis Insumo (Kg o litro/Ha aplicada)" DEBE ser 2.0"""
    
    def _build_prompt(
        self,
        context: GeneralContext,
        details: LaboreoDetailsResponse,
        productor: str
    ) -> str:
        """Construye el prompt con todos los datos"""
        
        # Serializar contexto
        context_json = context.model_dump_json(indent=2)
        
        # Serializar detalles
        details_json = details.model_dump_json(indent=2)
        
        return f"""Combina el contexto general con los detalles de laboreos y genera registros individuales.

**CONTEXTO GENERAL**:
```json
{context_json}
```

**DETALLES DE LABOREOS E INSUMOS**:
```json
{details_json}
```

**PRODUCTOR**: {productor}

**INSTRUCCIONES**:

1. Por cada laboreo:
   - Si tiene N insumos → genera N registros
   - Cada registro comparte: contexto general + datos del laboreo
   - Cada registro tiene: UN insumo diferente

2. Genera IDs únicos con formato "uuid-0", "uuid-1", etc.

3. **MAPEO DE CAMPOS CRÍTICO**:
   - "Dosis Insumo" = tomar del campo "dosis" del insumo en los detalles
   - "Tipo" = tomar del campo "tipo_insumo" del insumo
   - "Insumo" = tomar del campo "nombre_insumo" del insumo
   - Si un insumo tiene dosis=null, dejar "Dosis Insumo" vacío
   
4. Campos que van vacíos si no hay datos:
   - Cultivo, Tipo Cultivo
   - Fertilizante, Dosis Fertilizantes
   - Model Id

5. Normaliza fechas a formato DD/MM/YYYY

6. Asegúrate que:
   - Tipo es uno de: Herbicidas, Insecticidas, Fungicidas, Coadyuvantes, Fertilizantes, Semillas
   - Campaña está en formato "YYYY/YYYY"

Genera el JSON con todos los registros expandidos."""
    
    def _export_to_csv(self, records: List[FinalRecord], output_path: str):
        """
        Exporta los registros a un archivo CSV.
        
        Args:
            records: Lista de registros a exportar
            output_path: Path del archivo CSV de salida
        """
        # Crear directorio si no existe
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Headers (18 columnas)
        headers = [
            "Id",
            "Productor",
            "Campaña",
            "Campo",
            "Lote",
            "Ambiente",
            "Cultivo",
            "Tipo Cultivo",
            "Laboreo",
            "Hectareas (Ha)",
            "Pasadas (cant.)",
            "Fecha",
            "Tipo",
            "Insumo",
            "Dosis Insumo (Kg o litro/Ha aplicada)",
            "Fertilizante",
            "Dosis Fertilizantes (Kg o litro/Ha aplicada)",
            "Model Id"
        ]
        
        # Escribir CSV
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile, delimiter=';')
            writer.writerow(headers)
            
            for record in records:
                row = [
                    record.Id,
                    record.Productor,
                    record.Campania,
                    record.Campo,
                    record.Lote,
                    record.Ambiente,
                    record.Cultivo or "",
                    record.Tipo_Cultivo or "",
                    record.Laboreo,
                    record.Hectareas if record.Hectareas is not None else "",
                    record.Pasadas if record.Pasadas is not None else "",
                    record.Fecha or "",
                    record.Tipo,
                    record.Insumo,
                    record.Dosis_Insumo if record.Dosis_Insumo is not None else "",
                    record.Fertilizante or "",
                    record.Dosis_Fertilizante if record.Dosis_Fertilizante is not None else "",
                    record.Model_Id or ""
                ]
                writer.writerow(row)


def test_merger():
    """Test rápido del merger agent"""
    from minimal.agents.context_extractor import ContextExtractorAgent
    from minimal.agents.laboreo_detail_extractor import LaboreoDetailExtractorAgent
    
    excel_path = "planilla_3.xlsx"
    sheet_name = "CAMPO 1"
    
    # Agent 1: Context
    print("Paso 1: Extrayendo contexto...")
    context_agent = ContextExtractorAgent()
    context = context_agent.extract(excel_path, sheet_name)
    print(f"✓ {len(context.laboreos)} laboreos identificados")
    
    # Agent 2: Details
    print("\nPaso 2: Extrayendo detalles...")
    detail_agent = LaboreoDetailExtractorAgent()
    details = detail_agent.extract_details(excel_path, sheet_name, context)
    total_insumos = sum(len(lab.insumos) for lab in details.laboreos)
    print(f"✓ {len(details.laboreos)} laboreos con {total_insumos} insumos totales")
    
    # Agent 3: Merge
    print("\nPaso 3: Mergeando y exportando...")
    merger = MergerAgent()
    output_path = "output/minimal_test.csv"
    result = merger.merge_and_export(context, details, output_path)
    
    print("\n" + "="*80)
    print("RESULTADO FINAL:")
    print("="*80)
    print(f"Total registros generados: {result.total_records}")
    print(f"Resumen: {result.summary}")
    print(f"CSV guardado en: {output_path}")
    print("\nPrimeros 3 registros:")
    for i, record in enumerate(result.records[:3], 1):
        print(f"\n{i}. {record.Laboreo} - {record.Insumo}")
        print(f"   Tipo: {record.Tipo}")
        print(f"   Fecha: {record.Fecha}")
        print(f"   Hectáreas: {record.Hectareas}")
        print(f"   Dosis: {record.Dosis_Insumo}")


if __name__ == "__main__":
    test_merger()
