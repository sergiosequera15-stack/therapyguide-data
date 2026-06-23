# Política de publicación de mapas microbiológicos anuales

Esta política diferencia los artefactos temporales de revisión de los mapas microbiológicos finales publicados por DATA.

## 1. Artefactos temporales

Los artefactos generados por GitHub Actions, como:

- `preconsolidation_enterobacterias_draft_2025.json`
- `consolidated_enterobacterias_candidate_2025.json`

son herramientas de trabajo. Sirven para auditar, revisar y validar el proceso, pero no son la fuente estable que debe consultar la APP.

Estos artefactos pueden tener retención limitada en GitHub Actions y no deben depender de disponibilidad permanente.

## 2. Mapa final revisado

Una vez revisado manualmente, el mapa final debe convertirse en un archivo JSON permanente, versionado por año y commiteado en DATA.

Ejemplo de ruta prevista:

```text
docs/microbiology/published/huvn_enterobacterias_2025.json
```

Ese archivo final:

- debe estar validado por CI;
- debe estar referenciado desde los manifiestos DATA;
- debe poder ser consultado por la APP;
- debe conservar trazabilidad a la fuente y a la revisión manual;
- debe permanecer disponible mientras el año/fuente siga vigente.

## 3. Vigencia

Los mapas microbiológicos son anuales. Si la fuente no cambia durante el año, el mapa publicado no debe regenerarse en cada ejecución de CI.

Solo debe sustituirse o generarse uno nuevo cuando ocurra al menos una de estas situaciones:

1. publicación de una nueva fuente anual;
2. corrección documentada de la fuente;
3. corrección manual documentada tras auditoría;
4. cambio estructural aprobado del formato del dataset.

## 4. Consumo por APP

La APP no debe consumir artefactos temporales ni ficheros generados efímeramente por CI.

La APP solo debe consumir mapas microbiológicos desde rutas permanentes publicadas en DATA y expuestas por manifiestos.

## 5. Seguridad clínica

La publicación como mapa consultable no implica automáticamente recomendación terapéutica.

El dataset debe mantener metadatos explícitos sobre:

- alcance (`scope`);
- año (`dataYear`);
- fuente;
- estado de revisión;
- limitaciones por bajo número de aislamientos;
- si permite o no soporte a decisión clínica.

Por defecto, salvo validación editorial explícita posterior, los mapas publicados deben seguir evitando:

- ranking automático de antibióticos;
- recomendaciones terapéuticas;
- extrapolación a centros o servicios no cubiertos;
- fallback desde ámbitos específicos a HUVN global.

## 6. Promoción manual controlada

La promoción de una candidata temporal a mapa anual permanente debe hacerse mediante script manual, no como efecto automático de CI.

Script previsto:

```text
python tools/promote_enterobacteria_candidate.py \
  --candidate docs/microbiology/consolidated_enterobacterias_candidate_2025.json \
  --output docs/microbiology/published/huvn_enterobacterias_2025.json \
  --reviewer "NOMBRE_REVISOR" \
  --reviewed-at YYYY-MM-DD \
  --accept-low-count-warnings \
  --approve-publication
```

Si existen conflictos excluidos en la candidata, la promoción debe requerir además aceptación explícita documentada:

```text
--accept-excluded-conflicts
```

El script debe fallar si:

- no se aporta revisor;
- no se aporta fecha de revisión;
- no se usa `--approve-publication`;
- existen grupos de bajo recuento y no se acepta su advertencia;
- existen conflictos excluidos y no se aceptan explícitamente;
- ya existe un mapa publicado y no se usa `--overwrite` para una corrección documentada.

## 7. Publicación en manifiestos

Crear el archivo permanente no basta para que la APP lo consuma.

Después de generar y revisar el mapa permanente, debe realizarse otro cambio controlado para:

1. validar el archivo publicado;
2. añadirlo a los manifiestos DATA;
3. mantener bloqueado el uso como recomendación terapéutica;
4. asegurar que la APP solo lo trata como mapa anual de consulta.
