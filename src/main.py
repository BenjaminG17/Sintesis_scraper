from .config import load_settings, load_actions, load_env
from.selenium_driver import build_driver

def obtener_lista_municipios(settings: dict) -> list[str]:
    """
    Devuelve la lista de códigos MUxxx a procesar.

    - Si 'orgs' en settings tiene valores, usamos esa lista (modo test).
    - Si 'orgs' está vacío o no existe, usamos el rango org_start..org_end.
    """
    orgs_config = settings.get("orgs") or []

    if orgs_config:
        # Ya vienen códigos tipo "MU042", "MU120", etc.
        return orgs_config

    # Modo rango completo
    org_start = settings.get("org_start", 1)
    org_end = settings.get("org_end", 345)
    return [f"MU{n:03d}" for n in range(org_start, org_end + 1)]

def main():
    settings = load_settings()
    actions = load_actions()
    env=load_env()

    orgs= obtener_lista_municipios(settings)

    print("=== SETTINGS ===")
    print(f"base_url   : {settings.get('base_url')}")
    print(f"org_start  : {settings.get('org_start')}")
    print(f"org_end    : {settings.get('org_end')}")
    print(f"start_year : {settings.get('start_year')}")
    print(f"months     : {settings.get('months')}")
    print(f"orgs (modo actual): {orgs}")

    print("\n=== ENV ===")
    print(f"HEADLESS      : {env['HEADLESS']}")
    print(f"DOWNLOAD_ROOT : {env['DOWNLOAD_ROOT']}")
    print(f"STAGING_DIR   : {env['STAGING_DIR']}")
    print(f"FINAL_DIR     : {env['FINAL_DIR']}")

    print("\n=== ACTIONS ===")
    modules = actions.get("modules", [])
    print(f"módulos definidos: {len(modules)}")
    if modules:
        print(f"primer módulo id : {modules[0].get('id')}")
        print(f"url_pattern      : {modules[0].get('url_pattern')}")
    
    ## Aquí se realiza la prueba del driver
    print("\n=== DRIVER ===")
    print("Inicializando driver de Selenium...")

    driver = build_driver(
        headless=env["HEADLESS"],
        download_root=env["DOWNLOAD_ROOT"],
    )

    print("Driver inicializado correctamente. Cerrando navegador...")
    driver.quit()
    print("Navegador cerrado. Fin de main().")

if __name__ == "__main__":
    main()