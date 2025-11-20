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

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1600,1080")

    # Preferencias de descarga
    prefs = {
        "download.default_directory": str(download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)

    # Usamos selenium-wire para poder inspeccionar requests más adelante si queremos
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(60)

    return driver
