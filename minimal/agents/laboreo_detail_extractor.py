"""
Agent 2 - Laboreo Detail Extractor

Para cada laboreo identificado, extrae:
- Fecha del laboreo
- Hectáreas trabajadas
- Pasadas
- Lista de INSUMOS usados con sus detalles (nombre, tipo, dosis, fecha)

Este agente entiende que un laboreo puede tener múltiples insumos.
"""

import pandas as pd
from typing import Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
import json

from minimal.config import get_settings
from minimal.observability import get_langfuse_callbacks

from minimal.schemas.output_schema import (
    GeneralContext, 
    LaboreoDetail, 
    LaboreoDetailsResponse,
    InsumoDetail
)


class LaboreoDetailExtractorAgent:
    """
    Agent 2: Extrae detalles de cada laboreo con sus insumos
    """
    
    def __init__(self, model: str = "gpt-4o", temperature: float = 0.1, session_id: str = None):
        """
        Args:
            model: Modelo de OpenAI a usar
            temperature: Temperatura para la generación
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
    
    def extract_details(
        self, 
        excel_path: str, 
        sheet_name: str,
        context: GeneralContext
    ) -> LaboreoDetailsResponse:
        """
        Extrae detalles de todos los laboreos de una hoja.
        
        Args:
            excel_path: Path al archivo Excel
            sheet_name: Nombre de la hoja
            context: Contexto general del Agent 1
            
        Returns:
            LaboreoDetailsResponse con todos los laboreos y sus insumos
        """
        # Leer Excel completo
        df = pd.read_excel(excel_path, sheet_name=sheet_name, header=None)
        excel_data = self._format_excel_for_llm(df, max_rows=100)
        
        # Crear prompt
        prompt = self._build_prompt(sheet_name, context, excel_data)
        
        # Llamar al LLM con Langfuse tracking
        messages = [
            SystemMessage(content=self._get_system_prompt()),
            HumanMessage(content=prompt)
        ]
        
        # Obtener callbacks de Langfuse si está habilitado
        callbacks = get_langfuse_callbacks(
            agent_name="laboreo_detail_extractor",
            sheet_name=sheet_name,
            session_id=self.session_id
        )
        
        response = self.llm.invoke(messages, config={"callbacks": callbacks})
        
        # Parse JSON
        result = json.loads(response.content)
        
        # Validar con Pydantic
        details = LaboreoDetailsResponse(**result)
        
        return details
    
    def _get_system_prompt(self) -> str:
        """System prompt que define el rol del agente"""
        return """Eres un experto en análisis de datos agrícolas de Argentina especializado en LABOREOS e INSUMOS.

Tu tarea es analizar hojas de Excel que contienen datos de laboreos agrícolas y extraer:

Para cada LABOREO:
1. Nombre del laboreo (la actividad/acción)
2. Fecha del laboreo
3. Hectáreas trabajadas
4. Pasadas (cantidad)
5. Lista de INSUMOS usados en ese laboreo

Para cada INSUMO:
1. Nombre del producto (ej: "Roundup Top", "Glifosato", "2,4-D")
2. Tipo (Herbicidas, Insecticidas, Fungicidas, Coadyuvantes, Fertilizantes, Semillas)
3. **Dosis (Kg o litros por Ha)** - MUY IMPORTANTE: buscar en columnas como "Dosis", "L/Ha", "Kg/Ha", "Litros/Ha", o valores numéricos cerca del nombre del producto
4. Fecha de aplicación (si es diferente a la del laboreo)

CONCEPTOS CLAVE:
- **LABOREO** = ACCIÓN (Pulverización, Siembra, Fertilización)
- **INSUMO** = PRODUCTO usado en el laboreo (Roundup, Glifosato, Semilla de Soja)
- Un laboreo puede tener MÚLTIPLES insumos
- Si un laboreo tiene 3 productos → ese laboreo tiene 3 insumos

TIPOS DE INSUMO válidos:
- Herbicidas (controlan malezas)
- Insecticidas (controlan insectos)
- Fungicidas (controlan hongos)
- Coadyuvantes (mejoran la aplicación)
- Fertilizantes (nutren el cultivo)
- Semillas (para siembra)

