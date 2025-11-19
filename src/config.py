from pathlib import Path
import json
import os
from dotenv import load_dotenv

# Carpeta raíz del proyecto (donde está la carpeta configs/)
BASE_DIR = Path(__file__).resolve().parent.parent


def load_settings() -> dict:
    """
    Lee configs/settings.json y devuelve un diccionario con la configuración general.
    """
    settings_path = BASE_DIR / "configs" / "settings.json"
    with settings_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_actions() -> dict:
    """
    Lee configs/actions_transparencia.json y devuelve la configuración de módulos/acciones.
    """
    actions_path = BASE_DIR / "configs" / "actions_transparencia.json"
    with actions_path.open("r", encoding="utf-8") as f:
        return json.load(f)

def load_env() -> dict:
    """
    Carga variables desde .env (si existe) y devuelve un diccionario
    con las configuraciones de entorno que usará el scraper.
    """
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    headless_str = os.getenv("HEADLESS", "1")
    headless = headless_str == "1"

    download_root = os.getenv("DOWNLOAD_ROOT", "./data/raw")
    staging_dir = os.getenv("STAGING_DIR", "./data/staging")
    final_dir = os.getenv("FINAL_DIR", "./data/final")

    return {
        "HEADLESS": headless,
        "DOWNLOAD_ROOT": download_root,
        "STAGING_DIR": staging_dir,
        "FINAL_DIR": final_dir,
    }
