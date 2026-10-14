# PUMA Data Harmonizer (PUMA_POC)

Aplicación web que toma planillas Excel de laboreos agrícolas (formatos heterogéneos, una hoja por campo) y las normaliza a un CSV estándar usando un pipeline de 3 agentes LLM (OpenAI vía LangChain). El usuario sube el Excel, ve el progreso en tiempo real, revisa/edita los registros en una tabla y descarga el CSV final.

---

## Índice

1. [Arquitectura](#arquitectura)
2. [Estructura del proyecto](#estructura-del-proyecto)
3. [Requisitos](#requisitos)
4. [Configuración (`.env`)](#configuración-env)
5. [Cómo levantar con Docker (recomendado)](#cómo-levantar-con-docker-recomendado)
6. [Cómo levantar sin Docker](#cómo-levantar-sin-docker)
7. [Uso](#uso)
8. [¿Dónde quedan los outputs?](#dónde-quedan-los-outputs)
9. [Formato del CSV de salida](#formato-del-csv-de-salida)
10. [API](#api)
11. [Observabilidad (Langfuse)](#observabilidad-langfuse)
12. [Troubleshooting](#troubleshooting)

---

## Arquitectura

```
Navegador (static/index.html)
   │  POST /api/upload (Excel)          WebSocket /ws/{session_id} (progreso)
   ▼                                     ▲
FastAPI (app.py) ────────────────────────┘
   │  por cada hoja del Excel:
   ├─ 1. ContextExtractorAgent       → campo, lotes, cultivo, laboreos identificados
   ├─ 2. LaboreoDetailExtractorAgent → insumos y dosis de cada laboreo
   └─ 3. MergerAgent                 → registros normalizados (formato CSV final)
   │
   ▼
JSON con los registros → tabla editable en el navegador → POST /api/save → descarga CSV
```

- **Backend:** FastAPI + Uvicorn (`app.py`).
- **Frontend:** HTML/JS estático (`static/index.html`), servido por el mismo FastAPI.
- **Pipeline:** paquete `minimal/` (agentes, esquemas Pydantic y configuración).
- **Modelo LLM:** `gpt-4o-mini` (definido en `app.py`, variable `model`).

## Estructura del proyecto

```
PUMA_POC/
├── app.py                  # API FastAPI + WebSocket de progreso
├── static/index.html       # Interfaz web
├── minimal/                # Pipeline de agentes (requerido)
│   ├── agents/
│   │   ├── context_extractor.py
│   │   ├── laboreo_detail_extractor.py
│   │   └── merger_agent.py
│   ├── schemas/output_schema.py
│   ├── config.py           # Settings leídos desde .env
│   ├── observability.py    # Integración con Langfuse
│   ├── test_minimal.py     # Ejecución del pipeline por línea de comandos
│   └── output/             # CSVs generados por ejecuciones de prueba (CLI)
├── uploads/                # Carpeta creada por la app (hoy no se usa)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env / .env.example
├── start_web.sh            # Arranque sin Docker (legacy)
├── test_web.py / test_websocket.html   # Pruebas manuales de API y WebSocket
└── *.xlsx                  # Planillas de ejemplo
```

> Las carpetas `minimal bu/` y `minimal_bu_2/` (si existen) son backups anteriores del 16/01/2026. La versión vigente es `minimal/` + `app.py` de la raíz.

## Requisitos

- **Docker Desktop** (con Docker Compose v2), o bien **Python 3.12** si se corre sin Docker.
- Una **API key de OpenAI** con acceso a `gpt-4o-mini`.
- (Opcional) Credenciales de **Langfuse** para trazas.

## Configuración (`.env`)

Copiar el ejemplo y completar:

```bash
cp .env.example .env
```

| Variable | Obligatoria | Default | Descripción |
|---|---|---|---|
| `OPENAI_API_KEY` | Sí | — | API key de OpenAI |
| `OPENAI_MODEL` | No | `gpt-4o` | Modelo por defecto de `minimal/config.py` (la web usa `gpt-4o-mini` fijo en `app.py`) |
| `OPENAI_TEMPERATURE` | No | `0.1` | Temperatura del LLM |
| `OPENAI_MAX_TOKENS` | No | `4000` | Tokens máximos por respuesta |
| `LANGFUSE_ENABLED` | No | `false` | Activa el tracking en Langfuse |
| `LANGFUSE_PUBLIC_KEY` | Si Langfuse activo | — | Public key |
| `LANGFUSE_SECRET_KEY` | Si Langfuse activo | — | Secret key |
| `LANGFUSE_HOST` | No | `https://cloud.langfuse.com` | Host de Langfuse (ej. `https://us.cloud.langfuse.com`) |
| `CSV_SEPARATOR` | No | `;` | Separador del CSV |
| `CSV_ENCODING` | No | `utf-8` | Encoding del CSV |
| `DATE_FORMAT` | No | `%d/%m/%Y` | Formato de fechas |

> `.env` está en `.gitignore` y en `.dockerignore`: nunca se commitea ni se copia a la imagen; Docker Compose lo inyecta como variables de entorno al levantar.

## Cómo levantar con Docker (recomendado)

Desde la carpeta `PUMA_POC/`:

```bash
# 1. Construir la imagen y levantar en segundo plano
docker compose up -d --build

# 2. Ver logs en vivo
docker compose logs -f

# 3. Verificar que está arriba
curl http://localhost:8000/health
# {"status":"ok","service":"PUMA Data Harmonizer API","active_connections":0}
```

Abrir **http://localhost:8000** (interfaz) o **http://localhost:8000/docs** (Swagger).

### Desarrollo en tiempo real (hot reload)

El `docker-compose.yml` monta la carpeta del proyecto dentro del contenedor (`.:/app`) y corre Uvicorn con `--reload`:

- Al guardar `app.py` o cualquier `.py` de `minimal/`, el servidor se reinicia solo (se ve `Reloading...` en los logs).
- Los cambios en `static/index.html` se ven refrescando el navegador (no requieren reinicio).
- `.venv`, `minimal bu` y `minimal_bu_2` están excluidos del reload.

Solo hace falta reconstruir la imagen (`docker compose up -d --build`) si cambia `requirements.txt`.

### Comandos útiles

```bash
docker compose ps                 # estado del contenedor
docker compose restart            # reiniciar el proceso (no relee .env)
docker compose down               # detener y eliminar el contenedor
docker compose exec app bash      # shell dentro del contenedor
docker compose exec app python minimal/test_minimal.py   # pipeline por CLI
```

> Cambios en `.env` no se toman con el hot reload: hay que hacer `docker compose up -d` (recrea el contenedor con las nuevas variables).

## Cómo levantar sin Docker

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# con hot reload
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# o con el script legacy (sin reload)
./start_web.sh
```

Debe ejecutarse desde `PUMA_POC/` para que se resuelvan `minimal/`, `static/` y `.env`.

## Uso

1. Abrir http://localhost:8000.
2. Subir un Excel (`.xlsx` o `.xls`). Hay ejemplos en la raíz: `planilla_1.xlsx`, `Soja Compañia - Lote a Lote.xlsx`.
3. Se procesan **todas las hojas**; por cada una se ve el avance de los 3 agentes vía WebSocket. Tiempo orientativo: 45–70 s por hoja.
4. Revisar y editar los registros en la tabla.
5. Click en **Descargar** → se baja el CSV final.

## ¿Dónde quedan los outputs?

**La aplicación web no guarda resultados en disco.** Todo el flujo es en memoria / temporal:

| Qué | Dónde | Persistencia |
|---|---|---|
| Excel subido | `/tmp/upload_<id>_<nombre>.xlsx` dentro del contenedor | Se borra al terminar el procesamiento |
| CSV intermedio del `MergerAgent` | `/tmp/tali_<id>.csv` dentro del contenedor | Se borra al terminar cada hoja |
| Registros procesados | Respuesta JSON de `/api/upload` → tabla del navegador | Solo en la pestaña abierta |
| **CSV final** | **Descarga del navegador** (carpeta de Descargas), generado por `/api/save` | Es el único output persistente |
| CSVs de pruebas por CLI | `minimal/output/` | Persisten (y, al estar montado el volumen, se ven en el disco local) |
| Trazas de LLM | Langfuse (si `LANGFUSE_ENABLED=true`) | En la nube de Langfuse |

Consecuencias prácticas:

- Si se cierra o recarga la pestaña antes de descargar, **se pierde el resultado** y hay que reprocesar (y volver a pagar las llamadas al LLM).
- La carpeta `uploads/` se crea al iniciar, pero el código actual no la usa.
- Para persistir resultados del lado servidor habría que modificar `/api/upload` o `/api/save` para escribir en `uploads/` o `minimal/output/` (ambas ya quedan en el disco local gracias al volumen de Docker).

## Formato del CSV de salida

Separador `;`, encoding UTF-8, un registro por insumo aplicado en cada laboreo:

| Columna | Descripción |
|---|---|
| `Id` | Identificador del registro |
| `Productor` | Productor (en la web: `web-upload-AAAAMMDD`) |
| `Campaña` | Campaña agrícola |
| `Campo` | Campo (normalmente, el nombre de la hoja) |
| `Lote` | Lote |
| `Ambiente` | Ambiente |
| `Cultivo` | Cultivo |
| `Tipo Cultivo` | Tipo de cultivo |
| `Laboreo` | Labor realizada (siembra, pulverización, etc.) |
| `Hectareas (Ha)` | Superficie |
| `Pasadas (cant.)` | Cantidad de pasadas |
| `Fecha` | Fecha (`dd/mm/aaaa`) |
| `Tipo` | Tipo de insumo |
| `Insumo` | Producto aplicado |
| `Dosis Insumo (Kg o litro/Ha aplicada)` | Dosis del insumo |
| `Fertilizante` | Fertilizante |
| `Dosis Fertilizantes (Kg o litro/Ha aplicada)` | Dosis de fertilizante |
| `Model Id` | Modelo LLM que generó el registro |

## API

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Interfaz web |
| `GET` | `/docs` | Swagger UI |
| `GET` | `/health` | Health check |
| `POST` | `/api/upload` | `multipart/form-data`: `file` (Excel) y `session_id` (opcional). Procesa todas las hojas y devuelve los registros en JSON |
| `POST` | `/api/save` | JSON `{ "records": [...], "filename": "laboreos_editados.csv" }`. Devuelve el CSV como descarga |
| `WS` | `/ws/{session_id}` | Progreso en tiempo real: `{stage, progress, message, timestamp}`. Acepta `ping` → `pong` |

Ejemplo por línea de comandos:

```bash
# procesar un Excel
curl -F "file=@planilla_1.xlsx" http://localhost:8000/api/upload -o resultado.json

# convertir los registros de una hoja a CSV
jq '{records: .results[0].records, filename: "salida.csv"}' resultado.json \
  | curl -s -X POST http://localhost:8000/api/save \
      -H "Content-Type: application/json" -d @- -o salida.csv
```

## Observabilidad (Langfuse)

Con `LANGFUSE_ENABLED=true` y las keys configuradas, cada llamada de los agentes se registra en Langfuse (tokens, costo, latencia), agrupada por `session_id`. Si está habilitado pero faltan credenciales, la app sigue funcionando y lo avisa en los logs. El código (`minimal/observability.py`) usa la API v2 de Langfuse, por eso `requirements.txt` fija `langfuse<3`.

## Troubleshooting

| Síntoma | Causa / solución |
|---|---|
| `ModuleNotFoundError: No module named 'minimal'` | Falta la carpeta `minimal/` en `PUMA_POC/`. Restaurarla; con hot reload el contenedor levanta solo |
| `Bind for 0.0.0.0:8000 failed: port is already allocated` | Otro proceso/contenedor usa el 8000: `docker ps` y detenerlo, o cambiar el puerto en `docker-compose.yml` (`"8001:8000"`) |
| Error de autenticación de OpenAI | Revisar `OPENAI_API_KEY` en `.env` y recrear con `docker compose up -d` |
| Cambié `.env` y no se aplica | `docker compose up -d` (un `restart` no relee `env_file`) |
| Cambié `requirements.txt` | `docker compose up -d --build` |
| El progreso no se actualiza | Verificar el WebSocket con `test_websocket.html` o en la consola del navegador |
| `ResolutionImpossible` al hacer build | Conflicto de versiones en `requirements.txt` (ej. `langchain 0.3.x` requiere `numpy<2`) |