Responde SOLO con JSON válido siguiendo este schema:
{
  "campo": "nombre del campo",
  "laboreos": [
    {
      "laboreo": "nombre del laboreo",
      "fecha": "DD/MM/YYYY o null",
      "hectareas": número o null,
      "pasadas": número (default 1),
      "insumos": [
        {
          "nombre_insumo": "nombre del producto",
          "tipo_insumo": "Herbicidas|Insecticidas|Fungicidas|Coadyuvantes|Fertilizantes|Semillas",
          "dosis": número o null,
          "fecha": "DD/MM/YYYY o null"
        }
      ]
    }
  ]
}"""
    
    def _build_prompt(
        self, 
        sheet_name: str, 
        context: GeneralContext,
        excel_data: str
    ) -> str:
        """Construye el prompt con contexto y datos del Excel"""
        laboreos_list = "\n".join(f"  - {lab}" for lab in context.laboreos)
        
        return f"""Analiza esta hoja de Excel y extrae los detalles de cada laboreo con sus insumos.

**CONTEXTO YA IDENTIFICADO** (del Agent 1):
- Campo: {context.campo}
- Campaña: {context.campania}
- Laboreos identificados:
{laboreos_list}

**CONTENIDO DEL EXCEL**:
```
{excel_data}
```

**INSTRUCCIONES**:

1. Para cada laboreo de la lista, encuentra en el Excel:
   - Fecha del laboreo
   - Hectáreas trabajadas (puede estar en metadata o por fila)
   - Pasadas (si no está explícito, usa 1)
   
2. Para cada laboreo, identifica TODOS los insumos/productos usados:
   - Nombre del producto (busca en columnas de productos/insumos/agroquímicos)
   - Tipo del producto (clasifica según su función: Herbicida, Insecticida, etc)
   - **Dosis aplicada** (Kg o litros/Ha) - CRÍTICO: busca columnas como "Dosis", "Litros/Ha", "Kg/Ha", "L/Ha"
   - Fecha (si es diferente a la del laboreo)

3. **IMPORTANTE**: 
   - Si ves una tabla con productos en filas → cada fila es un insumo diferente
   - Si un laboreo aparece con 5 productos → crea 5 insumos en la lista
   - Los productos pueden estar en columnas paralelas o en filas

4. **ESTRUCTURA TÍPICA**:
   - A veces hay una tabla de "Laboreos" (izquierda) y otra de "Insumos" (derecha)
   - Relaciona las tablas por fecha o por posición de fila
   - Si no puedes relacionar con certeza, crea laboreos separados por cada insumo

Extrae todos los laboreos con sus insumos en formato JSON."""
    
    def _format_excel_for_llm(self, df: pd.DataFrame, max_rows: int = 100) -> str:
        """
        Convierte DataFrame a texto legible para el LLM.
        
        Args:
            df: DataFrame del Excel
            max_rows: Máximo de filas a incluir
            
        Returns:
            String formateado del Excel
        """
        df_sample = df.head(max_rows)
        
        lines = []
        for idx, row in df_sample.iterrows():
            values = [str(v) if pd.notna(v) else "" for v in row.values]
            line = " | ".join(values)
            lines.append(f"Fila {idx}: {line}")
        
        return "\n".join(lines)


def test_laboreo_detail_extractor():
    """Test rápido del agente"""
    from minimal.agents.context_extractor import ContextExtractorAgent
    
    # Primero extraer contexto con Agent 1
    context_agent = ContextExtractorAgent()
    excel_path = "planilla_3.xlsx"
    sheet_name = "CAMPO 1"
    
    print("Paso 1: Extrayendo contexto...")
    context = context_agent.extract(excel_path, sheet_name)
    print(f"✓ Contexto extraído: {len(context.laboreos)} laboreos identificados")
    
    # Ahora extraer detalles con Agent 2
    detail_agent = LaboreoDetailExtractorAgent()
    
    print("\nPaso 2: Extrayendo detalles de laboreos e insumos...")
    details = detail_agent.extract_details(excel_path, sheet_name, context)
    
    print("\n" + "="*80)
    print("DETALLES EXTRAÍDOS:")
    print("="*80)
    print(f"Campo: {details.campo}")
    print(f"Total laboreos: {len(details.laboreos)}")
    
    total_insumos = sum(len(lab.insumos) for lab in details.laboreos)
    print(f"Total insumos: {total_insumos}")
    
    print("\nDetalles por laboreo:")
    for i, laboreo in enumerate(details.laboreos[:3], 1):  # Mostrar primeros 3
        print(f"\n{i}. {laboreo.laboreo}")
        print(f"   Fecha: {laboreo.fecha}")
        print(f"   Hectáreas: {laboreo.hectareas}")
        print(f"   Pasadas: {laboreo.pasadas}")
        print(f"   Insumos ({len(laboreo.insumos)}):")
        for insumo in laboreo.insumos:
            print(f"     - {insumo.nombre_insumo} ({insumo.tipo_insumo}) - Dosis: {insumo.dosis}")


if __name__ == "__main__":
    test_laboreo_detail_extractor()
