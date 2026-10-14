"""
Test Minimal Pipeline

Pipeline LLM-first de 3 agentes para extraer datos de Excel agrícolas:
1. Context Extractor: Extrae contexto general y lista de laboreos
2. Laboreo Detail Extractor: Extrae detalles de cada laboreo con sus insumos
3. Merger: Combina todo y genera CSV de 18 columnas

Regla clave: 1 laboreo con N insumos = N filas en el CSV
"""

import sys
sys.path.insert(0, '.')

from minimal.agents.context_extractor import ContextExtractorAgent
from minimal.agents.laboreo_detail_extractor import LaboreoDetailExtractorAgent
from minimal.agents.merger_agent import MergerAgent
from pathlib import Path
import pandas as pd
from datetime import datetime


def test_minimal_pipeline(excel_path: str, sheet_name: str = None):
    """
    Ejecuta el pipeline minimal completo.
    
    Args:
        excel_path: Path al archivo Excel
        sheet_name: Nombre de la hoja (si None, procesa todas)
    """
    print("="*100)
    print("🚀 TALI MINIMAL PIPELINE - LLM First Approach")
    print("="*100)
    print(f"Archivo: {excel_path}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*100)
    print()
    
    # Si no se especifica sheet, obtener todas las hojas
    if sheet_name is None:
        xls = pd.ExcelFile(excel_path)
        sheet_names = xls.sheet_names
        print(f"📄 Hojas detectadas: {len(sheet_names)}")
        for name in sheet_names:
            print(f"   - {name}")
        print()
    else:
        sheet_names = [sheet_name]
    
    # Inicializar agentes
    context_agent = ContextExtractorAgent()
    detail_agent = LaboreoDetailExtractorAgent()
    merger_agent = MergerAgent()
    
    # Procesar cada hoja
    all_results = []
    
    for i, sheet in enumerate(sheet_names, 1):
        print(f"\n{'='*100}")
        print(f"📊 PROCESANDO HOJA {i}/{len(sheet_names)}: {sheet}")
        print(f"{'='*100}\n")
        
        try:
            # Agent 1: Context
            print("🧠 [1/3] Context Extractor Agent")
            print("-" * 100)
            context = context_agent.extract(excel_path, sheet)
            print(f"✓ Contexto extraído:")
            print(f"   Campo: {context.campo}")
            print(f"   Campaña: {context.campania}")
            print(f"   Lote: {context.lote}")
            print(f"   Laboreos identificados: {len(context.laboreos)}")
            for j, laboreo in enumerate(context.laboreos, 1):
                print(f"      {j}. {laboreo}")
            print()
            
            # Agent 2: Details
            print("🔍 [2/3] Laboreo Detail Extractor Agent")
            print("-" * 100)
            details = detail_agent.extract_details(excel_path, sheet, context)
            total_insumos = sum(len(lab.insumos) for lab in details.laboreos)
            print(f"✓ Detalles extraídos:")
            print(f"   Total laboreos procesados: {len(details.laboreos)}")
            print(f"   Total insumos encontrados: {total_insumos}")
            print(f"   Ratio insumos/laboreo: {total_insumos/len(details.laboreos):.1f}")
            print()
            
            # Agent 3: Merge
            print("🔗 [3/3] Merger Agent")
            print("-" * 100)
            filename = Path(excel_path).stem
            output_path = f"minimal/output/{filename}_{sheet.replace(' ', '_')}_minimal.csv"
            
            result = merger_agent.merge_and_export(
                context=context,
                details=details,
                output_path=output_path,
                productor=f"auto-productor-{filename}"
            )
            
            print(f"✓ Merge completado:")
            print(f"   Registros generados: {result.total_records}")
            print(f"   {result.summary}")
            print(f"   CSV guardado: {output_path}")
            
            all_results.append({
                'sheet': sheet,
                'records': result.total_records,
                'csv_path': output_path
            })
            
            # Mostrar muestra
            print(f"\n   📋 Muestra de datos (primeros 3 registros):")
            for k, record in enumerate(result.records[:3], 1):
                print(f"      {k}. Laboreo: {record.Laboreo}")
                print(f"         Insumo: {record.Insumo} ({record.Tipo})")
                print(f"         Fecha: {record.Fecha} | Ha: {record.Hectareas} | Dosis: {record.Dosis_Insumo}")
            
            print(f"\n✅ Hoja '{sheet}' procesada exitosamente")
            
        except Exception as e:
            print(f"\n❌ ERROR procesando hoja '{sheet}':")
            print(f"   {str(e)}")
            import traceback
            traceback.print_exc()
            continue
    
    # Resumen final
    print("\n" + "="*100)
    print("📊 RESUMEN FINAL")
    print("="*100)
    print(f"Hojas procesadas: {len(all_results)}/{len(sheet_names)}")
    total_records = sum(r['records'] for r in all_results)
    print(f"Total registros generados: {total_records}")
    print("\nArchivos generados:")
    for result in all_results:
        print(f"  - {result['sheet']}: {result['records']} registros → {result['csv_path']}")
    
    print("\n" + "="*100)
    print("✅ PIPELINE COMPLETADO")
    print("="*100)
    
    return all_results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Uso: python test_minimal.py <excel_path> [sheet_name]")
        print("\nEjemplos:")
        print("  python test_minimal.py planilla_3.xlsx")
        print("  python test_minimal.py planilla_3.xlsx 'CAMPO 1'")
        sys.exit(1)
    
    excel_path = sys.argv[1]
    sheet_name = sys.argv[2] if len(sys.argv) > 2 else None
    
    test_minimal_pipeline(excel_path, sheet_name)
