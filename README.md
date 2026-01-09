# 🕸️ Scraper Portal de Transparencia Municipal 

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Licencia](https://img.shields.io/badge/Licencia-MIT-green.svg)](LICENSE)
[![Estado](https://img.shields.io/badge/Estado-Desarrollo_Activo-yellow)](https://github.com/BenjaminG17/Sintesis_scraper)

Un scraper automatizado y robusto desarrollado en Python para la extracción sistemática de datos de personal (Contrata y Planta) del Portal de Transparencia de todas las municipalidades de Chile (MU001 a MU345), desde 2018 hasta la fecha.

> **Nota del desarrollador:** Este proyecto es parte de una tesis universitaria y se encuentra en activo desarrollo. Su arquitectura está diseñada para ser modular y escalable.

## ✨ Características Principales

*   **Cobertura Completa:** Recorre automáticamente los 345 municipios disponibles en el portal (MU001 - MU345).
*   **Extracción Dual:** Descarga archivos CSV para ambos tipos de personal: **CONTRATA** y **PLANTA**.
*   **Rango Temporal Completo:** Obtiene datos desde enero de 2018 hasta el mes y año actual de forma automatizada.
*   **Organización Inteligente:** Guarda los archivos descargados en una estructura de carpetas clara: `data/{codigo_municipio}/{tipo_personal}/`.
*   **Configuración Centralizada:** Gestión sencilla de parámetros mediante archivos JSON en la carpeta `configs/`.
*   **Robustez:** Implementa manejo de errores, reintentos y logs detallados para procesamientos de larga duración.

## 📁 Estructura del Proyecto
```markdown
SINTESIS_SCRAPER/
│
├── 📁 logs/                            # Logs de ejecución del sistema
│
├── 📁 src/                             # Código fuente principal
│   │
│   ├── main.py                         # 🎯 Punto de entrada principal
│   ├── scraper.py                      # 🔍 Lógica de scraping y descarga
│   ├── driver_builder.py               # 🌐 Configuración de navegador Selenium
│   │
│   └── 📁 utils/                       # 🛠️  Módulos de utilidad
│       └── (manejo de archivos)
│
├── 📁 configs/                         # ⚙️  Configuraciones del sistema
│   │
│   ├── actions_transparencia.json      # 🤖 Secuencias de automatización
│   └── settings.json                   # 🏙️  Metadatos de municipios
│
├── 📁 data/                            # 💾 Datos extraídos (generado)
│   │
│   └── 📁 MU001/                       # 📍 Ejemplo: Municipio 001
│       │
│       ├── 📁 CONTRATA/                # 👥 Personal contratado
│       │   │
│       │   └── 📁 AÑO_X/               # 📅 Ejemplo: Año 2023
│       │       │
│       │       └── 📄 mes_01.csv
│       │       └── 📄 mes_02.csv
│       │       └── ...                 # 📊 Archivos CSV mensuales
│       │
│       └── 📁 PLANTA/                  # 👥 Personal de planta
│           │
│           └── 📁 AÑO_X/               # 📅 Ejemplo: Año 2023
│               │
│               └── 📄 mes_01.csv
│               └── 📄 mes_02.csv
│               └── ...                  # 📊 Archivos CSV mensuales
│
├── 📄 .env.example                     # 🔐 Plantilla de variables de entorno
├── 📄 requirements.txt                 # 📦 Dependencias de Python
└── 📄 README.md                        # 📚 Documentación del proyecto
```

## 🚀 Comenzando

### Prerrequisitos

*   **Python 3.8 o superior.**
*   **Google Chrome** instalado en el sistema.
*   **ChromeDriver** compatible con tu versión de Chrome (el script puede gestionarlo).

El flujo principal está controlado por el archivo `src/main.py`. Puedes ejecutar el scraper para todos los municipios o para uno específico.

**Ejecución completa (extrae datos de todos los municipios):**
```bash
python src/main.py
```
En la carpeta `configs/setting.json` están todos los parámetros a modificar

#### Ejecución para un municipio específico (ej: MU322 - Valparaíso):
```bash
"orgs": [
    "MU322"
  ]
```

#### Ejecución para un rango de años especificos
```bash
"start_year": 2020 # Año inicial     
"end_year": 2025 # Año final
```

### ¿Qué hace el script?
1. Lee la configuración desde configs/.
2. Inicializa un navegador Chrome controlado por Selenium.
3. Navega al portal de transparencia del municipio correspondiente.
4. Itera sobre los meses y años configurados.
5. Para cada período, selecciona el tipo de personal (CONTRATA/PLANTA) y descarga el CSV.
6. Guarda el archivo en la carpeta data/ correspondiente.
7. Genera logs de progreso y errores en la consola y/o archivos.

### 🛠️ Stack Tecnológico
- Lenguaje: Python 
- Automatización Web: Selenium WebDriver
- Manejo de Navegador: ChromeDriver, WebDriver Manager
- Manejo de Datos/Archivos: JSON, CSV, Pandas (posible uso futuro)
- Utilidades: Python-dotenv (variables de entorno), Logging

### 📄 Licencia
- Este proyecto esta distribuido bajo la Licencia MIT. Consulta el archivo LICENSE para más información.

### 👤 Autor & Contacto
Benjamín González – @BenjaminG17
- Si este proyecto es útil para tu investigación o trabajo, ¡considera darle una estrella ⭐ en GitHub!