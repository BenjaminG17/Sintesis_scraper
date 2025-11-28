import logging
from datetime import datetime

def setup_detailed_logger():
    """Configura el logger detallado para archivo"""
    logger = logging.getLogger('scraping_detallado')
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler = logging.FileHandler('logs/scraping_detallado.log', encoding='utf-8')
    file_handler.setFormatter(formatter)
    if not logger.hasHandlers():
        logger.addHandler(file_handler)
    return logger

def log_resumen_terminal(municipio_id, resultados):
    """Muestra el resumen estructurado en terminal y lo guarda en resumen_ejecucion.log"""
    resumen_lines = [
        f"[RESUMEN] Resultados para {municipio_id}:",
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
    with open('logs/resumen_ejecucion.log', 'a', encoding='utf-8') as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{resumen_text}\n\n")

def log_detallado_municipio(logger, municipio_id, duracion, resultados):
    """Guarda información detallada y legible en scraping_detallado.log"""
    logger.info("\n" + "="*60)
    logger.info(f"--- Municipio {municipio_id} ---")
    logger.info(f"Tiempo de procesamiento: {duracion:.2f} segundos")
    logger.info(f"Acceso exitoso: {resultados.get('acceso_municipio_exitoso')}")
    logger.info(f"Tipo municipio detectado: {resultados.get('tipo_municipio_detectado')}")
    detalle = resultados.get('tipos_personal', {})
    for tipo, estado in detalle.items():
        logger.info(f"Tipo: {tipo}")
        logger.info(f"  - Personal: {estado['personal']} | XPath: {estado.get('xpath_tipo')}")
        logger.info(f"  - Área: {estado['area']} | XPath: {estado.get('xpath_area')}")
        logger.info(f"  - Año: {estado['año']} | XPath: {estado.get('xpath_anio')}")
        logger.info(f"  - Meses : {estado.get('meses','N/A')} ")
        logger.info("    Detalle por mes:")

        for mes, info_mes in estado.get('meses_detalle', {}).items():
            status = info_mes.get('status', 'N/A')
            xpath_mes= info_mes.get('xpath_mes')
            csv_status=info_mes.get('csv_status','N/A')
            csv_path = info_mes.get('csv_path')
            logger.info(f"      * {mes}: {status} | XPath: {xpath_mes} "
                        f"| Descargar CSV: {csv_status} "
                        f"| Xpath CSV: {info_mes.get('xpath_csv',None)}")
        #meses_detalle = estado.get('meses_detalle', {})
        #if meses_detalle:
        #    logger.info("    Detalle por mes:")
        #    for mes, info in meses_detalle.items():
        #        ok_flag = "ÉXITO" if info.get("ok") else "FALLÓ"
        #        xpath_mes = info.get("xpath_mes")
        #        logger.info(f"      * {mes}: {ok_flag} | XPath: {xpath_mes}")
    logger.info("="*60 + "\n")
