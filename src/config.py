from pathlib import Path
import json


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
