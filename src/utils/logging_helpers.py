import logging
import os
from datetime import datetime

def setup_detailed_logger():
    os.makedirs("logs", exist_ok=True)

    logger = logging.getLogger('scraping_detallado')
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    if not logger.handlers:
        file_handler = logging.FileHandler('logs/scraping_detallado.log', encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)

        errores_handler = logging.FileHandler('logs/errores_scraper.log', encoding='utf-8')
        errores_handler.setFormatter(formatter)
        errores_handler.setLevel(logging.WARNING)
        logger.addHandler(errores_handler)
    
    return logger

def log_resumen_terminal(municipio_id, year, resultados):
    resumen_lines = [
        f"[RESUMEN] Resultados para {municipio_id} (año {year}):",
        f"   - acceso_municipio_exitoso: {resultados['acceso_municipio_exitoso']}",
        f"   - tipo_municipio_detectado: {resultados['tipo_municipio_detectado']}"
    ]
    
    for tipo_personal, estado in resultados.get('tipos_personal', {}).items():
        resumen_lines.append(
            f"   - Tipo de personal '{tipo_personal}': {estado['personal']} | "
            f"Área MUNICIPAL: {estado['area']} | "
            f"Año: {estado['año']} | "
            f"Meses: {estado['meses']} | "
            f"CSV: {estado['CSV']}"
        )
    
    resumen_text = '\n'.join(resumen_lines)
    print(f"\n{resumen_text}")
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open('logs/resumen_ejecucion.log', 'a', encoding='utf-8') as f:
        f.write(f"{timestamp} | año={year}\n{resumen_text}\n\n")

def log_detallado_municipio(logger, municipio_id, year, duracion, resultados):
    logger.info("\n" + "=" * 60)
    logger.info(f"--- Municipio {municipio_id} ---")
    logger.info(f"Año procesado: {year}")
    logger.info(f"Tiempo de procesamiento: {duracion:.2f} segundos")
    logger.info(f"Acceso exitoso: {resultados.get('acceso_municipio_exitoso')}")
    logger.info(f"Tipo municipio detectado: {resultados.get('tipo_municipio_detectado')}")

    detalle = resultados.get('tipos_personal', {})
    for tipo, estado in detalle.items():
        logger.info(f"Tipo: {tipo}")
        logger.info(f"  - Personal: {estado['personal']} | XPath: {estado.get('xpath_tipo')}")
        logger.info(f"  - Área: {estado['area']} | XPath: {estado.get('xpath_area')}")
        logger.info(f"  - Año: {estado['año']} | XPath: {estado.get('xpath_anio')}")
        logger.info(f"  - Meses: {estado.get('meses', 'N/A')}")
        logger.info("    Detalle por mes:")

        for mes, info_mes in estado.get('meses_detalle', {}).items():
            status = info_mes.get('status', 'N/A')
            xpath_mes = info_mes.get('xpath_mes')
            csv_status = info_mes.get('csv_status', 'N/A')
            csv_path = info_mes.get('csv_path')
            xpath_csv = info_mes.get('xpath_csv', None)

            if status == 'SKIP_EXISTE' or csv_status == 'YA_EXISTIA':
                logger.info(f"      * {mes}: SKIP (CSV ya existía) | CSV path: {csv_path}")
            else:
                logger.info(
                    f"      * {mes}: {status} | XPath: {xpath_mes} "
                    f"| Descargar CSV: {csv_status} "
                    f"| XPath CSV: {xpath_csv} "
                    f"| CSV path: {csv_path}"
                )
                
                if status == 'FALLÓ' or csv_status == 'FALLÓ':
                    logger.warning(
                        f"[FALLO] Municipio {municipio_id} | año {year} | tipo {tipo} | "
                        f"mes {mes} | status_mes={status} | csv_status={csv_status}"
                    )

    logger.info("=" * 60 + "\n")