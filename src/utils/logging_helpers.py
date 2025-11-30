import logging
import os
from datetime import datetime

def setup_detailed_logger():
    """Configura el logger detallado para archivo y un log separado solo de errores/warnings."""
    os.makedirs("logs", exist_ok=True)

    """Configura el logger detallado para archivo"""
    logger = logging.getLogger('scraping_detallado')
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    # Solo configuramos handlers una vez
    if not logger.handlers:
        # Log detallado completo
        file_handler = logging.FileHandler('logs/scraping_detallado.log', encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)

        # NUEVO: log solo de warnings/errores
        errores_handler = logging.FileHandler('logs/errores_scraper.log', encoding='utf-8')
        errores_handler.setFormatter(formatter)
        errores_handler.setLevel(logging.WARNING)  # WARNING, ERROR, CRITICAL
        logger.addHandler(errores_handler)
    return logger

def log_resumen_terminal(municipio_id, year, resultados):
    """Muestra el resumen estructurado en terminal y lo guarda en resumen_ejecucion.log"""
    resumen_lines = [
        f"[RESUMEN] Resultados para {municipio_id} (año {year}):",
        f"   - acceso_municipio_exitoso: {resultados['acceso_municipio_exitoso']}",
        f"   - tipo_municipio_detectado: {resultados['tipo_municipio_detectado']}"
    ]
    #for tipo_personal, estado in resultados['tipos_personal'].items():
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
    # Guardar en archivo resumen_ejecucion.log
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open('logs/resumen_ejecucion.log', 'a', encoding='utf-8') as f:
        f.write(f"{timestamp} | año= {year}\n{resumen_text}\n\n")

def log_detallado_municipio(logger, municipio_id, year, duracion, resultados):
    """
    Guarda información detallada y legible en scraping_detallado.log.
    Además, cuando detecta FALLÓ en algún nivel, emite WARNING que
    también se guardan en logs/errores_scraper.log.
    """
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
        logger.info(f"  - Meses : {estado.get('meses', 'N/A')} ")
        logger.info("    Detalle por mes:")

        # Estados generales
        personal_status = estado.get('personal')
        area_status = estado.get('area')
        anio_status = estado.get('año')
        meses_status = estado.get('meses')
        csv_status_global = estado.get('CSV')

        # Warnings de nivel "tipo de personal"
        if personal_status == 'FALLÓ':
            logger.warning(
                f"[FALLO] Municipio {municipio_id} | año {year} | tipo {tipo} | "
                f"PERSONAL FALLÓ | xpath_tipo={estado.get('xpath_tipo')}"
            )
        if area_status == 'FALLÓ':
            logger.warning(
                f"[FALLO] Municipio {municipio_id} | año {year} | tipo {tipo} | "
                f"ÁREA MUNICIPAL FALLÓ | xpath_area={estado.get('xpath_area')}"
            )
        if anio_status == 'FALLÓ':
            logger.warning(
                f"[FALLO] Municipio {municipio_id} | año {year} | tipo {tipo} | "
                f"AÑO FALLÓ | xpath_anio={estado.get('xpath_anio')}"
            )
        if meses_status == 'FALÓ' or meses_status == 'FALLÓ':
            logger.warning(
                f"[FALLO] Municipio {municipio_id} | año {year} | tipo {tipo} | "
                f"ALGÚN MES FALLÓ (ver detalle por mes)"
            )
        if csv_status_global == 'FALLÓ':
            logger.warning(
                f"[FALLO] Municipio {municipio_id} | año {year} | tipo {tipo} | "
                f"CSV GLOBAL FALLÓ en al menos un mes"
            )

        # Detalle por mes
        for mes, info_mes in estado.get('meses_detalle', {}).items():
            status = info_mes.get('status', 'N/A')
            xpath_mes = info_mes.get('xpath_mes')
            csv_status = info_mes.get('csv_status', 'N/A')
            csv_path = info_mes.get('csv_path')
            xpath_csv = info_mes.get('xpath_csv', None)

            logger.info(
                f"      * {mes}: {status} | XPath: {xpath_mes} "
                f"| Descargar CSV: {csv_status} "
                f"| XPath CSV: {xpath_csv} "
                f"| CSV path: {csv_path}"
            )

            # Si falla el mes o la descarga CSV, registramos WARNING detallado
            if status == 'FALLÓ' or csv_status == 'FALLÓ':
                logger.warning(
                    f"[FALLO] Municipio {municipio_id} | año {year} | tipo {tipo} | "
                    f"mes {mes} | status_mes={status} | csv_status={csv_status} | "
                    f"xpath_mes={xpath_mes} | xpath_csv={xpath_csv} | csv_path={csv_path}"
                )

    logger.info("=" * 60 + "\n")
