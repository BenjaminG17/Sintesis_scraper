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
    - Ejecuta las acciones iniciales (ir a sección personal).
    """

    modulo = _obtener_modulo_generico(actions_cfg)

    url_pattern = modulo.get("url_pattern")
    if not url_pattern:
        raise ValueError("El módulo no tiene 'url_pattern' definido.")

    url = url_pattern.format(org=org_code)

    print(f"\n[INFO] Abriendo municipio {org_code} -> {url}")
    driver.get(url)

    # Aquí podríamos agregar una espera genérica de carga inicial si es necesario
    # por ahora confiamos en las esperas explícitas de las acciones.
    _ejecutar_actions_iniciales(driver, modulo, org_code)
    print(f"[INFO] Acciones iniciales finalizadas para {org_code}")
