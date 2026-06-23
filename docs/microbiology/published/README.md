# Mapas microbiológicos publicados

Esta carpeta contiene mapas microbiológicos permanentes, versionados por año, revisados manualmente y publicados por DATA.

Los archivos de esta carpeta sí pueden ser referenciados por los manifiestos DATA y consumidos por la APP, siempre que sus metadatos lo permitan explícitamente.

## Diferencia frente a artefactos temporales

Los artefactos generados por CI en `docs/microbiology/*.json` durante validación son borradores de trabajo y no deben ser consumidos por la APP.

Los mapas publicados en esta carpeta:

- están commiteados en el repositorio;
- tienen ruta estable;
- tienen vigencia anual;
- permanecen disponibles hasta sustitución por una fuente anual nueva o corrección documentada;
- deben conservar trazabilidad de fuente y revisión.

## Ruta prevista para enterobacterias 2025

```text
published/huvn_enterobacterias_2025.json
```

Este archivo no debe generarse automáticamente en cada ejecución de CI. Debe crearse solo mediante promoción manual controlada tras revisión.
