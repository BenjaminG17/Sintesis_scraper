from .config import load_settings, load_actions



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

    orgs= obtener_lista_municipios(settings)

    print("=== SETTINGS ===")
    print(f"base_url   : {settings.get('base_url')}")
    print(f"org_start  : {settings.get('org_start')}")
    print(f"org_end    : {settings.get('org_end')}")
    print(f"start_year : {settings.get('start_year')}")
    print(f"months     : {settings.get('months')}")
    print(f"orgs (modo actual): {orgs}")

    print("\n=== ACTIONS ===")
    modules = actions.get("modules", [])
    print(f"módulos definidos: {len(modules)}")
    if modules:
        print(f"primer módulo id : {modules[0].get('id')}")
        print(f"url_pattern      : {modules[0].get('url_pattern')}")


if __name__ == "__main__":
    main()