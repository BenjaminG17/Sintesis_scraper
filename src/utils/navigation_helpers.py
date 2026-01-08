from typing import Dict, Any, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from datetime import datetime
from pathlib import Path
from src.config import load_env
from .browser_helpers import esperar_y_mover_csv, espera_click, _guardar_screenshot
from .logging_helpers import setup_detailed_logger
import time

def obtener_modulo_generico(actions_cfg: Dict[str, Any]) -> Dict[str, Any]:
    modules = actions_cfg.get("modules", [])
    if not modules:
        raise ValueError("No hay módulos definidos en actions_transparencia.json")
    for m in modules:
        if m.get("id") == "municipio_generico":
            return m
    return modules[0]

def esperar_carga_municipio(driver, org_code: str, timeout: int = 15):
    try:
        WebDriverWait(driver, 5).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        return True
    except Exception:
        try:
            WebDriverWait(driver, timeout - 5).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            return True
        except Exception:
            print(f"[ERROR] ({org_code}) La página no cargó en {timeout}s.")
            _guardar_screenshot(driver, org_code, "no_carga")
            return False

def procesar_municipio(driver, org_code: str, settings: Dict[str, Any], 
                       actions_cfg: Dict[str, Any], year: int, meses=None):
    env = load_env()
    download_root = env["DOWNLOAD_ROOT"]
    logger = setup_detailed_logger()
    modulo = obtener_modulo_generico(actions_cfg)
    url_pattern = modulo.get("url_pattern")
    if not url_pattern:
        raise ValueError("El módulo no tiene 'url_pattern' definido.")
    
    url = url_pattern.format(org=org_code)
    tipos_personal = ["CONTRATA", "PLANTA"]
    resultados: Dict[str, Dict[str, Any]] = {}
    acceso_municipio_exitoso = False

    # SISTEMA DE CACHE GLOBAL MEJORADO
    if not hasattr(procesar_municipio, "estructura_cache"):
        procesar_municipio.estructura_cache = {}
    
    if not hasattr(procesar_municipio, "xpath_cache"):
        procesar_municipio.xpath_cache = {}
    
    estructura_cache = procesar_municipio.estructura_cache
    xpath_cache = procesar_municipio.xpath_cache

    if meses is None:
        meses = settings.get("months", [])

    # Inicializar cache para este municipio si no existe
    if org_code not in estructura_cache:
        estructura_cache[org_code] = {}
        for tipo in tipos_personal:
            estructura_cache[org_code][tipo] = {
                "tiene_area": None,
                "xpaths": {}
            }

    logger.info(f"({org_code}) Procesando municipio para año {year}")
    
    for tipo in tipos_personal:
        print(f"\n[INFO] ({org_code}) - Procesando tipo de personal: {tipo}")
        logger.info(f"({org_code}) Procesando tipo de personal: {tipo}")
        
        if tipo not in resultados:
            resultados[tipo] = {}

        driver.get(url)
        if not esperar_carga_municipio(driver, org_code):
            resultados[tipo][year] = {
                "tipo_personal_ok": False,
                "area_municipal_ok": False,
                "anio_ok": False,
                "xpath_tipo": None,
                "xpath_area": None,
                "xpath_anio": None,
                "meses_ok": False,
                "meses_detalle": {}
            }
            logger.warning(f"({org_code}) No se pudo cargar la página para tipo {tipo}")
            continue

        acceso_municipio_exitoso = True
        estructura = estructura_cache[org_code][tipo]

        # 1. SELECCIONAR TIPO DE PERSONAL (CON CACHE)
        cache_key_tipo = (org_code, tipo, "tipo")
        if cache_key_tipo in xpath_cache:
            xpath_tipo_cache = xpath_cache[cache_key_tipo]
            print(f"[CACHE] ({org_code}) Probando XPath cacheado para tipo '{tipo}': {xpath_tipo_cache}")
            if espera_click(driver, xpath_tipo_cache, timeout=1, scroll=True):
                exito_tipo, xpath_tipo = True, xpath_tipo_cache
                print(f"[OK] ({org_code}) Tipo '{tipo}' seleccionado (cache)")
                logger.info(f"({org_code}) Tipo '{tipo}' seleccionado con XPath cacheado")
            else:
                print(f"[WARN] ({org_code}) XPath cacheado falló, buscando alternativas...")
                exito_tipo, xpath_tipo = abrir_tipo_personal(
                    driver, modulo, org_code, tipo=tipo, xpath_cache=xpath_cache
                )
        else:
            exito_tipo, xpath_tipo = abrir_tipo_personal(
                driver, modulo, org_code, tipo=tipo, xpath_cache=xpath_cache
            )

        if not exito_tipo:
            print(f"[WARN] ({org_code}) No se pudo abrir tipo '{tipo}'.")
            logger.warning(f"({org_code}) No se pudo abrir tipo de personal '{tipo}'")
            resultados[tipo][year] = {
                "tipo_personal_ok": False,
                "area_municipal_ok": False,
                "anio_ok": False,
                "xpath_tipo": None,
                "xpath_area": None,
                "xpath_anio": None,
                "meses_ok": False,
                "meses_detalle": {}
            }
            continue

        # 2. DETECTAR ESTRUCTURA (SI ES NECESARIO)
        exito_area, xpath_area = False, None
        
        if estructura["tiene_area"] is None:
            print(f"[DETECCIÓN] ({org_code}) Tipo '{tipo}': detectando estructura...")
            logger.info(f"({org_code}) Tipo '{tipo}': detectando estructura...")
            
            # Intentar seleccionar área
            exito_area_prueba, xpath_area_prueba = seleccionar_area(
                driver, modulo, org_code, area_value="MUNICIPAL", 
                xpath_cache=xpath_cache, timeout=2, tipo=tipo, modo_deteccion=True
            )
            
            if exito_area_prueba:
                estructura["tiene_area"] = True
                exito_area, xpath_area = True, xpath_area_prueba
                estructura["xpaths"]["area"] = xpath_area_prueba
                print(f"[DETECCIÓN] ({org_code}) Tipo '{tipo}': CON área municipal")
                logger.info(f"({org_code}) Tipo '{tipo}': CON área municipal")
            else:
                print(f"[DETECCIÓN] ({org_code}) Tipo '{tipo}': verificando si tiene años...")
                logger.info(f"({org_code}) Tipo '{tipo}': verificando si tiene años...")
                
                exito_anio_prueba, xpath_anio_prueba = seleccionar_anio(
                    driver, modulo, org_code, year=year,
                    xpath_cache=xpath_cache, timeout=2, tipo=tipo, modo_deteccion=True
                )
                
                if exito_anio_prueba:
                    estructura["tiene_area"] = False
                    print(f"[DETECCIÓN] ({org_code}) Tipo '{tipo}': SIN área, pero CON años")
                    logger.info(f"({org_code}) Tipo '{tipo}': SIN área, pero CON años")
                else:
                    estructura["tiene_area"] = False
                    print(f"[WARN] ({org_code}) Tipo '{tipo}': estructura inusual")
                    logger.warning(f"({org_code}) Tipo '{tipo}': estructura inusual")
        
        elif estructura["tiene_area"]:
            print(f"[CACHE] ({org_code}) Tipo '{tipo}': tiene área municipal")
            exito_area, xpath_area = seleccionar_area(
                driver, modulo, org_code, area_value="MUNICIPAL",
                xpath_cache=xpath_cache, timeout=2, tipo=tipo
            )
            
            if not exito_area and "area" in estructura["xpaths"]:
                xpath_area_cache = estructura["xpaths"]["area"]
                print(f"[CACHE] ({org_code}) Probando XPath cacheado para área: {xpath_area_cache}")
                if espera_click(driver, xpath_area_cache, timeout=1):
                    exito_area, xpath_area = True, xpath_area_cache
        
        else:
            print(f"[CACHE] ({org_code}) Tipo '{tipo}': sin área municipal (skip)")
            logger.info(f"({org_code}) Tipo '{tipo}': sin área municipal (skip)")
            exito_area, xpath_area = False, None

        # 3. SELECCIONAR AÑO
        exito_anio, xpath_anio = seleccionar_anio(
            driver, modulo, org_code, year=year,
            xpath_cache=xpath_cache, timeout=2, tipo=tipo
        )
        
        if exito_anio and xpath_anio:
            estructura["xpaths"]["año"] = xpath_anio

        # 4. PROCESAR MESES
        meses_detalle = {}
        mes_ok = False

        if exito_anio and meses:
            for mes in meses:
                nombre_csv = f"{org_code}_{tipo}_{year}_{mes}.csv"
                ruta_csv_esperada = Path(download_root) / org_code / tipo / str(year) / nombre_csv

                if ruta_csv_esperada.exists() and ruta_csv_esperada.stat().st_size > 1024:
                    print(f"[SKIP] ({org_code}) CSV ya existe para tipo {tipo}, año {year}, mes '{mes}'.")
                    logger.info(f"({org_code}) CSV ya existe para tipo {tipo}, año {year}, mes '{mes}'. Se omite descarga.")
                    meses_detalle[mes] = {
                        "status": "SKIP_EXISTE",
                        "xpath_mes": None,
                        "csv_status": "YA_EXISTIA",
                        "csv_path": str(ruta_csv_esperada),
                    }
                    mes_ok = True
                    continue

                print(f"[INFO] ({org_code}) Recargando para {tipo}, mes '{mes}'")
                logger.info(f"({org_code}) Recargando municipio y seleccionando tipo, área y año del mes '{mes}'")
                
                driver.get(url)
                
                if not esperar_carga_municipio(driver, org_code):
                    print(f"[WARN] ({org_code}) No se pudo recargar para mes '{mes}'")
                    logger.warning(f"({org_code}) No se pudo recargar el municipio antes de mes '{mes}'")
                    meses_detalle[mes] = {"status": "FALLÓ", "xpath_mes": None}
                    continue

                # TIPO
                if cache_key_tipo in xpath_cache:
                    espera_click(driver, xpath_cache[cache_key_tipo], timeout=0.5)
                else:
                    abrir_tipo_personal(driver, modulo, org_code, tipo=tipo, xpath_cache=xpath_cache)

                # ÁREA
                if estructura["tiene_area"]:
                    xpath_area_cache = estructura["xpaths"].get("area")
                    if xpath_area_cache:
                        espera_click(driver, xpath_area_cache, timeout=0.5)
                    else:
                        seleccionar_area(driver, modulo, org_code, area_value="MUNICIPAL",
                                       xpath_cache=xpath_cache, timeout=1, tipo=tipo)

                # AÑO
                xpath_anio_cache = estructura["xpaths"].get("año")
                if xpath_anio_cache:
                    espera_click(driver, xpath_anio_cache, timeout=0.5)
                else:
                    seleccionar_anio(driver, modulo, org_code, year=year,
                                   xpath_cache=xpath_cache, timeout=1, tipo=tipo)

                # MES
                exito_mes, xpath_mes = seleccionar_mes(
                    driver, modulo, org_code, month=mes,
                    xpath_cache=xpath_cache, timeout=2, tipo=tipo
                )
                if not exito_mes:
                    print(f"[WARN] ({org_code}) No se pudo seleccionar mes '{mes}'")
                    logger.warning(f"({org_code}) No se pudo seleccionar el mes '{mes}' para tipo {tipo}.")
                    meses_detalle[mes] = {"status": "FALLÓ", "xpath_mes": None}
                    continue

                print(f"[OK] ({org_code}) Mes '{mes}' seleccionado para {tipo}")
                logger.info(f"({org_code}) Mes '{mes}' seleccionado correctamente para tipo {tipo}.")
                meses_detalle[mes] = {"status": "ÉXITO", "xpath_mes": xpath_mes}
                mes_ok = True

                # DESCARGAR CSV
                exito_csv, xpath_csv = descargar_csv(
                    driver, modulo, org_code, xpath_cache=xpath_cache,
                    timeout=15, tipo=tipo
                )
                
                if exito_csv:
                    print(f"[OK] ({org_code}) Descarga CSV disparada para {tipo}, {year}, '{mes}'")
                    logger.info(f"({org_code}) Descarga CSV disparada para tipo {tipo}, año {year}, mes '{mes}'.")
                    
                    ruta_csv = esperar_y_mover_csv(
                        download_root=download_root,
                        municipio=org_code,
                        tipo_personal=tipo,
                        year=year,
                        mes=mes,
                        timeout=15
                    )
                    
                    if ruta_csv:
                        meses_detalle[mes]["csv_status"] = "ÉXITO"
                        meses_detalle[mes]["xpath_csv"] = xpath_csv
                        meses_detalle[mes]["csv_path"] = ruta_csv
                        print(f"[OK] ({org_code}) CSV movido a: {ruta_csv}")
                        logger.info(f"({org_code}) CSV movido a: {ruta_csv}")
                    else:
                        meses_detalle[mes]["csv_status"] = "FALLÓ"
                        meses_detalle[mes]["xpath_csv"] = xpath_csv
                        meses_detalle[mes]["csv_path"] = None
                        print(f"[WARN] ({org_code}) No se pudo mover CSV")
                        logger.warning(f"({org_code}) No se pudo mover/renombrar el CSV para tipo {tipo}, año {year}, mes '{mes}'.")
                else:
                    print(f"[WARN] ({org_code}) No se pudo disparar CSV para {tipo}, {year}, '{mes}'")
                    logger.warning(f"({org_code}) No se pudo disparar descarga CSV para tipo {tipo}, año {year}, mes '{mes}'.")
                    meses_detalle[mes]["csv_status"] = "FALLÓ"
                    meses_detalle[mes]["xpath_csv"] = None
                    meses_detalle[mes]["csv_path"] = None

                time.sleep(1)

        resultados[tipo][year] = {
            "tipo_personal_ok": True,
            "area_municipal_ok": bool(exito_area) if estructura["tiene_area"] is not None else False,
            "anio_ok": bool(exito_anio),
            "xpath_tipo": xpath_tipo,
            "xpath_area": xpath_area,
            "xpath_anio": xpath_anio,
            "meses_ok": mes_ok,
            "meses_detalle": meses_detalle,
        }

    # RESUMEN
    tiene_area_algun_tipo = any(
        estructura_cache[org_code][tipo]["tiene_area"]
        for tipo in tipos_personal
        if estructura_cache[org_code][tipo]["tiene_area"] is not None
    )
    
    tipo_municipio_detectado = "con_area_municipal" if tiene_area_algun_tipo else "sin_area_municipal"

    print(f"\n[RESUMEN] {org_code} (año {year}):")
    print(f"   - Acceso: {acceso_municipio_exitoso}")
    print(f"   - Tipo: {tipo_municipio_detectado}")
    
    for tipo in tipos_personal:
        datos = resultados.get(tipo, {}).get(year, {})
        if not datos:
            continue
            
        print(f"   - {tipo}: Personal: {'ÉXITO' if datos['tipo_personal_ok'] else 'FALLÓ'} | "
              f"Área: {'ÉXITO' if datos['area_municipal_ok'] else 'FALLÓ'} | "
              f"Año: {'ÉXITO' if datos['anio_ok'] else 'FALLÓ'} | "
              f"Meses: {'ÉXITO' if datos['meses_ok'] else 'FALLÓ'}")

    logger.info(f"({org_code}) Procesamiento completado para año {year}")
    
    return {
        "acceso_municipio_exitoso": acceso_municipio_exitoso,
        "tipo_municipio_detectado": tipo_municipio_detectado,
        "detalle_por_tipo": resultados,
    }

