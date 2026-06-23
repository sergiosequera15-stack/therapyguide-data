# Contrato futuro para importación de CSV microbiológico

Este documento define cómo debe integrarse un CSV oficial de microbiología si se obtiene en el futuro.

## Regla principal

La APP no debe consumir nunca el CSV directamente.

El flujo obligatorio será:

```text
CSV oficial
  -> importador/normalizador DATA
  -> JSON canónico DATA
  -> validadores DATA
  -> revisión manual
  -> publicación controlada en manifiestos
  -> consumo por APP
```

## Motivo

Un CSV es una fuente de entrada, no un contrato estable para la APP. Puede cambiar el separador, la codificación, los nombres de columnas, las unidades, los textos de microorganismos, los códigos de antibióticos o el alcance asistencial.

La APP debe depender solo de JSON canónico publicado por DATA.

## Requisitos mínimos del importador

Cualquier importador desde CSV deberá:

- registrar el fichero fuente y su fecha de obtención;
- validar columnas obligatorias antes de generar JSON;
- normalizar microorganismos, antibióticos, año y alcance;
- conservar el valor original relevante cuando haya transformación;
- rechazar porcentajes fuera de rango;
- detectar duplicados y conflictos;
- separar claramente datos HUVN globales de datos por centro, hospital, servicio o pediatría;
- impedir fallback automático desde un alcance específico a HUVN global;
- generar salida con `manualReviewStatus: "pending"` hasta revisión explícita;
- mantener `clinicalUseAllowed: false`, `interactiveUseAllowed: false` y `therapeuticRecommendationAllowed: false` en cualquier dataset no revisado.

## Modelo canónico esperado

Los datos importados desde CSV deberán transformarse a registros JSON equivalentes a este contrato mínimo:

```json
{
  "scope": "huvn",
  "year": 2025,
  "microorganism": "Escherichia coli",
  "isolatesTested": 123,
  "antibiotic": "CIP",
  "susceptibilityPercent": 78.4,
  "source": {
    "type": "csv",
    "file": "source_file.csv"
  },
  "manualReviewStatus": "pending"
}
```

## Promoción a dataset consultable

Un dataset generado desde CSV solo podrá declararse consultable por APP cuando:

1. el importador esté versionado;
2. los validadores pasen en CI;
3. los recuentos y conflictos estén auditados;
4. el alcance esté explícitamente definido;
5. no exista fallback no autorizado;
6. haya revisión manual documentada;
7. el manifiesto DATA lo publique explícitamente.

Hasta entonces, el resultado debe tratarse como borrador técnico no clínico.
