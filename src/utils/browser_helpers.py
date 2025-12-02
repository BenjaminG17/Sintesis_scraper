from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import shutil

def build_driver(headless: bool = True, download_root: str = "./data/raw"):
    download_dir = Path(download_root).resolve()
    download_dir.mkdir(parents=True, exist_ok=True)
    
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    
    options.add_argument(
        "--user-agent="
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        "AppleWebKit/537.36 (KHTML, like Gecko)"
        "Chrome/121.0.0.0 Safari/537.36"
    )
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1600,1080")
    options.add_experimental_option("excludeSwitches",["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    prefs = {
        "download.default_directory": str(download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(options=options)
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source":"""
                Object.defineProperty(navigator,'webdriver',{
                    get:() => undefined
                });
                """
            },
        )
    except Exception as e:
        print(f"[WARN] No se pudo ajustar navigator.webdriver:{e}")
    
    driver.set_page_load_timeout(60)
    return driver

def espera_click(driver, xpath: str, timeout: int = 2, scroll: bool = True) -> bool:
    try:
        wait = WebDriverWait(driver, timeout)
        elemento = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
        if scroll:
            driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});",
                elemento,
            )
            time.sleep(0.1)
        elemento.click()
        time.sleep(0.1)
        return True
    except Exception:
        return False

def _guardar_screenshot(driver, org_code: str, sufijo: str):
    screenshots_dir = Path("screenshots")
    screenshots_dir.mkdir(exist_ok=True)
    filename = screenshots_dir / f"{org_code}_{sufijo}.png"
    driver.save_screenshot(str(filename))
    print(f"[DEBUG] Screenshot guardado: {filename}")

def esperar_y_mover_csv(download_root: str, municipio: str, tipo_personal: str, 
                       year: int, mes: str, timeout: int = 15) -> str:
    download_dir = Path(download_root)
    inicio = time.time()
    temporales = [".crdownload", ".tmp", ".part"]
    archivo_descargado = None
    
    print(f"[INFO] Esperando CSV para {municipio} - {tipo_personal} - {year}-{mes}")
    
    while time.time() - inicio < timeout:
        try:
            archivos = list(download_dir.iterdir())
            for f in archivos:
                if f.is_file():
                    try:
                        if f.stat().st_size == 0:
                            continue
                            
                        if f.suffix.lower() == ".csv":
                            with open(f, 'r', encoding='utf-8', errors='ignore') as test_file:
                                test_file.read(1024)
                            archivo_descargado = f
                            print(f"[INFO] CSV encontrado: {f.name} ({f.stat().st_size} bytes)")
                            break
                    except:
                        continue

            if archivo_descargado:
                break
                
            time.sleep(0.5)
        except Exception as e:
            print(f"[WARN] Error escaneando archivos: {e}")
            time.sleep(0.5)
    
    if not archivo_descargado:
        print(f"[ERROR] No se encontró CSV para {municipio} en {timeout}s.")
        return None

    destino = download_dir / municipio / tipo_personal / str(year)
    destino.mkdir(parents=True, exist_ok=True)

    nombre_final = f"{municipio}_{tipo_personal}_{year}_{mes}.csv"
    ruta_final = destino / nombre_final

    try:
        temp_final = ruta_final.with_suffix('.tmp')
        shutil.copy2(archivo_descargado, temp_final)
        
        if temp_final.stat().st_size > 0:
            if ruta_final.exists():
                ruta_final.unlink()
            
            temp_final.rename(ruta_final)
            print(f"[OK] CSV movido a: {ruta_final}")
            
            try:
                archivo_descargado.unlink()
            except:
                pass
                
            return str(ruta_final)
        else:
            temp_final.unlink()
            return None
            
    except Exception as e:
        print(f"[ERROR] No se pudo mover CSV: {e}")
        for temp_file in [temp_final, archivo_descargado]:
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass
        return None