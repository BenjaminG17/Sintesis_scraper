# Scraper Portal de Transparencia Municipal (Tesis)

Este repositorio contiene el proyecto de scraper para descargar automáticamente
todos los archivos CSV de personal a Contrata y Planta desde el Portal de
Transparencia de todas las municipalidades (MU001–MU345), desde el año 2018 hasta la fecha actual.

## Estado del proyecto

Actualmente el repositorio está en fase de preparación y estructura inicial.
El objetivo es mantener un diseño modular, limpio y escalable, que permita:

- Recorrer todos los municipios.
- Descargar todos los CSV por Tipo de Personal (CONTRATA / PLANTA).
- Descargar desde enero 2018 hasta el mes/año actual.
- Guardar los archivos en carpetas organizadas por municipio.

En pasos posteriores se implementará:
- Selenium Driver configurado para descargas.
- Manejo de acciones con JSON 
- Flujo completo de scraping por municipio.