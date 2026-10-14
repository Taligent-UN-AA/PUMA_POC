# TALI Minimal - LLM-First Approach

Pipeline **ultra-simplificado** de 3 agentes LLM para extraer datos de Excel agrícolas y normalizarlos a CSV de 18 columnas.

## 🎯 Filosofía

**"Con menos hacer más"** - POC/Spike rápido usando solo LLMs (GPT-4o), sin pandas, sin código generado.

## 🏗️ Arquitectura

### 3 Agentes LLM Puros:

```
Excel → Agent 1: Context Extractor
          ↓
          {campo, campaña, lote, laboreos: [...]}
          ↓
        Agent 2: Laboreo Detail Extractor
          ↓
          {laboreo1: {insumos: [...]}, laboreo2: {...}}
          ↓
        Agent 3: Merger
          ↓
        CSV (18 columnas)
```

### Agent 1 - Context Extractor
**Input**: Excel completo (primeras 50 filas)  
**Output**: 
- Campos generales: `Campo, Lote, Ambiente, Campaña, Cultivo, Tipo Cultivo, Productor`
- Lista de LABOREOS (acciones: "Pulverización", "Siembra", etc.)

**Archivo**: `agents/context_extractor.py`

### Agent 2 - Laboreo Detail Extractor
**Input**: Excel + contexto del Agent 1  
**Output**: Por cada laboreo:
- Fecha, Hectáreas, Pasadas
- Lista de INSUMOS usados: `{nombre, tipo, dosis, fecha}`

**Archivo**: `agents/laboreo_detail_extractor.py`

### Agent 3 - Merger
**Input**: Contexto (Agent 1) + Detalles (Agent 2)  
**Output**: CSV de 18 columnas

**Regla crítica**: 1 laboreo con N insumos = N filas  
Ejemplo: Pulverización con 3 productos → 3 filas en el CSV

**Archivo**: `agents/merger_agent.py`

## 📦 Instalación

```bash
# Desde la raíz de TALI
cd minimal

# Dependencias (ya instaladas en el proyecto):
# - langchain-openai
# - pandas
# - pydantic
# - openpyxl
```

## 🚀 Uso

### Procesar un Excel completo:
```bash
python test_minimal.py planilla_3.xlsx
```

### Procesar una hoja específica:
```bash
python test_minimal.py planilla_3.xlsx "CAMPO 1"
```

### Test de un agente individual:

**Agent 1**:
```bash
python -m minimal.agents.context_extractor
```

**Agent 2**:
```bash
python -m minimal.agents.laboreo_detail_extractor
```

**Agent 3**:
```bash
python -m minimal.agents.merger_agent
```

## 📊 Output

El pipeline genera CSVs con 18 columnas estándar en: **`minimal/output/`**

```
/minimal/output/
├── planilla_3_CAMPO_1_minimal.csv
├── planilla_3_CAMPO_2_minimal.csv
├── planilla_3_CAMPO_3_minimal.csv
└── planilla_3_CAMPO_4_minimal.csv
```

Formato de los archivos generados:

```
Id;Productor;Campaña;Campo;Lote;Ambiente;Cultivo;Tipo Cultivo;Laboreo;Hectareas (Ha);Pasadas (cant.);Fecha;Tipo;Insumo;Dosis Insumo (Kg o litro/Ha aplicada);Fertilizante;Dosis Fertilizantes (Kg o litro/Ha aplicada);Model Id
uuid-0;auto-productor-planilla_3;2023/2024;CAMPO 1;único;único;;;Pulverización Terrestre;50;1;01/07/2023;Herbicidas;Roundup Top;3;;;
uuid-1;auto-productor-planilla_3;2023/2024;CAMPO 1;único;único;;;Pulverización Terrestre;50;1;01/07/2023;Herbicidas;2,4-D Amina;1;;;
...
```

Archivos generados en: **`minimal/output/{filename}_{sheetname}_minimal.csv`**

