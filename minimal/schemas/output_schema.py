"""
Schemas Pydantic para validar salidas de los agentes LLM
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date


class GeneralContext(BaseModel):
    """Contexto general extraído del Excel (Agent 1)"""
    
    campo: str = Field(description="Nombre del campo/establecimiento")
    lote: str = Field(default="único", description="Nombre del lote")
    ambiente: str = Field(default="único", description="Ambiente del lote")
    campania: str = Field(description="Campaña agrícola (ej: 2023/2024)")
    cultivo: Optional[str] = Field(default=None, description="Tipo de cultivo (Soja, Trigo, etc)")
    tipo_cultivo: Optional[str] = Field(default=None, description="Primera, Segunda, etc")
    productor: Optional[str] = Field(default=None, description="Nombre del productor")
    
    laboreos: List[str] = Field(
        description="Lista de laboreos/actividades encontradas (ej: ['Pulverización Terrestre', 'Siembra'])"
    )


class InsumoDetail(BaseModel):
    """Detalle de un insumo usado en un laboreo"""
    
    nombre_insumo: str = Field(description="Nombre del producto/insumo")
    tipo_insumo: str = Field(
        description="Tipo: Herbicidas, Insecticidas, Fungicidas, Coadyuvantes, Fertilizantes, Semillas"
    )
    dosis: Optional[float] = Field(default=None, description="Dosis en Kg o litros/Ha")
    fecha: Optional[str] = Field(default=None, description="Fecha de aplicación (formato DD/MM/YYYY)")


class LaboreoDetail(BaseModel):
    """Detalle completo de un laboreo con sus insumos (Agent 2)"""
    
    laboreo: str = Field(description="Nombre del laboreo/actividad")
    fecha: Optional[str] = Field(default=None, description="Fecha del laboreo")
    hectareas: Optional[float] = Field(default=None, description="Hectáreas trabajadas")
    pasadas: Optional[int] = Field(default=1, description="Cantidad de pasadas")
    
    insumos: List[InsumoDetail] = Field(
        description="Lista de insumos usados en este laboreo"
    )


class LaboreoDetailsResponse(BaseModel):
    """Respuesta completa del Agent 2"""
    
    campo: str
    laboreos: List[LaboreoDetail] = Field(
        description="Lista de todos los laboreos con sus detalles"
    )


class FinalRecord(BaseModel):
    """Registro final del CSV (18 columnas)"""
    
    Id: str
    Productor: str
    Campania: str = Field(alias="Campaña")
    Campo: str
    Lote: str
    Ambiente: str
    Cultivo: Optional[str] = ""
    Tipo_Cultivo: Optional[str] = Field(default="", alias="Tipo Cultivo")
    Laboreo: str
    Hectareas: Optional[float] = Field(default=None, alias="Hectareas (Ha)")
    Pasadas: Optional[int] = Field(default=1, alias="Pasadas (cant.)")
    Fecha: Optional[str] = ""
    Tipo: str  # Tipo de insumo
    Insumo: str  # Nombre del insumo
    Dosis_Insumo: Optional[float] = Field(default=None, alias="Dosis Insumo (Kg o litro/Ha aplicada)")
    Fertilizante: Optional[str] = ""
    Dosis_Fertilizante: Optional[float] = Field(default=None, alias="Dosis Fertilizantes (Kg o litro/Ha aplicada)")
    Model_Id: Optional[str] = Field(default="", alias="Model Id")
    
    class Config:
        populate_by_name = True


class MergedOutput(BaseModel):
    """Output final del Agent 3 - Merger"""
    
    records: List[FinalRecord] = Field(
        description="Lista de registros expandidos (1 laboreo con N insumos = N records)"
    )
    total_records: int
    summary: str = Field(
        description="Resumen de la operación (ej: '3 laboreos expandidos a 45 registros')"
    )
