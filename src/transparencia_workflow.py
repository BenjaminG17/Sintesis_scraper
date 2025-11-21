
import time
from typing import Dict, Any
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException



def _obtener_modulo_generico(actions_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Obtiene el módulo 'municipio_generico' desde actions_transparencia.json.
    Si no existe con ese id, toma el primero de la lista.
    """
    modules = actions_cfg.get("modules", [])
    if not modules:
        raise ValueError("No hay módulos definidos en actions_transparencia.json")

    for m in modules:
        if m.get("id") == "municipio_generico":
            return m

    # fallback: primer módulo
    return modules[0]            

def esperar_carga_municipio(driver,org_code:str, timeout: int = 20):
    """
    Espera hasta que la página del municipio haya termine de cargar.
    comprobando que la pagina este completamente cargada
    document.readyState == "complete"
    """
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        print(f"[OK] ({org_code}) Página del municipio cargada correctamente.")
        #(readyState=complete)
        return True
    
    except TimeoutException:
        print(f"[ERROR] ({org_code}) La página del municipio no termino de cargar en {timeout}s.")
        _guardar_screenshot(driver,org_code,"no_carga")
        print(f"[ERROR] ({org_code}) La página del municipio no termino de cargar en {timeout}")
        return False
    
def procesar_municipio(driver, org_code: str, settings: Dict[str, Any], actions_cfg: Dict[str, Any]):
    """
    - Construye la URL del municipio usando url_pattern del módulo genérico.
    - Abre la página del municipio.
    - Para cada tipo de personal (CONTRATA / PLANTA):
        - Espera carga del municipio
        - Abrir tipo personal
        - Seleccionar área municipal (si es que existe)
    - Si tipo personal de CONTRATA falla completamente, omitir PLANTA.
    """

    modulo = _obtener_modulo_generico(actions_cfg)

    url_pattern = modulo.get("url_pattern")
    if not url_pattern:
        raise ValueError("El módulo no tiene 'url_pattern' definido.")

    url = url_pattern.format(org=org_code)

    tipos_personal = ["CONTRATA", "PLANTA"]

    # resultados[tipo] = {
    #   "tipo_personal_ok": bool,
    #   "area_municipal_ok": bool,
    #   "skip_por_contrata": bool
    # }
    resultados: Dict[str, Dict[str, Any]] = {}

    acceso_municipio_exitoso = False
    skip_planta_por_contrata = False             # CONTRATA falló completamente 
    municipal_no_disponible = False              # No hay panel de área municipal detectado en CONTRATA

    for tipo in tipos_personal:

        # si CONTRATA ya falló del todo, saltamos PLANTA ---
        if tipo == "PLANTA" and skip_planta_por_contrata:
            print(f"\n[SKIP] ({org_code}) - Se omite tipo de personal {tipo}, CONTRATA fallo todos los xpath")
            resultados[tipo] = {
                "tipo_personal_ok": False,
                "area_municipal_ok": False,
                "skip_por_contrata": True,
                "skip_por_area": False,
            }
            continue

        # si no hay área municipal en CONTRATA, saltamos PLANTA
        if tipo == "PLANTA" and municipal_no_disponible:
            print(f"\n[SKIP] ({org_code}) - Área MUNICIPAL no disponible (detectado en CONTRATA). "
                  f"Se omite PLANTA.")
            resultados[tipo] = {
                "tipo_personal_ok": False,
                "area_municipal_ok": False,
                "skip_por_contrata": False,
                "skip_por_area": True,
            }
            continue

        print(f"\n[INFO]({org_code}) - Abriendo tipo de personal {tipo}")
        driver.get(url)

        # Verificar carga de la página
        if not esperar_carga_municipio(driver, org_code, timeout=30):
            resultados[tipo] = {
                "tipo_personal_ok": False,
                "area_municipal_ok": False,
                "skip_por_contrata": False,
                "skip_por_area": False,
            }
            print(f"[INFO] ({org_code}) Fin de la fase tipo_personal '{tipo}' - FALLÓ (no cargó la página)")
            if tipo == "CONTRATA":
                skip_planta_por_contrata = True
            continue

        acceso_municipio_exitoso = True
        # 1) Abrir el tipo de personal y guardar resultado
        exito_tipo = abrir_tipo_personal(driver, modulo, org_code, tipo=tipo)

        if not exito_tipo:
            print(f"[INFO] ({org_code}) Fin de fase tipo_personal '{tipo}' - FALLÓ")
            resultados[tipo] = {
                "tipo_personal_ok": False,
                "area_municipal_ok": False,
                "skip_por_contrata": False,
                "skip_por_area": False,
            }
            if tipo == "CONTRATA":
                skip_planta_por_contrata = True
            continue

        print(f"[INFO] ({org_code}) Fase tipo_personal '{tipo}' - ÉXITO al abrir vista de personal.")

        # Seleccionar área MUNICIPAL (si existe panel de área)
        exito_area = seleccionar_area(driver, modulo, org_code, area_value="MUNICIPAL")

        if tipo == "CONTRATA" and not exito_area:
            municipal_no_disponible = True
            print(f"[DEBUG] ({org_code}) municipal_no_disponible = True ( No se encontro área MUNICIPAL en CONTRATA)")

        resultados[tipo] = {
            "tipo_personal_ok": True,
            "area_municipal_ok": exito_area,
            "skip_por_contrata": False,
            "spik_por_area": False,
        }

    # ---- Resumen a nivel municipio ----
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
        extra = " (skip_por_contrata)" if datos.get("skip_por_contrata") else ""

        print(
            f"   - Tipo de personal '{tipo}': {status_tipo}{extra} | "
            f"Área MUNICIPAL: {status_area}"
        )

    return {
        "acceso_municipio_exitoso": acceso_municipio_exitoso,
        "tipo_municipio_detectado": tipo_municipio_detectado,
        "detalle_por_tipo": resultados,
    }

def abrir_tipo_personal(driver, modulo: Dict[str, Any], org_code: str, tipo: str, timeout: int = 20):
    """
    Abre la página del tipo de personal indicado (CONTRATA o PLANTA),
    utilizando los XPaths configurados en scraping_actions (por texto del enlace).
    """
    scraping_actions = modulo.get("scraping_actions", [])
    config_tipo = None

    # Buscar la acción tipo 'open_tipo_personal'
    for sa in scraping_actions:
        if sa.get("type") == "open_tipo_personal":
            config_tipo = sa
            break

    if not config_tipo:
        print(f"[WARN] No se encontró configuración 'open_tipo_personal' en scraping_actions.")
        return

    # Buscar la opción correspondiente al tipo solicitado
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

    intentos_fallidos=[]

    ## DEBUG para poder ver si el texto esperado esta en el HTML que se recibio en el driver
   # page_text=driver.page_source
    #texto_busqueda=[
    #    "Personal a Contrata",
    #    "Personal a contrata",
    #    "Personal de Planta",
    #    "Personal de planta"
    #]
    #print(f"[DEBUG] ({org_code}) Headless DOM contiene textos clave?")
    #for t in texto_busqueda:
    #    print(f"          - '{t}':{t in page_text}")

    for i,xp in enumerate(xpaths,1):

        print(f"[DEBUG] ({org_code}) Intento #{i}: XPath {xp}")
        exito=espera_click(driver,xp,timeout=timeout, scroll=True)

        if exito:
            if intentos_fallidos:
                print(f"[OK] {org_code} - tipo '{tipo}' abierto en intento #{i}")
                print(f"XPath exitoso:{xp}")
                print(f"Intentos fallidos {len(intentos_fallidos)}")
            else:
                print(f"[OK] {org_code} - tipo '{tipo}' abierto en el primer intento")
                print(f"XPath: {xp}")
            return True
        else:
            #Guardar el intento fallido
            intentos_fallidos.append(f"XPath {i}: {xp}")
            print(f"[INTENTO] {org_code} - XPath #{i} falló para tipo '{tipo}'")
    
    # -- Ninguno funcionó --       
    print(f"[ERROR] {org_code} No se pudo abrir el tipo de personal '{tipo}'")
    print(f"        Total de XPaths intentados: {len(xpaths)}")
    print("         XPaths probados:")
    for xp_info in intentos_fallidos:
        print(f"           - {xp_info}")
    return False

def espera_click (driver,xpath:str, timeout:int=10, scroll:bool=True)->bool:
    try:
        wait= WebDriverWait(driver, timeout)
        elemento =wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))

        if scroll:
            driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                elemento,
            )
            time.sleep(0.5)  
        
        elemento.click()
        return True
    except Exception as e:
        print(f"[ERROR] No se pudo clickear el xpath: {xpath}.Error:{type(e).__name__}:{e}")
        return False
    
def _guardar_screenshot(driver,org_code:str, sufijo:str):
    screenshots_dir= Path("screenshots")
    screenshots_dir.mkdir(exist_ok=True)
    filename=screenshots_dir /f"{org_code}_{sufijo}.png"
    driver.save_screenshot(str(filename))
    print(f"[DEBUG] Screenshot guardado: {filename}")

def seleccionar_area(driver,modulo: Dict[str, Any],org_code: str,area_value: str = "MUNICIPAL",timeout: int = 5) -> bool:
    """
    Selecciona el área indicada (por defecto 'MUNICIPAL')
    usando la configuración 'select_area' en scraping_actions.
    Devuelve True si hizo click en algún xpath, False si no.
    """
    scraping_actions = modulo.get("scraping_actions", [])
    config_area = None

    # Buscar la acción tipo 'select_area'
    for sa in scraping_actions:
        if sa.get("type") == "select_area":
            config_area = sa
            break

    if not config_area:
        print(f"[WARN] ({org_code}) No se encontró configuración 'select_area' en scraping_actions.")
        return False

    # Buscar la opción que coincida con el área deseada ('MUNICIPAL')
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
                print(f"[OK] ({org_code}) Área '{area_value}' seleccionada en el primer intento")
                print(f"     XPath: {xp}")
            return True
        else:
            intentos_fallidos.append(f"XPath #{i}: {xp}")
            print(f"[INTENTO] {org_code} - XPath #{i} falló para área '{area_value}'")

    # Si llega aquí, ninguno funcionó
    print(f"[ERROR] {org_code} No se pudo seleccionar el área '{area_value}'")
    print(f"        Total de XPaths intentados: {len(xpaths)}")
    for xp_info in intentos_fallidos:
        print(f"           - {xp_info}")
    return False