def abrir_tipo_personal(driver, modulo: Dict[str, Any], org_code: str, 
                       tipo: str, timeout: int = 3, xpath_cache=None, 
                       modo_deteccion: bool = False):
    if modo_deteccion:
        timeout = 2
    
    scraping_actions = modulo.get("scraping_actions", [])
    config_tipo = None
    for sa in scraping_actions:
        if sa.get("type") == "open_tipo_personal":
            config_tipo = sa
            break
    
    if not config_tipo:
        print(f"[WARN] ({org_code}) No se encontró configuración 'open_tipo_personal'")
        return False, None
    
    option = None
    for opt in config_tipo.get("options", []):
        if opt.get("value") == tipo:
            option = opt
            break
    
    if not option:
        print(f"[WARN] ({org_code}) No hay opción para tipo_personal='{tipo}'")
        return False, None
    
    xpaths = option.get("xpaths") or []
    if not xpaths:
        print(f"[WARN] ({org_code}) La opción '{tipo}' no tiene xpaths")
        return False, None
    
    print(f"[ACTION] {org_code} - Abriendo tipo '{tipo}'")
    print(f"[XPATH] Probando {len(xpaths)} XPaths para tipo '{tipo}'")
    
    cache_key = (org_code, tipo, "tipo")
    
    for i, xp in enumerate(xpaths, 1):
        print(f"[XPATH] Intento #{i} para tipo '{tipo}': {xp}")
        exito = espera_click(driver, xp, timeout=timeout, scroll=True)
        
        if exito:
            print(f"[OK] XPath #{i} funcionó para tipo '{tipo}'")
            if xpath_cache is not None and not modo_deteccion:
                xpath_cache[cache_key] = xp
            return True, xp
        else:
            print(f"[FAIL] XPath #{i} falló para tipo '{tipo}'")
    
    print(f"[ERROR] {org_code} No se pudo abrir tipo '{tipo}' después de {len(xpaths)} intentos")
    return False, None

