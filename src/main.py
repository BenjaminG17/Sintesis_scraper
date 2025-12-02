from src.utils.browser_helpers import build_driver
from src.utils.navigation_helpers import procesar_municipio, get_meses_para_year
from src.utils.logging_helpers import setup_detailed_logger, log_resumen_terminal
from src.utils.logging_helpers import log_detallado_municipio
from src.config import load_settings, load_actions, load_env
from pathlib import Path
import os
import time 
import signal
import sys 

def obtener_lista_municipios(settings: dict) -> list[str]:
    orgs_config = settings.get("orgs") or []
    excluded = set(settings.get("excluded_orgs") or [])

    if orgs_config:
        return [org for org in orgs_config if org not in excluded]

    org_start = settings.get("org_start")
    org_end = settings.get("org_end")
    todos=[f"MU{n:03d}" for n in range(org_start, org_end + 1)]

    return [org for org in todos if org not in excluded]

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

def limpiar_archivos_temporales(download_root: str):
    download_dir = Path(download_root)
    if not download_dir.exists():
        return
        
    extensiones_temporales = [".crdownload", ".tmp", ".part", ".bak"]
    archivos_eliminados = 0
    
    for archivo in download_dir.rglob("*"):
        if archivo.is_file():
            if any(archivo.name.endswith(ext) for ext in extensiones_temporales):
                try:
                    archivo.unlink()
                    archivos_eliminados += 1
                except:
                    pass
            elif archivo.suffix.lower() == ".csv":
                try:
                    if archivo.stat().st_size == 0:
                        archivo.unlink()
                        archivos_eliminados += 1
                except:
                    pass
                    
    if archivos_eliminados > 0:
        print(f"[INFO] Se limpiaron {archivos_eliminados} archivos temporales")

def signal_handler(sig, frame):
    print(f"\n[INFO] Interrupción recibida. Cerrando...")
    if 'driver' in globals():
        try:
            globals()['driver'].quit()
            print("[INFO] Navegador cerrado.")
        except:
            pass
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)
    
    settings = load_settings()
    actions = load_actions()
    env = load_env()
    orgs = obtener_lista_municipios(settings)

    logger_detallado = setup_detailed_logger()

    print("=== CONFIGURACIÓN ===")
    print(f"Municipios a procesar: {len(orgs)}")
    print(f"Año inicio: {settings.get('start_year')}")
    print(f"Año fin: {settings.get('end_year')}")
    print(f"Modo HEADLESS: {env['HEADLESS']}")
    print(f"Directorio descargas: {env['DOWNLOAD_ROOT']}")

    limpiar_archivos_temporales(env["DOWNLOAD_ROOT"])

    driver = build_driver(
        headless=env["HEADLESS"],
        download_root=env["DOWNLOAD_ROOT"],
    )
    
    globals()['driver'] = driver
    
    try:
        print("Driver inicializado correctamente.")
        print("[INFO] Presiona Ctrl+C para detener.")
        
        if not orgs:
            print("[WARN] No hay municipios configurados.")
            return

        tiempo_inicio = time.time()
        municipios_procesados = 0
        
        for year in range(settings["start_year"], settings["end_year"] + 1):
            print(f"\n[INFO] Procesando año: {year}")
            meses_para_year = get_meses_para_year(year, settings)
            if not meses_para_year:
                print(f"[INFO] Año {year} no tiene meses completos. Se omite.")
                continue
            
            for org_code in orgs:
                try:
                    print(f"\n[INFO] {'='*50}")
                    print(f"[INFO] Municipio: {org_code} | Año: {year}")
                    print(f"[INFO] Meses a procesar: {len(meses_para_year)}")
                    
                    tipos_personal = ["CONTRATA", "PLANTA"]
                    archivos_completos = True

                    # Verificar archivos existentes
                    for tipo in tipos_personal:
                        for mes in meses_para_year:
                            nombre_csv = f"{org_code}_{tipo}_{year}_{mes}.csv"
                            ruta_csv = os.path.join(env["DOWNLOAD_ROOT"], org_code, tipo, str(year), nombre_csv)
                            
                            if not safe_file_check(ruta_csv):
                                archivos_completos = False
                                break
                        if not archivos_completos:
                            break

                    if archivos_completos:
                        print(f"[SKIP] Todos los CSV ya existen para {org_code} en {year}.")
                        continue

                    # Procesar municipio
                    t_inicio_muni = time.time()
                    resultados = procesar_municipio(
                        driver, org_code, settings, actions, 
                        year=year, meses=meses_para_year
                    )
                    t_final_muni = time.time()
                    duracion = t_final_muni - t_inicio_muni

                    # Logging
                    detalle_por_tipo = resultados.get("detalle_por_tipo", {})
                    tipos_personal_resumen = {}

                    for tipo, datos_por_anio in detalle_por_tipo.items():
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

                    log_detallado_municipio(logger_detallado, org_code, year, duracion, resumen_dict)
                    log_resumen_terminal(org_code, year, resumen_dict)
                    
                    municipios_procesados += 1
                    print(f"[TIEMPO] Municipio {org_code}: {duracion:.2f}s")
                    print(f"[PROGRESO] {municipios_procesados}/{len(orgs)} municipios")

                except KeyboardInterrupt:
                    raise  # Re-lanzar para manejo global
                except Exception as e:
                    print(f"[ERROR] Error en {org_code}: {e}")
                    continue

        tiempo_final = time.time()
        total = tiempo_final - tiempo_inicio
        horas = int(total // 3600)
        minutos = int((total % 3600) // 60)
        segundos = int(total % 60)
        
        print(f"\n{'='*60}")
        print(f"[FINAL] Tiempo total: {horas:02d}:{minutos:02d}:{segundos:02d}")
        print(f"[FINAL] Municipios procesados: {municipios_procesados}")
        print(f"[FINAL] Tiempo promedio por municipio: {total/max(1, municipios_procesados):.2f}s")

    except KeyboardInterrupt:
        print(f"\n[INFO] Ejecución interrumpida por usuario.")
    except Exception as e:
        print(f"[ERROR] Error general: {e}")
    finally:
        print("\nCerrando navegador...")
        driver.quit()
        print("Navegador cerrado. Fin.")

if __name__ == "__main__":
    main()