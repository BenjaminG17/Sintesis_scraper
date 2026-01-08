#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Procesa CSV jerárquicos (CONTRATA / PLANTA) y los carga en una sola tabla BigQuery:
<project>.<dataset>.personal_municipal

- Extrae metadatos desde el nombre de archivo (municipio, tipo_contrato, año, mes_numero).
- Corrige columnas intercambiadas en PLANTA (viáticos vs observaciones).
- Limpia strings (incluyendo 'Ańo' -> 'Año' y luego -> 'anio' sin ñ).
- Convierte montos y fechas a tipos adecuados.
- Loguea errores por archivo y continúa con el resto.
- Carga por municipio en modo APPEND.
- Guarda los datos transformados en data/final como respaldo local en CSV.
"""

import argparse
import json
import logging
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

import pandas as pd
from google.cloud import bigquery
from google.api_core.exceptions import NotFound
import datetime as dt

# -----------------------
# Configuración de rutas
# -----------------------

def get_project_paths() -> Dict[str, Path]:
    """Define las rutas del proyecto basadas en la ubicación del script"""
    script_dir = Path(__file__).parent.parent.parent
    paths = {
        'project_root': script_dir,
        'data_raw': script_dir / 'data' / 'raw',
        'data_final': script_dir / 'data' / 'final',
        'logs': script_dir / 'logs',
        'configs': script_dir / 'configs'
    }
    
    # Crear directorios si no existen
    paths['data_final'].mkdir(parents=True, exist_ok=True)
    
    return paths


# -----------------------
# Utilidades generales
# -----------------------

MONTH_MAP = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "setiembre": 9,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12
}

VIATICOS_COL_NAME = "Viáticos del mes (no inc. en rem. bruta)"
OBS_COL_NAME = "Observaciones"


def load_config(path: str) -> Dict:
    """Carga configuración desde archivo JSON"""
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg


def setup_etl_logging() -> logging.Logger:
    """Configura logging específico para el proceso ETL"""
    paths = get_project_paths()
    
    # Nombre distintivo para el log del ETL
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = paths['logs'] / f"etl_process_{timestamp}.log"
    
    # Configurar logger específico para ETL
    logger = logging.getLogger('etl_process')
    logger.setLevel(logging.INFO)
    
    # Evitar duplicación de handlers
    if not logger.handlers:
        # Handler para archivo
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] ETL - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        # Handler para consola
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    return logger


def month_name_to_number(mes: str) -> int:
    if mes is None:
        raise ValueError("Mes nulo")
    key = mes.strip().lower()
    key = key.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    if key not in MONTH_MAP:
        raise ValueError(f"Nombre de mes desconocido: {mes}")
    return MONTH_MAP[key]


def normalize_text_series(s: pd.Series) -> pd.Series:
    """
    Limpia texto:
    - convierte NaN a ""
    - reemplaza 'ń' / 'Ń' por 'ñ' / 'Ñ'
    - colapsa espacios en blanco y hace strip
    """
    s = s.astype(str)
    s = s.replace({"nan": ""})
    s = s.str.replace("ń", "ñ").str.replace("Ń", "Ñ")
    s = s.str.replace(r"\s+", " ", regex=True)
    s = s.str.strip()
    return s


def parse_amount(value: Optional[str], zero_if_missing: bool = False) -> Optional[float]:
    """
    Convierte strings tipo "$ 248.874", "18.080", "-", "No informa" a float.
    """
    if value is None:
        return 0.0 if zero_if_missing else None

    value = str(value).strip()

    if value == "":
        return 0.0 if zero_if_missing else None

    if value in ("-", "0", "0,0", "0,00"):
        return 0.0

    if value.lower() in ("no tiene", "no informa", "sin información", "sin informacion"):
        return 0.0 if zero_if_missing else None
    
    clean = re.sub(r"[^\d,.\-]", "", value)

    if clean == "":
        return 0.0 if zero_if_missing else None

    if "." in clean and "," in clean:
        clean = clean.replace(".", "")
        clean = clean.replace(",", ".")
    else:
        if "." in clean and "," not in clean:
            clean = clean.replace(".", "")
        if "," in clean and "." not in clean:
            clean = clean.replace(",", ".")
    try:
        return float(clean)
    except ValueError:
        logging.warning(f"No se pudo parsear monto '{value}' (limpio: '{clean}'). Se deja NULL.")
        return 0.0 if zero_if_missing else None


def parse_date(value: Optional[str]) -> Optional[str]:
    """
    Intenta convertir fechas en varios formatos.
    Retorna fecha en formato ISO: YYYY-MM-DD
    """
    if value is None:
        return None

    s = str(value).strip()
    if s == "" or s in ("-", "0"):
        return None

    lower = s.lower()
    if lower in ("indefinido", "no informa", "sin información", "sin informacion"):
        return None

    formatos = [
        "%d/%m/%Y", "%d/%m/%y",
        "%d-%m-%Y", "%d-%m-%y",
        "%Y-%m-%d", "%Y/%m/%d",
    ]
    for fmt in formatos:
        try:
            d = dt.datetime.strptime(s, fmt).date()
            return d.isoformat()
        except ValueError:
            continue

    logging.warning(f"No se pudo parsear fecha '{value}', se deja NULL.")
    return None


# -----------------------
# Procesamiento de archivos
# -----------------------

def extract_metadata_from_filename(file_path: Path) -> Dict:
    """
    Espera nombres tipo: MU001_CONTRATA_2018_Enero.csv
    Devuelve: municipio, tipo_contrato, anio (int), mes (string), mes_numero (int)
    """
    fname = file_path.name
    base = fname.rsplit(".", 1)[0]
    parts = base.split("_")

    if len(parts) < 4:
        raise ValueError(f"Nombre de archivo no cumple patrón esperado: {fname}")

    municipio = parts[0]
    tipo_contrato = parts[1].upper()
    year_str = parts[2]
    mes_str = parts[3]

    try:
        anio_int = int(year_str)
    except ValueError:
        raise ValueError(f"Año no es numérico: {year_str}")

    mes_num = month_name_to_number(mes_str)

    return {
        "municipio": municipio,
        "tipo_contrato": tipo_contrato,
        "anio_int": anio_int,
        "mes_str": mes_str,
        "mes_num": mes_num,
    }


def read_csv_with_fallback(file_path: Path) -> pd.DataFrame:
    """
    Intenta leer el CSV primero como UTF-8; si falla, como Latin-1.
    """
    try:
        df = pd.read_csv(file_path, sep=";", encoding="utf-8", dtype=str)
        return df
    except UnicodeDecodeError:
        logging.info(f"UTF-8 falló para {file_path}, se intenta latin1.")
        df = pd.read_csv(file_path, sep=";", encoding="latin1", dtype=str)
        return df


def normalize_planta_columns(df: pd.DataFrame, tipo_contrato: str) -> pd.DataFrame:
    """
    En archivos PLANTA, las columnas 20 y 21 vienen intercambiadas.
    Este método las corrige si detecta ese patrón.
    """
    df = df.loc[:, ~df.columns.str.contains(r"^Unnamed")]
    
    if df.shape[1] != 21:
        logging.warning(f"Archivo tiene {df.shape[1]} columnas después de limpiar Unnamed; se esperaban 21.")

    if tipo_contrato.upper() == "PLANTA":
        cols = list(df.columns)
        if len(cols) >= 21 and cols[-2] == OBS_COL_NAME and cols[-1] == VIATICOS_COL_NAME:
            logging.info("Detectado archivo PLANTA con columnas intercambiadas. Corrigiendo orden Viáticos/Observaciones.")
            df[[VIATICOS_COL_NAME, OBS_COL_NAME]] = df[[OBS_COL_NAME, VIATICOS_COL_NAME]]
        else:
            logging.info("Archivo PLANTA no cumple patrón esperado de columnas intercambiadas. No se reordenan.")
    
    return df


def rename_and_clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Renombra columnas originales a nombres finales para BigQuery.
    """
    rename_map = {
        "Año": "anio",
        "Ano": "anio",
        "Mes": "mes",
        "Estamento": "estamento",
        "Nombre completo": "nombre_completo",
        "Cargo o función": "cargo_funcion",
        "Grado EUS o jornada": "grado_eus_jornada",
        "Calificación profesional o formación": "calificacion_profesional",
        "Región": "region",
        "Asignaciones especiales del mes (inc. en rem. bruta)": "asignaciones_especiales",
        "Remuneración bruta del mes (incluye bonos e incentivos, asig. especiales, horas extras)": "remuneracion_bruta",
        "Remuneración líquida del mes": "remuneracion_liquida",
        "Rem. adicionales del mes (no inc. en rem. bruta)": "rem_adicionales",
        "Remuneración Bonos incentivos del mes (inc. en rem. bruta)": "rem_bonos_incentivos",
        "Derecho a horas extraordinarias": "derecho_horas_extra",
        "Montos y horas extraordinarias diurnas del mes(inc. en rem. bruta)": "horas_extra_diurnas",
        "Montos y horas extraordinarias nocturnas del mes(inc. en rem. bruta)": "horas_extra_nocturnas",
        "Montos y horas extraordinarias festivas del mes (inc. en rem. bruta)": "horas_extra_festivas",
        "Fecha de inicio dd/mm/aa": "fecha_inicio",
        "Fecha de término dd/mm/aa": "fecha_termino",
        VIATICOS_COL_NAME: "viaticos",
        OBS_COL_NAME: "observaciones",
    }
    
    new_cols = []
    for c in df.columns:
        c_norm = (
            c.replace("ń", "ñ").replace("Ń", "Ñ")
            .replace("Ã±", "ñ")
            .strip()
        )
        new_cols.append(c_norm)
    df.columns = new_cols

    df = df.rename(columns=rename_map)

    for col in df.select_dtypes(include="object").columns:
        df[col] = normalize_text_series(df[col])

    return df


