"""
Langfuse Observability Integration

Helper para inicializar y configurar Langfuse para tracking de LLM calls,
costos, tokens y métricas generales.
"""

from typing import Optional, List
from langfuse.callback import CallbackHandler
from langfuse.decorators import langfuse_context
from minimal.config import get_settings


def get_langfuse_handler(
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    tags: Optional[List[str]] = None
) -> Optional[CallbackHandler]:
    """
    Crea un CallbackHandler de Langfuse si está habilitado.
    
    Args:
        session_id: ID de sesión para agrupar traces
        user_id: ID de usuario (opcional)
        tags: Lista de tags para el trace
        
    Returns:
        CallbackHandler de Langfuse o None si está deshabilitado
    """
    settings = get_settings()
    
    if not settings.langfuse_enabled:
        return None
    
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        print("⚠️  Langfuse habilitado pero faltan credenciales (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY)")
        return None
    
    try:
        handler = CallbackHandler(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
            session_id=session_id,
            user_id=user_id,
            tags=tags or []
        )
        return handler
    except Exception as e:
        print(f"⚠️  Error inicializando Langfuse: {e}")
        return None


def set_langfuse_metadata(
    trace_name: str,
    metadata: dict,
    session_id: Optional[str] = None
):
    """
    Establece metadata para el trace actual de Langfuse.
    
    Args:
        trace_name: Nombre del trace
        metadata: Diccionario con metadata adicional
        session_id: ID de sesión
    """
    settings = get_settings()
    
    if not settings.langfuse_enabled:
        return
    
    try:
        langfuse_context.update_current_trace(
            name=trace_name,
            metadata=metadata,
            session_id=session_id
        )
    except Exception as e:
        print(f"⚠️  Error actualizando metadata de Langfuse: {e}")


def get_langfuse_callbacks(
    agent_name: str,
    sheet_name: Optional[str] = None,
    session_id: Optional[str] = None
) -> List:
    """
    Obtiene la lista de callbacks para usar con LangChain.
    
    Args:
        agent_name: Nombre del agente (context, details, merge)
        sheet_name: Nombre de la hoja siendo procesada
        session_id: ID de sesión para agrupar
        
    Returns:
        Lista de callbacks (puede estar vacía si Langfuse está deshabilitado)
    """
    tags = [f"agent:{agent_name}"]
    if sheet_name:
        tags.append(f"sheet:{sheet_name}")
    
    handler = get_langfuse_handler(
        session_id=session_id,
        tags=tags
    )
    
    if handler:
        return [handler]
    return []
