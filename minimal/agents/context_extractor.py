"""
Agent 1 - Context Extractor

Extrae el contexto general del Excel:
- Campos generales: Campo, Lote, Ambiente, Campaña, Cultivo, Productor
- Lista de laboreos/actividades agrícolas encontradas

Este agente lee el Excel completo y entiende la estructura general.
"""

import pandas as pd
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
import json
from pathlib import Path

from minimal.config import get_settings
from minimal.observability import get_langfuse_callbacks

from minimal.schemas.output_schema import GeneralContext


class ContextExtractorAgent:
    """
    Agent 1: Extrae contexto general y lista de laboreos del Excel
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
    
    def extract(self, excel_path: str, sheet_name: str) -> GeneralContext:
        """
        Extrae contexto general de una hoja del Excel.
        
        Args:
            excel_path: Path al archivo Excel
            sheet_name: Nombre de la hoja a procesar
            
        Returns:
            GeneralContext con los datos extraídos
        """
        # Leer Excel (primeras 50 filas como muestra)
        df = pd.read_excel(excel_path, sheet_name=sheet_name, header=None)
        excel_sample = self._format_excel_for_llm(df, max_rows=50)
        
        # Crear prompt
        prompt = self._build_prompt(sheet_name, excel_sample)
        
        # Llamar al LLM con Langfuse tracking
        messages = [
            SystemMessage(content=self._get_system_prompt()),
            HumanMessage(content=prompt)
        ]
        
        # Obtener callbacks de Langfuse si está habilitado
        callbacks = get_langfuse_callbacks(
            agent_name="context_extractor",
            sheet_name=sheet_name,
            session_id=self.session_id
        )
        
        response = self.llm.invoke(messages, config={"callbacks": callbacks})
        
        # Parse JSON
        result = json.loads(response.content)
        
        # Validar con Pydantic
        context = GeneralContext(**result)
        
        return context
    
    def _get_system_prompt(self) -> str:
        """System prompt que define el rol del agente"""
        return """Eres un experto en análisis de datos agrícolas de Argentina.

Tu tarea es analizar hojas de Excel que contienen datos de laboreos agrícolas (pulverizaciones, siembras, fertilizaciones, etc.) y extraer:

1. **Contexto General**: Campo, Lote, Ambiente, Campaña, Cultivo, Productor
2. **Lista de Laboreos**: Todas las actividades/laboreos agrícolas encontrados

IMPORTANTE:
- Los LABOREOS son ACCIONES (ej: "Pulverización Terrestre", "Siembra Directa"), NO son productos químicos
- Los productos químicos (Roundup, Glifosato, etc.) son INSUMOS, no laboreos
- Busca el contexto en las primeras filas (metadata) y en nombres de hojas
- Si no encuentras un campo, usa valores por defecto razonables

Responde SOLO con JSON válido siguiendo este schema:
{
  "campo": "nombre del campo/establecimiento",
  "lote": "nombre del lote (default: 'único')",
  "ambiente": "ambiente del lote (default: 'único')",
  "campania": "campaña agrícola (ej: '2023/2024')",
  "cultivo": "tipo de cultivo si se menciona (Soja, Trigo, etc) o null",
  "tipo_cultivo": "Primera, Segunda, etc, o null",
  "productor": "nombre del productor si se menciona o null",
  "laboreos": ["lista", "de", "laboreos", "encontrados"]
}"""
    
    def _build_prompt(self, sheet_name: str, excel_sample: str) -> str:
        """Construye el prompt con la muestra del Excel"""
        return f"""Analiza esta hoja de Excel que contiene datos de laboreos agrícolas.

**Nombre de la hoja**: {sheet_name}

**Contenido del Excel** (primeras 50 filas):
```
{excel_sample}
```

**Instrucciones**:
1. Identifica el CAMPO (puede estar en el nombre de la hoja o en las primeras filas)
2. Busca LOTE, AMBIENTE (si no hay, usa "único")
3. Identifica la CAMPAÑA (busca años como "2023-2024" o "23/24")
4. Busca el CULTIVO si se menciona (Soja, Trigo, Cevada, etc)
5. Busca el PRODUCTOR si se menciona
6. **CRÍTICO**: Identifica todos los LABOREOS (son las ACTIVIDADES/ACCIONES, NO los productos)
   - Ejemplos de laboreos: "Pulverización Terrestre", "Siembra Directa", "Fertilización", "Cosecha"
   - NO confundas con insumos: "Roundup", "Glifosato", "2,4-D" NO son laboreos

**Extrae el contexto general y la lista de laboreos en formato JSON.**"""
    
    def _format_excel_for_llm(self, df: pd.DataFrame, max_rows: int = 50) -> str:
        """
        Convierte DataFrame a texto legible para el LLM.
        
        Args:
            df: DataFrame del Excel
            max_rows: Máximo de filas a incluir
            
        Returns:
            String formateado del Excel
        """
        # Limitar filas
        df_sample = df.head(max_rows)
        
        # Convertir a string con formato de tabla
        lines = []
        for idx, row in df_sample.iterrows():
            # Filtrar valores nulos
            values = [str(v) if pd.notna(v) else "" for v in row.values]
            line = " | ".join(values)
            lines.append(f"Fila {idx}: {line}")
        
        return "\n".join(lines)


def test_context_extractor():
    """Test rápido del agente"""
    agent = ContextExtractorAgent()
    
    # Test con planilla_3.xlsx
    excel_path = "planilla_3.xlsx"
    sheet_name = "CAMPO 1"
    
    print(f"Extrayendo contexto de {excel_path} - {sheet_name}...")
    context = agent.extract(excel_path, sheet_name)
    
    print("\n" + "="*80)
    print("CONTEXTO EXTRAÍDO:")
    print("="*80)
    print(f"Campo: {context.campo}")
    print(f"Lote: {context.lote}")
    print(f"Ambiente: {context.ambiente}")
    print(f"Campaña: {context.campania}")
    print(f"Cultivo: {context.cultivo}")
    print(f"Tipo Cultivo: {context.tipo_cultivo}")
    print(f"Productor: {context.productor}")
    print(f"\nLaboreos encontrados ({len(context.laboreos)}):")
    for i, laboreo in enumerate(context.laboreos, 1):
        print(f"  {i}. {laboreo}")


if __name__ == "__main__":
    test_context_extractor()