## 🧠 Conceptos Clave

### LABOREO vs INSUMO

- **LABOREO** = ACCIÓN/ACTIVIDAD
  - Ejemplos: "Pulverización Terrestre", "Siembra Directa", "Fertilización"
  - Son las tareas agrícolas realizadas

- **INSUMO** = PRODUCTO usado en el laboreo
  - Ejemplos: "Roundup Top", "Glifosato", "2,4-D", "Semilla de Soja"
  - Tienen un TIPO: Herbicidas, Insecticidas, Fungicidas, Coadyuvantes, Fertilizantes, Semillas

### Expansión de Filas

**Input Excel** (estructura típica):
```
Fecha       | Laboreo              | Hectáreas
01/07/2023  | Pulverización       | 50

Productos:
- Roundup Top (3 L/Ha)
- 2,4-D (1 L/Ha)  
- AR 40 (0.5 L/Ha)
```

**Output CSV** (3 filas):
```
Fecha      | Laboreo          | Hectáreas | Insumo       | Dosis
01/07/2023 | Pulverización    | 50        | Roundup Top  | 3
01/07/2023 | Pulverización    | 50        | 2,4-D        | 1
01/07/2023 | Pulverización    | 50        | AR 40        | 0.5
```

## 🎨 Schemas

Los schemas Pydantic garantizan salidas estructuradas:

- `GeneralContext`: Output del Agent 1
- `LaboreoDetail` + `InsumoDetail`: Output del Agent 2
- `FinalRecord`: Cada fila del CSV final
- `MergedOutput`: Output del Agent 3

**Archivo**: `schemas/output_schema.py`

## 🔧 Configuración

Todos los agentes usan **GPT-4o** por defecto:

```python
agent = ContextExtractorAgent(model="gpt-4o", temperature=0.1)
```

Para cambiar el modelo:
```python
agent = ContextExtractorAgent(model="gpt-4-turbo")
```

## ⚡ Ventajas de este Enfoque

✅ **Rápido de implementar** - 3 agentes simples  
✅ **Sin código generado** - El LLM hace todo el razonamiento  
✅ **Fácil de debuggear** - Ves exactamente qué entiende el LLM  
✅ **Flexible** - Se adapta a cualquier layout  
✅ **Validación automática** - Pydantic valida las salidas  

## 🔮 Próximos Pasos (Evolutivo)

Una vez validado este POC, el evolutivo agregaría:

1. **Agent 4 - Code Generator**
   - Genera código Python para casos complejos
   - Usa pandas para operaciones pesadas
   - Más rápido y escalable

2. **Caché de resultados**
   - Evitar re-procesar archivos idénticos

3. **Validación avanzada**
   - Detección de anomalías en datos
   - Sugerencias de corrección

4. **Soporte multi-formato**
   - CSV, XML, JSON de entrada
   - Diferentes esquemas de salida

## 📝 Notas

- **API Keys**: Usa las variables de entorno del proyecto TALI principal
- **Costos**: ~$0.10-0.50 por archivo Excel (depende del tamaño)
- **Tiempo**: ~30-60 segundos por hoja (depende de GPT-4o)

## 🐛 Troubleshooting

### Error: "No module named 'minimal'"
```bash
# Ejecuta desde la raíz del proyecto TALI
cd /path/to/TALI
python minimal/test_minimal.py planilla_3.xlsx
```

### Error: "Invalid JSON response"
- El LLM a veces falla en generar JSON válido
- Solución: Re-ejecutar o ajustar temperature
- Todos los agentes usan `response_format: json_object` para forzar JSON

### Datos faltantes en el CSV
- Revisa los logs de cada agente
- El Agent 1 debe identificar correctamente los laboreos
- El Agent 2 debe encontrar los insumos asociados

## 📧 Contacto

Este es un POC minimal para validar el enfoque LLM-first.  
Para el sistema completo, ver: `/src/` (arquitectura original con Semantic Analyzer + Smart Extractor)
