from .config import load_settings, load_actions, load_env
from.selenium_driver import build_driver
from .transparencia_workflow import procesar_municipio
import time 

def obtener_lista_municipios(settings: dict) -> list[str]:
    """
    - Si 'orgs' en settings tiene valores, usamos esa lista (modo test).
    - Si 'orgs' está vacío o no existe, usamos el rango org_start..org_end.
    """
    orgs_config = settings.get("orgs") or []

    if orgs_config:
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
    try:
        print("Driver inicializado correctamente.")

        
        if not orgs:
            print("[WARN] No hay municipios configurados en settings.")
            return
        

        tiempo_inicio=time.time()
        n=1
        for org in orgs:
            
            print(f"\n=== PROCESANDO MUNICIPIO: {org} ===")
            t_inicio_muni=time.time()
            procesar_municipio(driver, org, settings, actions)  

            t_final_muni=time.time()  
            duracion=t_final_muni - t_inicio_muni

            print(f"\n=== MUNICIPIO {org} PROCESADO ({n}/{len(orgs)}) ===")
            print(f"⏱️ Tiempo municipal: {duracion:.2f} segundos")
            n+=1

        tiempo_final=time.time()
        total=tiempo_final - tiempo_inicio

        horas = int(total // 3600)
        minutos = int((total % 3600) // 60)
        segundos = int(total % 60)

        print(
            f"\n[TIEMPO] Tiempo total de ejecución: "
            f"{horas:02d}:{minutos:02d}:{segundos:02d} (hh:mm:ss)"
        )
        # ==========================================
        
    finally:
        print("\nCerrando navegador...")
        driver.quit()
        print("Navegador cerrado. Fin de main().")

if __name__ == "__main__":
    main()