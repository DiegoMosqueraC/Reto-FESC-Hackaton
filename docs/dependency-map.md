# Mapa de dependencias del legacy

Quién lee y quién escribe en la base legacy hoy, según `docs/procesos.md`, `docs/modelo-legacy.md` y el código de `services/`. Una fila por aplicación y tabla.

| Aplicación | Tabla | Operación | Criticidad |
|---|---|---|---|
| Educación | AFI_MAE | Lectura | Alta |
| Educación | EMPRESA | Lectura | Media |
| Subsidios | AFI_MAE | Escritura | Alta |
| Subsidios | LOGMOV | Escritura | Alta |
| Reportes | AFI_MAE | Lectura | Media |
| Reportes | LOGMOV | Lectura | Media |

## Criterio de criticidad

- **Alta:** si falla o cambia, se detiene un proceso de negocio en línea. Educación verifica la afiliación antes de matricular, y Subsidios deja el estado del afiliado y la bitácora de retiros. Un retiro duplicado o perdido tiene consecuencias económicas (incidentes de 2021 y 2023).
- **Media:** el impacto es de consulta o de lote. Los reportes nocturnos pueden repetirse al día siguiente, y los datos de empresa en Educación solo complementan la respuesta.

## Aplicaciones sin acceso directo

- **Portal de servicios:** solo habla HTTP con `GATEWAY_URL`. No toca ninguna tabla.
- **App móvil:** consume la API del gateway con permisos de solo lectura. No toca ninguna tabla.
- **Gateway y adapter:** son la única capa nueva con acceso a la base. No se listan porque reemplazan los accesos directos en lugar de agregar dependencias.
