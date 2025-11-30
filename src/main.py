from src.utils.browser_helpers import build_driver
from src.utils.navigation_helpers import procesar_municipio, get_meses_para_year
from src.utils.logging_helpers import setup_detailed_logger, log_resumen_terminal
from src.utils.logging_helpers import log_detallado_municipio
from src.config import load_settings, load_actions, load_env
import os
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
    env = load_env()
    orgs = obtener_lista_municipios(settings)

    logger_detallado = setup_detailed_logger()

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

        tiempo_inicio = time.time()
        
        
        for year in range(settings["start_year"], settings["end_year"] + 1):
            print(f"\n[INFO] Procesando año: {year}")
            # 👇 meses válidos para ESTE año (considerando año actual)
            meses_para_year = get_meses_para_year(year, settings)
            if not meses_para_year:
                print(f"[INFO] Año {year} es el año actual y aún no hay meses completos para procesar. Se omite.")
                continue
            n = 1
            for org_code in orgs:
                print(f"[INFO] Procesando municipio: {org_code} para año: {year}")
                tipos_personal = ["CONTRATA", "PLANTA"]
                #meses = settings.get("months", [])
                meses = meses_para_year
                archivos_completos = True

                # Verificar si ya existen todos los CSV
                for tipo in tipos_personal:
                    for mes in meses:
                        nombre_csv = f"{org_code}_{tipo}_{year}_{mes}.csv"
                        ruta_csv = os.path.join(env["DOWNLOAD_ROOT"], org_code, tipo, str(year), nombre_csv
                        )
                        if not os.path.exists(ruta_csv):
                            archivos_completos = False
                            break
                    if not archivos_completos:
                        break

                if archivos_completos:
                    print(f"[INFO] Todos los CSV ya existen para municipio {org_code} en año {year}. Se omite.")
                    continue

                # Si faltan archivos, procesar el municipio para ese año y loguear resumen
                t_inicio_muni = time.time()
                resultados = procesar_municipio(driver, org_code, settings, actions, year=year, meses=meses,)
                t_final_muni = time.time()
                duracion = t_final_muni - t_inicio_muni

                # Construir resumen para logging, usando la estructura nueva
                detalle_por_tipo = resultados.get("detalle_por_tipo", {})
                tipos_personal_resumen = {}

                for tipo, datos_por_anio in detalle_por_tipo.items():
                    # datos_por_anio es {year: {...}}
                    datos = datos_por_anio.get(year, {}) if isinstance(datos_por_anio, dict) else {}
                    meses_detalle = datos.get("meses_detalle", {}) or {}

                    algun_csv_ok = any(
                        (info.get("csv_status") == "ÉXITO")
                        for info in meses_detalle.values()
                    ) if meses_detalle else False

                    if meses_detalle:
                        csv_resumen = "ÉXITO" if algun_csv_ok else "FALLÓ"
                    else:
                        csv_resumen = "N/A"

                    tipos_personal_resumen[tipo] = {
                        'personal': 'ÉXITO' if datos.get('tipo_personal_ok') else 'FALLÓ',
                        'area': 'ÉXITO' if datos.get('area_municipal_ok') else 'FALLÓ',
                        'año': 'ÉXITO' if datos.get('anio_ok') else 'FALLÓ',
                        'meses': 'ÉXITO' if datos.get('meses_ok') else 'FALLÓ',
                        'CSV': csv_resumen,
                        'xpath_tipo': datos.get('xpath_tipo'),
                        'xpath_area': datos.get('xpath_area'),
                        'xpath_anio': datos.get('xpath_anio'),
                        'meses_detalle': meses_detalle,
                    }

                resumen_dict = {
                    'acceso_municipio_exitoso': resultados.get('acceso_municipio_exitoso'),
                    'tipo_municipio_detectado': resultados.get('tipo_municipio_detectado'),
                    'tipos_personal': tipos_personal_resumen
                }

                # Logging detallado y resumen
                log_detallado_municipio(logger_detallado, org_code, year,duracion, resumen_dict)
                log_resumen_terminal(org_code,year, resumen_dict)

                print(f"\n=== MUNICIPIO {org_code} PROCESADO ({n}/{len(orgs)}) ===")
                print(f"⏱️ Tiempo municipal: {duracion:.2f} segundos")
                n += 1

        tiempo_final = time.time()
        total = tiempo_final - tiempo_inicio
        horas = int(total // 3600)
        minutos = int((total % 3600) // 60)
        segundos = int(total % 60)
        print(
            f"\n[TIEMPO] Tiempo total de ejecución: "
            f"{horas:02d}:{minutos:02d}:{segundos:02d} (hh:mm:ss)"
        )
    finally:
        print("\nCerrando navegador...")
        driver.quit()
        print("Navegador cerrado. Fin de main().")

if __name__ == "__main__":
    main()