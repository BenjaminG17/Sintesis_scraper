from typing import Dict, Any

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
        driver.implicitly_wait(2)
        
        # Si en el futuro añadimos acciones iniciales (por ejemplo ir a "Subsidios y beneficios"),
        # las ejecutaríamos aquí:
        # _ejecutar_actions_iniciales(driver, modulo, org_code)

        
        # Abrir el tipo de personal y guardar resultado
        exito=_abrir_tipo_personal(driver, modulo, org_code, tipo=tipo)
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

def _abrir_tipo_personal(driver, modulo: Dict[str, Any], org_code: str, tipo: str, timeout: int = 15):
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
        return

    xpaths = option.get("xpaths") or []
    if not xpaths:
        print(f"[WARN] La opción '{tipo}' no tiene xpaths definidos.")
        return

    wait = WebDriverWait(driver, timeout)
    print(f"[ACTION] {org_code} - Abriendo tipo de personal '{tipo}'")

    intentos_fallidos=[]

    for i,xp in enumerate(xpaths,1):
        try:
            elemento = wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
            elemento.click()

            # SI FUNCIONA - Mostrar resumen
            if intentos_fallidos:
                print(f"[OK] {org_code} - tipo '{tipo}' abierto en intento #{i}")
                print(f"XPath exitoso:{xp}")
                print(f"Intentos fallidos previos {len(intentos_fallidos)}")
            else:
                print(f"[OK] {org_code} - tipo '{tipo}' abierto en el primer intento")
                print(f"XPath: {xp}")

            return True
        
        except (TimeoutException, NoSuchElementException) as e:
            #Guardar el intento fallido
            intentos_fallidos.append(f"XPath {i}: {xp}")
            print(f"[INTENTO] {org_code} - XPath #{i} falló para tipo '{tipo}'")
            
    print(f"[ERROR] {org_code} No se pudo abrir el tipo de personal '{tipo}'")
    print(f"        Total de XPaths intentados: {len(xpaths)}")
    print("         XPaths probados:")
    for xp_info in intentos_fallidos:
        print(f"           - {xp_info}")
    return False

def espera_click (driver,xpath, timeout=15):
    try:
        elemento =WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, xpath))
        )
        elemento.click()
        return True
    except:
        return False