def seleccionar_area(driver, modulo: Dict[str, Any], org_code: str, 
                    area_value: str = "MUNICIPAL", timeout: int = 2, 
                    xpath_cache=None, tipo: str = None, modo_deteccion: bool = False):
    """Selecciona el área municipal, probando TODOS los XPaths en modo detección."""
    
    if modo_deteccion:
        timeout = 2  # Timeout más corto para detección, pero probamos TODOS los XPaths
    
    scraping_actions = modulo.get("scraping_actions", [])
    config_area = None
    for sa in scraping_actions:
        if sa.get("type") == "select_area":
            config_area = sa
            break
    
    if not config_area:
        print(f"[WARN] ({org_code}) No se encontró configuración 'select_area'")
        return False, None
    
    option = None
    for opt in config_area.get("options", []):
        if opt.get("value") == area_value:
            option = opt
            break
    
    if not option:
        print(f"[WARN] ({org_code}) No hay opción para area='{area_value}'")
        return False, None
    
    xpaths = option.get("xpaths") or []
    if not xpaths:
        print(f"[WARN] ({org_code}) La opción '{area_value}' no tiene XPaths")
        return False, None
    
    print(f"[ACTION] {org_code} - Seleccionando área '{area_value}'")
    print(f"[XPATH] Probando TODOS los {len(xpaths)} XPaths para área '{area_value}'")
    
    if tipo:
        cache_key = (org_code, tipo, area_value, "area")
    else:
        cache_key = (org_code, area_value, "area")
    
    # En modo detección NO usamos cache
    if xpath_cache and cache_key in xpath_cache and not modo_deteccion:
        xp_cache = xpath_cache[cache_key]
        print(f"[CACHE] ({org_code}) Probando XPath cacheado: {xp_cache}")
        if espera_click(driver, xp_cache, timeout=timeout, scroll=True):
            print(f"[OK] XPath cacheado funcionó para área '{area_value}'")
            time.sleep(0.1)
            return True, xp_cache
    
    # PROBAR TODOS LOS XPATHS (sin límite)
    for i, xp in enumerate(xpaths, 1):
        print(f"[XPATH] Intento #{i}/{len(xpaths)} para área '{area_value}': {xp}")
        exito = espera_click(driver, xp, timeout=timeout, scroll=True)
        
        if exito:
            print(f"[OK] XPath #{i} funcionó para área '{area_value}'")
            time.sleep(0.1)
            # Solo guardar en cache si NO estamos en modo detección
            if xpath_cache is not None and not modo_deteccion:
                xpath_cache[cache_key] = xp
            return True, xp
        else:
            print(f"[FAIL] XPath #{i} falló para área '{area_value}'")
    
    print(f"[INFO] {org_code} No se encontró área '{area_value}' después de probar TODOS los {len(xpaths)} XPaths")
    return False, None

