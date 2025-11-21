from typing import Dict, Any
from pathlib import Path

import time
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

def _ejecutar_actions_iniciales(driver, modulo: Dict[str, Any], org_code: str, timeout: int = 15):
    """
    Ejecuta la lista de 'actions' definida en el módulo:
    - Ir a la sección de personal / transparencia activa.
    """
    actions = modulo.get("actions", [])
    wait = WebDriverWait(driver, timeout)

    for action in actions:
        descripcion = action.get("description", "")
        xpath = action.get("xpath")
        tipo_accion = action.get("action", "click")
        optional = action.get("optional", False)

        if not xpath:
            print(f"[WARN] Acción sin xpath, se omite. Descripción: {descripcion}")
            continue

        print(f"[ACTION] {org_code} - {descripcion}")

        try:
            elemento = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))

            if tipo_accion == "click":
                elemento.click()
            else:
                print(f"[WARN] Tipo de acción '{tipo_accion}' no soportado aún; se esperaba 'click'.")

        except (TimeoutException, NoSuchElementException) as e:
            if optional:
                print(f"[WARN] Acción opcional falló y se omite. Descripción: {descripcion} | Error: {e}")
                continue
            else:
                print(f"[ERROR] No se pudo ejecutar acción obligatoria: {descripcion} | Error: {e}")
                # Aquí podríamos decidir si rompemos o solo salimos de este municipio.
                # Por ahora, salimos de la función para este municipio:
                return
            

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
        print(f"[OK] ({org_code}) Página del municipio cargada correctamente (readyState=complete).")
        return True
    
    except TimeoutException:
        print(f"[ERROR] ({org_code}) La página del municipio no termino de cargar en {timeout}s.")
        _guardar_screenshot(driver,org_code,"no_carga")
        print(f"[ERROR] ({org_code}) La página del municipio no termino de cargar en {timeout}")
        return False
    
def procesar_municipio(driver, org_code: str, settings: Dict[str, Any], actions_cfg: Dict[str, Any]):
    """
    Primera versión de procesar_municipio:
    - Construye la URL del municipio usando url_pattern del módulo genérico.
    - Abre la página del municipio.
    - Ejecuta las acciones iniciales (vacias).
    -Intenta hacer click en el boton 'Tipo de personal'.
    """

    modulo = _obtener_modulo_generico(actions_cfg)

    url_pattern = modulo.get("url_pattern")
    if not url_pattern:
        raise ValueError("El módulo no tiene 'url_pattern' definido.")

    url = url_pattern.format(org=org_code)

    tipos_personal = ["CONTRATA", "PLANTA"]

    resultados={}

    for tipo in tipos_personal:
        print(f"\n[INFO]({org_code}) - Abriendo tipo de personal {tipo}")
        driver.get(url)

        
        if not esperar_carga_municipio(driver,org_code, timeout=30):
            resultados[tipo]=False
            print("[INFO] ({org_code}) Fin de la fase tipo_personal '{tipo}' - FALLÓ (no cargo la pagina)")
            continue
        

        # Abrir el tipo de personal y guardar resultado
        exito=_abrir_tipo_personal(driver, modulo, org_code, tipo=tipo,timeout=25)
        resultados[tipo]=exito

        if exito:
            print(f"[INFO] ({org_code}) Fin de fase tipo_personal '{tipo}' - EXITO.")
        else:
            print(f"[INFO] ({org_code}) Fin de fase tipo_personal '{tipo}' - FALLÓ")
    
    #RESUMEN 
    print(f"\n[RESUMEN] Resultados para {org_code}:")
    for tipo, exito in resultados.items():
        status="EXITO" if exito else "FALLÓ"
        print(f"   - Tipo de personal '{tipo}': {status}")
    return resultados

def _abrir_tipo_personal(driver, modulo: Dict[str, Any], org_code: str, tipo: str, timeout: int = 25):
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
    page_text=driver.page_source
    texto_busqueda=[
        "Personal a Contrata",
        "Personal a contrata",
        "Personal de Planta",
        "Personal de planta"
    ]
    print(f"[DEBUG] ({org_code}) Headless DOM contiene textos clave?")
    for t in texto_busqueda:
        print(f"          - '{t}':{t in page_text}")

    for i,xp in enumerate(xpaths,1):

        print(f"[DEBUG] ({org_code}) Intento #{i}: probando XPath {xp}")
        exito=espera_click(driver,xp,timeout=timeout, scroll=True)

        if exito:
            if intentos_fallidos:
                print(f"[OK] {org_code} - tipo '{tipo}' abierto en intento #{i}")
                print(f"XPath exitoso:{xp}")
                print(f"Intentos fallidos previos {len(intentos_fallidos)}")
            else:
                print(f"[OK] {org_code} - tipo '{tipo}' abierto en el primer intento")
                print(f"XPath: {xp}")
            return True
        else:
            #Guardar el intento fallido
            intentos_fallidos.append(f"XPath {i}: {xp}")
            print(f"[INTENTO] {org_code} - XPath #{i} falló para tipo '{tipo}'")
    
    # -- Si llega aquí, ninguno funcionó --       
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
            time.sleep(0.5)  # Espera breve para que el scroll termine
        
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