def convert_types(df: pd.DataFrame, meta: Dict) -> pd.DataFrame:
    """
    Convierte tipos a los requeridos.
    """
    df["anio"] = int(meta["anio_int"])
    df["mes_numero"] = int(meta["mes_num"])

    df["remuneracion_bruta"] = df["remuneracion_bruta"].apply(lambda x: parse_amount(x, zero_if_missing=False))
    df["remuneracion_liquida"] = df["remuneracion_liquida"].apply(lambda x: parse_amount(x, zero_if_missing=False))
    df["viaticos"] = df["viaticos"].apply(lambda x: parse_amount(x, zero_if_missing=True))

    df["fecha_inicio"] = df["fecha_inicio"].apply(parse_date)
    df["fecha_termino"] = df["fecha_termino"].apply(parse_date)

    df["fecha_inicio"] = pd.to_datetime(df["fecha_inicio"], errors="coerce").dt.date
    df["fecha_termino"] = pd.to_datetime(df["fecha_termino"], errors="coerce").dt.date

    return df


def add_context_columns(df: pd.DataFrame, meta: Dict) -> pd.DataFrame:
    df["municipio"] = meta["municipio"]
    df["tipo_contrato"] = meta["tipo_contrato"]

    final_cols = [
        "municipio",
        "tipo_contrato",
        "anio",
        "mes_numero",
        "mes",
        "estamento",
        "nombre_completo",
        "cargo_funcion",
        "grado_eus_jornada",
        "calificacion_profesional",
        "region",
        "asignaciones_especiales",
        "remuneracion_bruta",
        "remuneracion_liquida",
        "rem_adicionales",
        "rem_bonos_incentivos",
        "derecho_horas_extra",
        "horas_extra_diurnas",
        "horas_extra_nocturnas",
        "horas_extra_festivas",
        "fecha_inicio",
        "fecha_termino",
        "viaticos",
        "observaciones",
    ]

    missing = [c for c in final_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas después de transformaciones: {missing}")

    df = df[final_cols]
    return df


def save_transformed_data(df: pd.DataFrame, meta: Dict, final_dir: Path) -> Path:
    """
    Guarda los datos transformados en la carpeta final con estructura organizada.
    Estructura: data/final/<municipio>/<tipo_contrato>/<año>/
    """
    municipio = meta["municipio"]
    tipo_contrato = meta["tipo_contrato"].lower()
    anio = meta["anio_int"]
    
    # Crear estructura de directorios
    output_dir = final_dir / municipio / tipo_contrato / str(anio)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Nombre del archivo (mismo formato que el original pero con datos ya transformados)
    mes_num = meta["mes_num"]
    output_file = output_dir / f"{municipio}_{tipo_contrato.upper()}_{anio}_{mes_num:02d}.csv"
    
    # Guardar como CSV (mismo formato que se subirá a BigQuery)
    df.to_csv(output_file, index=False, sep=';', encoding='utf-8')
    
    logging.info(f"Datos transformados guardados en: {output_file}")
    return output_file


def process_single_file(file_path: Path, final_dir: Path) -> Optional[pd.DataFrame]:
    """
    Procesa un CSV individual. Guarda los datos transformados en la carpeta final.
    """
    logger = logging.getLogger('etl_process')

    try:
        meta = extract_metadata_from_filename(file_path)
    except Exception as e:
        logger.error(f"[{file_path}] Error extrayendo metadatos: {e}")
        return None

    try:
        df = read_csv_with_fallback(file_path)
    except Exception as e:
        logger.error(f"[{file_path}] Error leyendo CSV: {e}")
        return None

    try:
        logger.info(f"[{file_path}] Iniciando transformación y estandarización de datos")
        df = normalize_planta_columns(df, meta["tipo_contrato"])
        df = rename_and_clean_columns(df)
        df = convert_types(df, meta)
        df = add_context_columns(df, meta)
        
        # Guardar datos transformados localmente
        save_transformed_data(df, meta, final_dir)
        
    except Exception as e:
        logger.error(f"[{file_path}] Error transformando datos: {e}", exc_info=True)
        return None

    logger.info(f"[{file_path}] OK - {len(df)} filas procesadas y guardadas localmente.")
    return df


# -----------------------
# BigQuery
# -----------------------

def initialize_bigquery_client(project_id: str, service_account_key_path: Optional[str] = None) -> bigquery.Client:
    """
    Inicializa el cliente de BigQuery.
    """
    if service_account_key_path and os.path.exists(service_account_key_path):
        from google.oauth2 import service_account
        credentials = service_account.Credentials.from_service_account_file(
            service_account_key_path
        )
        client = bigquery.Client(project=project_id, credentials=credentials)
        logging.info(f"BigQuery client inicializado con credenciales de servicio desde: {service_account_key_path}")
    else:
        # Usar Application Default Credentials (ADC)
        client = bigquery.Client(project=project_id)
        logging.info("BigQuery client inicializado con Application Default Credentials")
    
    return client


def ensure_table_exists(client: bigquery.Client, dataset_id: str, table_name: str) -> None:
    """
    Verifica que la tabla exista. Si no existe, lanza error.
    """
    table_id = f"{client.project}.{dataset_id}.{table_name}"
    try:
        client.get_table(table_id)
        logging.info(f"La tabla {table_id} existe.")
    except NotFound:
        raise RuntimeError(
            f"La tabla {table_id} NO existe. "
            f"Primero crea la tabla en BigQuery antes de correr este script."
        )


def load_municipio_to_bq(
    client: bigquery.Client, dataset_id: str, table_name: str, municipio: str, df: pd.DataFrame
) -> int:
    """
    Carga un DataFrame de un municipio a BigQuery.
    """
    table_id = f"{client.project}.{dataset_id}.{table_name}"
    
    # Extraer años y meses únicos del DataFrame
    años_unicos = df["anio"].unique()
    meses_unicos = df["mes_numero"].unique()
    
    # Construir consulta DELETE
    conditions = []
    for año in años_unicos:
        for mes in meses_unicos:
            conditions.append(f"(municipio = '{municipio}' AND anio = {año} AND mes_numero = {mes})")
    
    if conditions:
        delete_query = f"""
            DELETE FROM `{table_id}`
            WHERE {" OR ".join(conditions)}
        """
        
        try:
            delete_job = client.query(delete_query)
            delete_job.result()
            logging.info(f"Registros eliminados para {municipio}, años: {list(años_unicos)}, meses: {list(meses_unicos)}")
        except Exception as e:
            logging.error(f"Error al eliminar registros existentes: {e}")
    
    # Cargar nuevos datos
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
    )
    
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    result = job.result()
    
    logging.info(f"Municipio {municipio}: {result.output_rows} filas cargadas a {table_id}")
    return result.output_rows


