from typing import Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from src.config import load_env
from .browser_helpers import esperar_y_mover_csv,espera_click,_guardar_screenshot
from .logging_helpers import setup_detailed_logger
import time

def _obtener_modulo_generico(actions_cfg: Dict[str, Any]) -> Dict[str, Any]:
	modules = actions_cfg.get("modules", [])
	if not modules:
		raise ValueError("No hay módulos definidos en actions_transparencia.json")
	for m in modules:
		if m.get("id") == "municipio_generico":
			return m
	return modules[0]

def esperar_carga_municipio(driver, org_code: str, timeout: int = 20):
	try:
		WebDriverWait(driver, timeout).until(
			lambda d: d.execute_script("return document.readyState") == "complete"
		)
		return True
	except Exception:
		print(f"[ERROR] ({org_code}) La página del municipio no terminó de cargar en {timeout}s.")
		_guardar_screenshot(driver, org_code, "no_carga")
		return False

def procesar_municipio(driver, org_code: str, settings: Dict[str, Any], actions_cfg: Dict[str, Any]):
	env=load_env()
	download_root=env["DOWNLOAD_ROOT"]
	logger = setup_detailed_logger()
	modulo = _obtener_modulo_generico(actions_cfg)
	url_pattern = modulo.get("url_pattern")
	if not url_pattern:
		raise ValueError("El módulo no tiene 'url_pattern' definido.")
	url = url_pattern.format(org=org_code)
	tipos_personal = ["CONTRATA", "PLANTA"]
	start_year = settings.get("start_year")
	end_year = settings.get("end_year", start_year)
	resultados: Dict[str, Dict[str, Any]] = {}
	acceso_municipio_exitoso = False


	# Memoria de estado de área por municipio
	if not hasattr(procesar_municipio, "estado_areas"):
		procesar_municipio.estado_areas = {}
	estado_areas = procesar_municipio.estado_areas

	# Sistema de caché inteligente de XPaths (solo para acelerar búsqueda dentro de cada función)
	if not hasattr(procesar_municipio, "xpath_cache"):
		procesar_municipio.xpath_cache = {}
	xpath_cache = procesar_municipio.xpath_cache

	resultados = {}
	for year in range(start_year, end_year + 1):
		for tipo in tipos_personal:
			print(f"\n[INFO] ({org_code}) - Procesando tipo de personal: {tipo} para año: {year}")
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
					"meses_ok":False,
					"meses_detalle":{},
				}
				print(f"[INFO] ({org_code}) Fin de la fase tipo_personal '{tipo}' - FALLÓ (no cargó la página)")
				continue
			acceso_municipio_exitoso = True

			# Abrir tipo de personal SIEMPRE tras recargar
			exito_tipo, xpath_tipo = abrir_tipo_personal(driver, modulo, org_code, tipo=tipo, xpath_cache=xpath_cache)
			if not exito_tipo:
				print(f"[INFO] ({org_code}) Fin de fase tipo_personal '{tipo}' - FALLÓ (no se abrió)")
				resultados[tipo][year] = {
					"tipo_personal_ok": False,
					"area_municipal_ok": False,
					"anio_ok": False,
					"xpath_tipo": None,
					"xpath_area": None,
					"xpath_anio": None,
					"meses_ok":False,
					"meses_detalle":{},
				}
				continue

			municipio_tiene_area = estado_areas.get(org_code, None)
			exito_area, xpath_area = None, None
			if municipio_tiene_area is None:
				print(f"[PASO 2] ({org_code}) Intentando seleccionar área MUNICIPAL para tipo: {tipo}")
				exito_area, xpath_area = seleccionar_area(driver, modulo, org_code, area_value="MUNICIPAL", xpath_cache=xpath_cache)
				if not exito_area:
					print(f"[WARN] ({org_code}) No se pudo seleccionar área MUNICIPAL. Se memoriza como SIN_AREA y se avanza a años.")
					estado_areas[org_code] = False
				else:
					estado_areas[org_code] = True
			elif municipio_tiene_area is False:
				print(f"[INFO] ({org_code}) Municipio ya detectado SIN área MUNICIPAL. Saltando a selección de año.")
			else:
				print(f"[PASO 2] ({org_code}) Seleccionando área MUNICIPAL para tipo: {tipo} (ya detectado CON área)")
				exito_area, xpath_area = seleccionar_area(driver, modulo, org_code, area_value="MUNICIPAL", xpath_cache=xpath_cache)

			print(f"[PASO 3] ({org_code}) Seleccionando año {year} para tipo: {tipo}")
			exito_anio, xpath_anio = seleccionar_anio(driver, modulo, org_code, year=year, xpath_cache=xpath_cache)

			meses = settings.get("months", [])
			meses_detalle={}
			mes_ok=False

			if exito_anio and meses:
				meses_detalle={}
				mes_ok=False

				for mes in meses:
					print(f"[INFO] ({org_code}) Recargando municipio y seleccionando tipo, área y año del mes '{mes}'")
					logger.info(f"({org_code}) Recargando municipio y seleccionando tipo, área y año del mes '{mes}'")
					driver.get(url)

					if not esperar_carga_municipio(driver, org_code):
						print(f"[WARN] ({org_code}) No se pudo recargar el municipio antes de mes '{mes}'")
						logger.warning(f"({org_code}) No se pudo recargar el municipio antes de mes '{mes}'")
						meses_detalle[mes] ={"status":"FALLÓ", "xpath_mes":None}
						continue

					exito_tipo, xpath_tipo = abrir_tipo_personal(driver, modulo, org_code, tipo=tipo, xpath_cache=xpath_cache)
					if not exito_tipo:
						print(f"[WARN] ({org_code}) No se pudo reabrir tipo de personal '{tipo}' antes de mes '{mes}'")
						logger.warning(f"({org_code}) No se pudo reabrir tipo de personal '{tipo}' antes de mes '{mes}'")
						meses_detalle[mes] ={"status":"FALLÓ", "xpath_mes":None}
						continue

					municipio_tiene_area = estado_areas.get(org_code, None)
					exito_area, xpath_area = None, None
					if municipio_tiene_area is None:
						exito_area, xpath_area = seleccionar_area(driver, modulo, org_code, area_value="MUNICIPAL", xpath_cache=xpath_cache)
						if not exito_area:
							estado_areas[org_code] = False
					elif municipio_tiene_area is True:
						exito_area, xpath_area = seleccionar_area(driver, modulo, org_code, area_value="MUNICIPAL", xpath_cache=xpath_cache)

					exito_anio, xpath_anio = seleccionar_anio(driver, modulo, org_code, year=year, xpath_cache=xpath_cache)
					if not exito_anio:
						print(f"[WARN] ({org_code}) No se pudo seleccionar año '{year}' antes de mes '{mes}'")
						logger.warning(f"({org_code}) No se pudo seleccionar año '{year}' antes de mes '{mes}'")
						meses_detalle[mes] ={"status":"FALLÓ", "xpath_mes":None}
						continue

					print(f"[PASO 4] ({org_code}) Seleccionando mes '{mes}' para tipo {tipo}, año {year}")
					exito_mes, xpath_mes = seleccionar_mes(driver, modulo, org_code, month=mes, xpath_cache=xpath_cache)
					if not exito_mes:
						print(f"[WARN] ({org_code}) No se pudo seleccionar el mes '{mes}' para tipo {tipo}. Se continúa con el siguiente mes.")
						logger.warning(f"({org_code}) No se pudo seleccionar el mes '{mes}' para tipo {tipo}.")
						meses_detalle[mes] ={"status":"FALLÓ", "xpath_mes":None}
						continue

					print(f"[OK] ({org_code}) Mes '{mes}' seleccionado correctamente para tipo {tipo}.")
					logger.info(f"({org_code}) Mes '{mes}' seleccionado correctamente para tipo {tipo}.")
					meses_detalle[mes] ={"status":"ÉXITO", "xpath_mes":xpath_mes}
					mes_ok=True

					exito_csv, xpath_csv = descargar_csv(driver, modulo, org_code, xpath_cache=xpath_cache)
					if exito_csv:
						print(f"[OK] ({org_code}) Descarga CSV disparada para tipo {tipo}, año {year}, mes '{mes}'.")
						logger.info(f"({org_code}) Descarga CSV disparada para tipo {tipo}, año {year}, mes '{mes}'.")

						ruta_csv = esperar_y_mover_csv(
							download_root=download_root,
							municipio=org_code,
							tipo_personal=tipo,
							year=year,
							mes=mes,
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
							print(f"[WARN] ({org_code}) No se pudo mover/renombrar el CSV para tipo {tipo}, año {year}, mes '{mes}'.")
							logger.warning(f"({org_code}) No se pudo mover/renombrar el CSV para tipo {tipo}, año {year}, mes '{mes}'.")
					else:
						print(f"[WARN] ({org_code}) No se pudo disparar descarga CSV para tipo {tipo}, año {year}, mes '{mes}'.")
						logger.warning(f"({org_code}) No se pudo disparar descarga CSV para tipo {tipo}, año {year}, mes '{mes}'.")
						meses_detalle[mes]["csv_status"] = "FALLÓ"
						meses_detalle[mes]["xpath_csv"] = None
						meses_detalle[mes]["csv_path"] =None
					time.sleep(3)
			else:
				for mes in meses:
					meses_detalle[mes] ={"status":"FALLÓ", "xpath_mes":None}

			resultados[tipo][year] = {
				"tipo_personal_ok": True,
				"area_municipal_ok": bool(exito_area),
				"anio_ok": bool(exito_anio),
				"xpath_tipo": xpath_tipo,
				"xpath_area": xpath_area,
				"xpath_anio": xpath_anio,
				"meses_ok":mes_ok,
				"meses_detalle": meses_detalle
			}
	if any(r.get("area_municipal_ok") for r in resultados.values()):
		tipo_municipio_detectado = "con_area_municipal"
	else:
		tipo_municipio_detectado = "sin_area_municipal"
	print(f"\n[RESUMEN] Resultados para {org_code}:")
	print(f"   - acceso_municipio_exitoso : {acceso_municipio_exitoso}")
	print(f"   - tipo_municipio_detectado : {tipo_municipio_detectado}")
	for tipo in tipos_personal:
		datos = resultados.get(tipo)
		if not datos:
			print(f"   - Tipo de personal '{tipo}': sin_datos")
			continue
		status_tipo = "ÉXITO" if datos["tipo_personal_ok"] else "FALLÓ"
		status_area = "ÉXITO" if datos["area_municipal_ok"] else "FALLÓ"
		status_anio = "EXITO" if datos["anio_ok"] else "FALLÓ"
		status_mes = "ÉXITO" if datos.get("meses_ok") else "FALLÓ"
		extra = " (skip_por_contrata)" if datos.get("skip_por_contrata") else ""
		print(
			f"   - Tipo de personal '{tipo}': {status_tipo}{extra} | "
			f"Área MUNICIPAL: {status_area} | "
			f"Año: {status_anio} | "
			f"Meses: {status_mes}"
		)
	return {
		"acceso_municipio_exitoso": acceso_municipio_exitoso,
		"tipo_municipio_detectado": tipo_municipio_detectado,
		"detalle_por_tipo": resultados,
	}

def abrir_tipo_personal(driver, modulo: Dict[str, Any], org_code: str, tipo: str, timeout: int = 10, xpath_cache=None):
	scraping_actions = modulo.get("scraping_actions", [])
	config_tipo = None
	for sa in scraping_actions:
		if sa.get("type") == "open_tipo_personal":
			config_tipo = sa
			break
	if not config_tipo:
		print(f"[WARN] No se encontró configuración 'open_tipo_personal' en scraping_actions.")
		return False
	option = None
	for opt in config_tipo.get("options", []):
		if opt.get("value") == tipo:
			option = opt
			break
	if not option:
		print(f"[WARN] No hay opción configurada para tipo_personal='{tipo}' en 'open_tipo_personal'.")
		return False
	xpaths = option.get("xpaths") or []
	if not xpaths:
		print(f"[WARN] ({org_code}) La opción '{tipo}' no tiene xpaths definidos.")
		return False
	print(f"[ACTION] {org_code} - Abriendo tipo de personal '{tipo}'")
	
	# Usar caché para acelerar búsqueda
	cache_key = (org_code, tipo, "tipo")
	intentos_fallidos = []
	if xpath_cache:
		xp_cache = xpath_cache.get(cache_key)
		if xp_cache:
			exito = espera_click(driver, xp_cache, timeout=timeout, scroll=True)
			if exito:
				print(f"[OK] {org_code} - tipo '{tipo}' abierto (cache)")
				return True, xp_cache
	for i, xp in enumerate(xpaths, 1):
		print(f"[DEBUG] ({org_code}) Intento #{i}: XPath {xp}")
		exito = espera_click(driver, xp, timeout=timeout, scroll=True)
		if exito:
			if xpath_cache is not None:
				xpath_cache[cache_key] = xp
			if intentos_fallidos:
				print(f"[OK] {org_code} - tipo '{tipo}' abierto en intento #{i}")
				print(f"XPath exitoso:{xp}")
				print(f"Intentos fallidos {len(intentos_fallidos)}")
			else:
				print(f"[OK] {org_code} - tipo '{tipo}' abierto")
			return True, xp
		else:
			intentos_fallidos.append(f"XPath {i}: {xp}")
			print(f"[INTENTO] {org_code} - XPath #{i} falló para tipo '{tipo}'")
	print(f"[ERROR] {org_code} No se pudo abrir el tipo de personal '{tipo}'")
	print(f"        Total de XPaths intentados: {len(xpaths)}")
	print("         XPaths probados:")
	for xp_info in intentos_fallidos:
		print(f"           - {xp_info}")
	return False, None

def seleccionar_area(driver, modulo: Dict[str, Any], org_code: str, area_value: str = "MUNICIPAL", timeout: int = 3, xpath_cache=None) -> bool:
	scraping_actions = modulo.get("scraping_actions", [])
	config_area = None
	for sa in scraping_actions:
		if sa.get("type") == "select_area":
			config_area = sa
			break
	if not config_area:
		print(f"[WARN] ({org_code}) No se encontró configuración 'select_area' en scraping_actions.")
		return False
	option = None
	for opt in config_area.get("options", []):
		if opt.get("value") == area_value:
			option = opt
			break
	if not option:
		print(f"[WARN] ({org_code}) No hay opción configurada para area='{area_value}' en 'select_area'.")
		return False
	xpaths = option.get("xpaths") or []
	if not xpaths:
		print(f"[WARN] ({org_code}) La opción de área '{area_value}' no tiene XPaths definidos.")
		return False
	print(f"[ACTION] {org_code} - Seleccionando área '{area_value}'")
	
	# Usar caché para acelerar búsqueda
	cache_key = (org_code, area_value, "area")
	intentos_fallidos = []
	if xpath_cache:
		xp_cache = xpath_cache.get(cache_key)
		if xp_cache:
			exito = espera_click(driver, xp_cache, timeout=timeout, scroll=True)
			if exito:
				print(f"[OK] ({org_code}) Área '{area_value}' seleccionada (cache)")
				return True, xp_cache
	for i, xp in enumerate(xpaths, 1):
		print(f"[DEBUG] ({org_code}) Intento #{i}: probando XPath {xp}")
		exito = espera_click(driver, xp, timeout=timeout, scroll=True)
		if exito:
			if xpath_cache is not None:
				xpath_cache[cache_key] = xp
			if intentos_fallidos:
				print(f"[OK] ({org_code}) Área '{area_value}' seleccionada en el intento #{i}")
				print(f"     XPath exitoso: {xp}")
				print(f"     Intentos fallidos previos: {len(intentos_fallidos)}")
			else:
				print("-----------------------------------------")
			return True, xp
		else:
			intentos_fallidos.append(f"XPath #{i}: {xp}")
			print(f"[INTENTO] {org_code} - XPath #{i} falló para área '{area_value}'")
	print(f"[ERROR] {org_code} No se pudo seleccionar el área '{area_value}'")
	print(f"        Total de XPaths intentados: {len(xpaths)}")
	for xp_info in intentos_fallidos:
		print(f"           - {xp_info}")
	return False, None

def seleccionar_anio(driver, modulo: Dict[str, Any], org_code: str, year: int, timeout: int = 3, xpath_cache=None) -> bool:
	scraping_actions = modulo.get("scraping_actions", [])
	config_anio = None
	for sa in scraping_actions:
		if sa.get("type") == "select_anio":
			config_anio = sa
			break
	if not config_anio:
		print(f"[WARN] ({org_code}) No se encontró configuración 'select_anio' en scraping_actions.")
		return False
	patterns = config_anio.get("year_patterns", [])
	if not patterns:
		print(f"[WARN] ({org_code}) 'select_anio' no tiene 'year_patterns' definidos.")
		return False
	year_str = str(year)
	xpaths = [pat.replace("{YEAR}", year_str) for pat in patterns]
	print(f"[ACTION] {org_code} - Seleccionando año '{year_str}'")
	
	# Usar caché para acelerar búsqueda
	cache_key = (org_code, year, "anio")
	intentos_fallidos = []
	if xpath_cache:
		xp_cache = xpath_cache.get(cache_key)
		if xp_cache:
			exito = espera_click(driver, xp_cache, timeout=timeout, scroll=True)
			if exito:
				print(f"[OK] ({org_code}) Año '{year_str}' seleccionado (cache)")
				return True, xp_cache
	for i, xp in enumerate(xpaths, 1):
		print(f"[DEBUG] ({org_code}) Año {year_str} - Intento #{i}: probando XPath {xp}")
		exito = espera_click(driver, xp, timeout=timeout, scroll=True)
		if exito:
			if xpath_cache is not None:
				xpath_cache[cache_key] = xp
			if intentos_fallidos:
				print(f"[OK] ({org_code}) Año '{year_str}' seleccionado en el intento #{i}")
				print(f"     XPath exitoso: {xp}")
				print(f"     Intentos fallidos previos: {len(intentos_fallidos)}")
			else:
				print(f"[OK] ({org_code}) Año '{year_str}' seleccionado en el primer intento")
				print(f"     XPath: {xp}")
			return True, xp
		else:
			intentos_fallidos.append(f"XPath #{i}: {xp}")
			print(f"[INTENTO] {org_code} - XPath #{i} falló para año '{year_str}'")
	print(f"[ERROR] ({org_code}) No se pudo seleccionar el año '{year_str}'")
	print(f"        Total de XPaths intentados: {len(xpaths)}")
	for xp_info in intentos_fallidos:
		print(f"           - {xp_info}")
	return False, None

def seleccionar_mes(driver, modulo: Dict[str, Any], org_code: str, month: str, timeout: int = 3, xpath_cache=None):
	"""
	Selecciona el MES indicado (por ejemplo 'Enero'),
	usando el bloque 'select_mes' de scraping_actions en actions_transparencia.json.

	Usa patrones con placeholders:
	  - {MONTH}         -> tal como viene de settings.json (ej: 'Diciembre')
	  - {MONTH_LOWER}   -> en minúsculas (ej: 'diciembre')
	  - {MONTH_PARTIAL} -> abreviado (primeros 4 chars, ej: 'dici')

	Devuelve (True, xpath_usado) si tuvo éxito, (False, None) si no.
	"""
	scraping_actions = modulo.get("scraping_actions", [])
	config_mes = None

	# Buscar la acción tipo 'select_mes'
	for sa in scraping_actions:
		if sa.get("type") == "select_mes":
			config_mes = sa
			break

	if not config_mes:
		print(f"[WARN] ({org_code}) No se encontró configuración 'select_mes' en scraping_actions.")
		return False, None

	patterns = config_mes.get("month_patterns", [])
	if not patterns:
		print(f"[WARN] ({org_code}) 'select_mes' no tiene 'month_patterns' definidos.")
		return False, None

	# Normalizaciones
	month_str = str(month)                 # 'Diciembre'
	month_lower = month_str.lower()        # 'diciembre'
	month_partial = month_lower[:4]        # 'dici'

	xpaths = []
	for pat in patterns:
		xp = (pat.replace("{MONTH}", month_str)
				.replace("{MONTH_LOWER}", month_lower)
				.replace("{MONTH_PARTIAL}", month_partial))
		xpaths.append(xp)

	print(f"[ACTION] {org_code} - Seleccionando mes '{month_str}'")
	# Usar caché para acelerar búsqueda
	cache_key = (org_code, month, "mes")
	intentos_fallidos = []
	if xpath_cache:
		xp_cache = xpath_cache.get(cache_key)
		if xp_cache:
			exito = espera_click(driver, xp_cache, timeout=timeout, scroll=True)
			if exito:
				print(f"[OK] ({org_code}) Mes '{month_str}' seleccionado (cache)")
				return True, xp_cache
	for i, xp in enumerate(xpaths, 1):
		print(f"[DEBUG] ({org_code}) Mes {month_str} - Intento #{i}: probando XPath {xp}")
		exito = espera_click(driver, xp, timeout=timeout, scroll=True)

		if exito:
			if xpath_cache is not None:
				xpath_cache[cache_key] = xp
			if intentos_fallidos:
				print(f"[OK] ({org_code}) Mes '{month_str}' seleccionado en el intento #{i}")
				print(f"     XPath exitoso: {xp}")
				print(f"     Intentos fallidos previos: {len(intentos_fallidos)}")
			else:
				print(f"[OK] ({org_code}) Mes '{month_str}' seleccionado en el primer intento")
				print(f"     XPath: {xp}")
			return True, xp
		else:
			intentos_fallidos.append(f"XPath #{i}: {xp}")
			print(f"[INTENTO] {org_code} - XPath #{i} falló para mes '{month_str}'")

	print(f"[ERROR] ({org_code}) No se pudo seleccionar el mes '{month_str}'")
	print(f"        Total de XPaths intentados: {len(xpaths)}")
	for xp_info in intentos_fallidos:
		print(f"           - {xp_info}")

	return False, None

def descargar_csv(driver, modulo: Dict[str, Any], org_code: str, timeout: int = 3, xpath_cache=None):
    """
    Hace click en el botón/enlace de descarga CSV usando la configuración
    'download_csv' de scraping_actions en actions_transparencia.json.

    Devuelve (True, xpath_usado) si tuvo éxito, (False, None) si no.
    """
    scraping_actions = modulo.get("scraping_actions", [])
    config_csv = None

    # Buscar la acción tipo 'download_csv'
    for sa in scraping_actions:
        if sa.get("type") == "download_csv":
            config_csv = sa
            break

    if not config_csv:
        print(f"[WARN] ({org_code}) No se encontró configuración 'download_csv' en scraping_actions.")
        return False, None

    xpaths = config_csv.get("xpaths", [])
    selector_button = config_csv.get("selector_button")
    if selector_button:
        # Por compatibilidad, si aún usas selector_button
        xpaths.append(selector_button)

    if not xpaths:
        print(f"[WARN] ({org_code}) 'download_csv' no tiene XPaths definidos.")
        return False, None

    print(f"[ACTION] {org_code} - Intentando disparar descarga CSV")
    # Usar caché para acelerar búsqueda
    cache_key = (org_code, "csv")
    intentos_fallidos = []
    if xpath_cache:
        xp_cache = xpath_cache.get(cache_key)
        if xp_cache:
            exito = espera_click(driver, xp_cache, timeout=timeout, scroll=True)
            if exito:
                print(f"[OK] ({org_code}) CSV disparado (cache)")
                return True, xp_cache
    for i, xp in enumerate(xpaths, 1):
        print(f"[DEBUG] ({org_code}) CSV - Intento #{i}: probando XPath {xp}")
        exito = espera_click(driver, xp, timeout=timeout, scroll=True)

        if exito:
            if xpath_cache is not None:
                xpath_cache[cache_key] = xp
            if intentos_fallidos:
                print(f"[OK] ({org_code}) CSV disparado en el intento #{i}")
                print(f"     XPath exitoso: {xp}")
                print(f"     Intentos fallidos previos: {len(intentos_fallidos)}")
            else:
                print(f"[OK] ({org_code}) CSV disparado en el primer intento")
                print(f"     XPath: {xp}")
            return True, xp
        else:
            intentos_fallidos.append(f"XPath #{i}: {xp}")
            print(f"[INTENTO] {org_code} - XPath #{i} falló para descarga CSV")

    print(f"[ERROR] ({org_code}) No se pudo disparar la descarga CSV")
    print(f"        Total de XPaths intentados: {len(xpaths)}")
    for xp_info in intentos_fallidos:
        print(f"           - {xp_info}")

    return False, None