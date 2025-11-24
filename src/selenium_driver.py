from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def build_driver(headless: bool = True, download_root: str = "./data/raw"):
    """
    Construye y devuelve una instancia de Chrome (selenium-wire),
    configurada para descargar archivos en download_root.
    """

    download_dir = Path(download_root).resolve()
    download_dir.mkdir(parents=True, exist_ok=True)

    options = Options()

    if headless:
        # Nuevo modo headless (Chrome 109+)
        options.add_argument("--headless=new")

    #Imitar un Chrome normal (Evitar que el sitio detecte headless)
    options.add_argument(
        "--user-agent="
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        "AppleWebKit/537.36 (KHTML, like Gecko)"
        "Chrome/121.0.0.0 Safari/537.36"
    )
    
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1600,900")

    #Opciones para reducir señales ded automatización
    options.add_experimental_option("excludeSwitches",["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Preferencias de descarga
    prefs = {
        "download.default_directory": str(download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=options)
    #Más camuflaje, se quita el navigator.webdriver
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source":"""
                Object.defineProperty(navigator,'webdriver',
                                      get:() => undefined
                });
                """
            },
        )
    except Exception as e:
        print(f"[WARN] No se pudo ajustar navigator.webdriver:{e}")
    driver.set_page_load_timeout(60)

    return driver
