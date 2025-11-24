from typing import Dict, Any
from .browser_helpers import _guardar_screenshot
from .browser_helpers import espera_click
from selenium.webdriver.support.ui import WebDriverWait


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
	modulo = _obtener_modulo_generico(actions_cfg)
	url_pattern = modulo.get("url_pattern")
	if not url_pattern:
		raise ValueError("El módulo no tiene 'url_pattern' definido.")
	url = url_pattern.format(org=org_code)
	tipos_personal = ["CONTRATA", "PLANTA"]
	start_year = settings.get("start_year")
	resultados: Dict[str, Dict[str, Any]] = {}
	acceso_municipio_exitoso = False
	for tipo in tipos_personal:
		print(f"\n[INFO] ({org_code}) - Procesando tipo de personal: {tipo}")
		driver.get(url)
		if not esperar_carga_municipio(driver, org_code):
			resultados[tipo] = {
				"tipo_personal_ok": False,
				"area_municipal_ok": False,
				"anio_ok": False,
				"xpath_tipo": None,
				"xpath_area": None,
				"xpath_anio": None,
			}
			print(f"[INFO] ({org_code}) Fin de la fase tipo_personal '{tipo}' - FALLÓ (no cargó la página)")
			continue
		acceso_municipio_exitoso = True
		print(f"[PASO 1] ({org_code}) Abriendo tipo de personal: {tipo}")
		exito_tipo, xpath_tipo = abrir_tipo_personal(driver, modulo, org_code, tipo=tipo)
		if not exito_tipo:
			print(f"[INFO] ({org_code}) Fin de fase tipo_personal '{tipo}' - FALLÓ (no se abrió)")
			resultados[tipo] = {
				"tipo_personal_ok": False,
				"area_municipal_ok": False,
				"anio_ok": False,
				"xpath_tipo": None,
				"xpath_area": None,
				"xpath_anio": None,
			}
			continue
		print(f"[PASO 2] ({org_code}) Intentando seleccionar área MUNICIPAL para tipo: {tipo}")
		exito_area, xpath_area = seleccionar_area(driver, modulo, org_code, area_value="MUNICIPAL")
		print(f"[PASO 3] ({org_code}) Seleccionando año {start_year} para tipo: {tipo}")
		exito_anio, xpath_anio = seleccionar_anio(driver, modulo, org_code, year=start_year)
		if exito_anio:
			print(f"[INFO] ({org_code}) Año {start_year} seleccionado correctamente para tipo {tipo}.")
		else:
			print(f"[WARN] ({org_code}) No se pudo seleccionar el año {start_year} para tipo {tipo}.")
		resultados[tipo] = {
			"tipo_personal_ok": True,
			"area_municipal_ok": bool(exito_area),
			"anio_ok": bool(exito_anio),
			"xpath_tipo": xpath_tipo,
			"xpath_area": xpath_area,
			"xpath_anio": xpath_anio,
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
		extra = " (skip_por_contrata)" if datos.get("skip_por_contrata") else ""
		print(
			f"   - Tipo de personal '{tipo}': {status_tipo}{extra} | "
			f"Área MUNICIPAL: {status_area} | "
			f"Año: {status_anio}"
		)
	return {
		"acceso_municipio_exitoso": acceso_municipio_exitoso,
		"tipo_municipio_detectado": tipo_municipio_detectado,
		"detalle_por_tipo": resultados,
	}

def abrir_tipo_personal(driver, modulo: Dict[str, Any], org_code: str, tipo: str, timeout: int = 20):
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
	
	intentos_fallidos = []
	for i, xp in enumerate(xpaths, 1):
		print(f"[DEBUG] ({org_code}) Intento #{i}: XPath {xp}")
		exito = espera_click(driver, xp, timeout=timeout, scroll=True)
		if exito:
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

def seleccionar_area(driver, modulo: Dict[str, Any], org_code: str, area_value: str = "MUNICIPAL", timeout: int = 5) -> bool:
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
	
	intentos_fallidos = []
	for i, xp in enumerate(xpaths, 1):
		print(f"[DEBUG] ({org_code}) Intento #{i}: probando XPath {xp}")
		exito = espera_click(driver, xp, timeout=timeout, scroll=True)
		if exito:
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

def seleccionar_anio(driver, modulo: Dict[str, Any], org_code: str, year: int, timeout: int = 5) -> bool:
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
	
	intentos_fallidos = []
	for i, xp in enumerate(xpaths, 1):
		print(f"[DEBUG] ({org_code}) Año {year_str} - Intento #{i}: probando XPath {xp}")
		exito = espera_click(driver, xp, timeout=timeout, scroll=True)
		if exito:
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