def seleccionar_anio(driver, modulo: Dict[str, Any], org_code: str, 
                    year: int, tipo: str = None, timeout: int = 2, 
                    xpath_cache=None, modo_deteccion: bool = False):
    if modo_deteccion:
        timeout = 2
    
    scraping_actions = modulo.get("scraping_actions", [])
    config_anio = None
    for sa in scraping_actions:
        if sa.get("type") == "select_anio":
            config_anio = sa
            break
    
    if not config_anio:
        print(f"[WARN] ({org_code}) No se encontró configuración 'select_anio'")
        return False, None
    
    patterns = config_anio.get("year_patterns", [])
    if not patterns:
        print(f"[WARN] ({org_code}) 'select_anio' no tiene 'year_patterns'")
        return False, None
    
    year_str = str(year)
    xpaths = [pat.replace("{YEAR}", year_str) for pat in patterns]
    
    print(f"[ACTION] {org_code} - Seleccionando año '{year_str}'")
    print(f"[XPATH] Probando {len(xpaths)} XPaths para año '{year_str}'")
    
    if tipo:
        cache_key = (org_code, tipo, year, "anio")
    else:
        cache_key = (org_code, year, "anio")
    
    for i, xp in enumerate(xpaths, 1):
        print(f"[XPATH] Intento #{i} para año '{year_str}': {xp}")
        exito = espera_click(driver, xp, timeout=timeout, scroll=True)
        
        if exito:
            print(f"[OK] XPath #{i} funcionó para año '{year_str}'")
            if xpath_cache is not None and not modo_deteccion:
                xpath_cache[cache_key] = xp
            return True, xp
        else:
            print(f"[FAIL] XPath #{i} falló para año '{year_str}'")
    
    print(f"[ERROR] ({org_code}) No se pudo seleccionar año '{year_str}' después de {len(xpaths)} intentos")
    return False, None