# -----------------------
# Main
# -----------------------

def main():
    # Obtener rutas del proyecto
    paths = get_project_paths()
    
    # Configurar logging específico para ETL
    logger = setup_etl_logging()
    
    # Cargar configuración desde archivo específico para ETL
    config_path = paths['configs'] / 'etl_config.json'
    
    if not config_path.exists():
        # Crear un archivo de configuración de ejemplo si no existe
        default_config = {
            "bq_project": "tu-proyecto-gcp",
            "bq_dataset": "tu_dataset",
            "bq_table": "personal_municipal",
            "service_account_key_path": "configs/service-account-key.json",
            "log_level": "INFO"
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        
        logger.error(f"Archivo de configuración no encontrado. Se ha creado uno de ejemplo en: {config_path}")
        logger.error("Por favor, edita el archivo con tus configuraciones y vuelve a ejecutar.")
        return
    
    cfg = load_config(str(config_path))
    
    # Mostrar información de configuración
    logger.info(f"=== INICIO PROCESO ETL MUNICIPAL ===")
    logger.info(f"Directorio de datos crudos: {paths['data_raw']}")
    logger.info(f"Directorio de datos finales: {paths['data_final']}")
    logger.info(f"Directorio de logs: {paths['logs']}")
    logger.info(f"BigQuery destino: {cfg['bq_project']}.{cfg['bq_dataset']}.{cfg['bq_table']}")
    logger.info("Modo de ejecución: CARGA CONTROLADA PARA VALIDACIÓN")
    
    # Inicializar cliente de BigQuery
    service_account_key = cfg.get("service_account_key_path")
    if service_account_key and not Path(service_account_key).is_absolute():
        service_account_key = paths['project_root'] / service_account_key
    
    client = initialize_bigquery_client(cfg["bq_project"], service_account_key)
    
    # Verificar que la tabla existe
    ensure_table_exists(client, cfg["bq_dataset"], cfg["bq_table"])
    
    # 1) Recorremos estructura de datos crudos y juntamos TODOS los paths de CSV
    all_csv_paths: List[Path] = []
    if paths['data_raw'].exists():
        for dirpath, _dirnames, filenames in os.walk(paths['data_raw']):
            for fname in filenames:
                if fname.lower().endswith(".csv"):
                    all_csv_paths.append(Path(dirpath) / fname)
    
    total_files = len(all_csv_paths)
    logger.info(f"Se encontraron {total_files} archivos CSV en {paths['data_raw']}.")
    
    if total_files == 0:
        logger.error("No se encontraron archivos CSV para procesar.")
        logger.error(f"Asegúrate de que los archivos CSV estén en: {paths['data_raw']}")
        return
    
    dfs_by_muni: Dict[str, List[pd.DataFrame]] = defaultdict(list)
    failed_files: List[str] = []
    total_rows = 0
    processed_files = 0
    
    # 2) Procesar archivo por archivo
    for idx, file_path in enumerate(sorted(all_csv_paths), start=1):
        progress_pct = 100.0 * idx / total_files if total_files else 0
        logger.info(f"Procesando archivo {idx}/{total_files} ({progress_pct:.1f}%) -> {file_path.name}")
        
        df = process_single_file(file_path, paths['data_final'])
        if df is None:
            failed_files.append(str(file_path))
            continue
        
        municipio = df["municipio"].iloc[0]
        dfs_by_muni[municipio].append(df)
        total_rows += len(df)
        processed_files += 1
    
    logger.info(f"Archivos procesados OK: {processed_files}/{total_files}")
    logger.info(f"Total filas procesadas (antes de carga): {total_rows}")
    
    if failed_files:
        logger.warning("Archivos con error:")
        for f in failed_files:
            logger.warning(f" - {f}")
    
    # 3) Carga a BigQuery por municipio
    total_rows_loaded = 0
    for municipio, frames in sorted(dfs_by_muni.items()):
        if not frames:
            continue
            
        muni_df = pd.concat(frames, ignore_index=True)
        logger.info(f"Cargando municipio {municipio} ({len(muni_df)} filas) a BigQuery...")
        
        try:
            loaded = load_municipio_to_bq(client, cfg["bq_dataset"], cfg["bq_table"], municipio, muni_df)
            total_rows_loaded += loaded
            logger.info(f"✓ Municipio {municipio} cargado exitosamente a BigQuery")
        except Exception as e:
            logger.error(f"✗ Error cargando municipio {municipio} a BigQuery: {e}")
    
    # 4) Generar resumen final
    logger.info("=" * 50)
    logger.info("         RESUMEN DE EJECUCIÓN         ")
    logger.info("=" * 50)
    logger.info(f"Archivos encontrados: {total_files}")
    logger.info(f"Archivos procesados OK: {processed_files}")
    logger.info(f"Archivos con error: {len(failed_files)}")
    logger.info(f"Filas procesadas totales: {total_rows}")
    logger.info(f"Filas cargadas en BigQuery: {total_rows_loaded}")
    logger.info(f"Datos transformados guardados en: {paths['data_final']}")
    
    if failed_files:
        logger.info("Lista de archivos fallidos:")
        for f in failed_files:
            logger.info(f" - {Path(f).name}")
    
    # Guardar archivo de resumen
    resumen_file = paths['logs'] / f"resumen_etl_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(resumen_file, 'w', encoding='utf-8') as f:
        f.write(f"Resumen ETL - {datetime.now()}\n")
        f.write("=" * 40 + "\n")
        f.write(f"Archivos procesados: {processed_files}/{total_files}\n")
        f.write(f"Filas cargadas a BigQuery: {total_rows_loaded}\n")
        f.write(f"Archivos con error: {len(failed_files)}\n")
        f.write(f"Datos guardados en: {paths['data_final']}\n")
        f.write("\nArchivos con error:\n")
        for file_path in failed_files:
            f.write(f"- {Path(file_path).name}\n")
    
    logger.info(f"Resumen guardado en: {resumen_file}")
    logger.info("=== FIN PROCESO ETL MUNICIPAL ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Procesa CSV municipales y carga a BigQuery.")
    parser.add_argument("--config", help="Ruta alternativa al archivo de configuración ETL")
    
    args = parser.parse_args()
    
    # Ejecutar el proceso principal
    try:
        main()
    except KeyboardInterrupt:
        print("\nProceso interrumpido por el usuario.")
    except Exception as e:
        logging.getLogger('etl_process').error(f"Error fatal en el proceso ETL: {e}", exc_info=True)
        raise