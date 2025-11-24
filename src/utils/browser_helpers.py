from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def build_driver(headless: bool = True, download_root: str = "./data/raw"):
	"""
	Construye y devuelve una instancia de Chrome (selenium-wire),
	configurada para descargar archivos en download_root.
	"""
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

def espera_click(driver, xpath: str, timeout: int = 10, scroll: bool = True) -> bool:
	try:
		wait = WebDriverWait(driver, timeout)
		elemento = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
		if scroll:
			driver.execute_script(
				"arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
				elemento,
			)
			time.sleep(0.5)
		elemento.click()
		return True
	except Exception as e:
		print(f"[ERROR] No se pudo clickear el xpath: {xpath} [ERROR] \n\n ")
		return False

def _guardar_screenshot(driver, org_code: str, sufijo: str):
	screenshots_dir = Path("screenshots")
	screenshots_dir.mkdir(exist_ok=True)
	filename = screenshots_dir / f"{org_code}_{sufijo}.png"
	driver.save_screenshot(str(filename))
	print(f"[DEBUG] Screenshot guardado: {filename}")