def seleccionar_mes(driver, modulo: Dict[str, Any], org_code: str, 
                   month: str, timeout: int = 2, xpath_cache=None, 
                   tipo: str = None):
    scraping_actions = modulo.get("scraping_actions", [])
    config_mes = None
    for sa in scraping_actions:
        if sa.get("type") == "select_mes":
            config_mes = sa
            break
    
    if not config_mes:
        print(f"[WARN] ({org_code}) No se encontró configuración 'select_mes'")
        return False, None
    
    patterns = config_mes.get("month_patterns", [])
    if not patterns:
        print(f"[WARN] ({org_code}) 'select_mes' no tiene 'month_patterns'")
        return False, None
    
    month_str = str(month)
    month_lower = month_str.lower()
    month_partial = month_lower[:4]
    
    xpaths = []
    for pat in patterns:
        xp = (pat.replace("{MONTH}", month_str)
                .replace("{MONTH_LOWER}", month_lower)
                .replace("{MONTH_PARTIAL}", month_partial))
        xpaths.append(xp)
    
    print(f"[ACTION] {org_code} - Seleccionando mes '{month_str}'")
    print(f"[XPATH] Probando {len(xpaths)} XPaths para mes '{month_str}'")
    
    if tipo:
        cache_key = (org_code, tipo, month, "mes")
    else:
        cache_key = (org_code, month, "mes")
    
    for i, xp in enumerate(xpaths, 1):
        print(f"[XPATH] Intento #{i} para mes '{month_str}': {xp}")
        exito = espera_click(driver, xp, timeout=timeout, scroll=True)
        
        if exito:
            print(f"[OK] XPath #{i} funcionó para mes '{month_str}'")
            if xpath_cache is not None:
                xpath_cache[cache_key] = xp
            return True, xp
        else:
            print(f"[FAIL] XPath #{i} falló para mes '{month_str}'")
    
    print(f"[ERROR] ({org_code}) No se pudo seleccionar mes '{month_str}' después de {len(xpaths)} intentos")
    return False, None

def descargar_csv(driver, modulo: Dict[str, Any], org_code: str, 
                 timeout: int = 15, xpath_cache=None, tipo: str = None):
    scraping_actions = modulo.get("scraping_actions", [])
    config_csv = None
    for sa in scraping_actions:
        if sa.get("type") == "download_csv":
            config_csv = sa
            break
    
    if not config_csv:
        print(f"[WARN] ({org_code}) No se encontró configuración 'download_csv'")
        return False, None
    
    xpaths = config_csv.get("xpaths", [])
    selector_button = config_csv.get("selector_button")
    if selector_button:
        xpaths.append(selector_button)
    
    if not xpaths:
        print(f"[WARN] ({org_code}) 'download_csv' no tiene XPaths")
        return False, None
    
    print(f"[ACTION] ({org_code}) Descargando CSV")
    print(f"[XPATH] Probando {len(xpaths)} XPaths para descargar CSV")
    
    if tipo:
        cache_key = (org_code, tipo, "csv")
    else:
        cache_key = (org_code, "csv")
    
    for i, xp in enumerate(xpaths, 1):
        print(f"[XPATH] Intento #{i} para CSV: {xp}")
        exito = espera_click(driver, xp, timeout=timeout, scroll=True)
        
        if exito:
            print(f"[OK] XPath #{i} funcionó para CSV")
            if xpath_cache is not None:
                xpath_cache[cache_key] = xp
            return True, xp
        else:
            print(f"[FAIL] XPath #{i} falló para CSV")
    
    print(f"[ERROR] ({org_code}) No se pudo descargar CSV después de {len(xpaths)} intentos")
    return False, None

def get_meses_para_year(year, settings):
    meses = settings.get("months", [])
    now = datetime.now()
    
    if year != now.year:
        return meses
    
    limite = now.month - 1
    if limite <= 0:
        return []
    
    return meses[:limite]

def safe_file_check(file_path):
    try:
        path = Path(file_path)
        if not path.exists():
            return False
            
        if path.stat().st_size == 0:
            return False
            
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                f.read(1024)
            return True
        except (OSError, IOError, UnicodeDecodeError):
            try:
                path.unlink()
                print(f"[INFO] Archivo corrupto eliminado: {file_path}")
            except:
                pass
            return False
            
    except Exception as e:
        print(f"[WARN] Error verificando archivo {file_path}: {e}")
        return False