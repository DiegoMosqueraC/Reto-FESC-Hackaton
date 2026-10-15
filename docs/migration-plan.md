# Plan de migración por dominio

Migración incremental, dominio por dominio, sin Big Bang. Cada dominio pasa por `LEGACY → DUAL → MODERN`:

- **LEGACY:** los consumidores usan el camino original. El gateway no es obligatorio para ese dominio.
- **DUAL:** el gateway atiende al dominio y el legacy sigue siendo la fuente de verdad. El camino legacy se mantiene vivo para poder volver.
- **MODERN:** el gateway es la única vía y el dominio ya no depende del esquema heredado.

| Dominio | Estado | Criterio para avanzar | Rollback |
|---|---|---|---|
| Afiliaciones | DUAL | 7 días sin diferencias entre gateway y legacy y 0 errores 5xx no explicados por caída de la base | ./rollback.sh affiliations |
| Retiros | LEGACY | 0 retiros perdidos o duplicados en 14 días de operación por el gateway y 100 % de los reintentos con el mismo requestId resueltos sin duplicar | volver Subsidios a sp_registrar_retiro con el modo legacy |
| Empresas | LEGACY | 7 días con activeMembers igual al conteo de los reportes nocturnos en el 100 % de las empresas | apuntar de nuevo el portal a la consulta directa del legacy y retirar la ruta del gateway |
| Aportes | LEGACY | 2 cierres mensuales consecutivos con totales iguales entre gateway y legacy | mantener la lectura directa del legacy para los reportes y desactivar la ruta del gateway |

Siguiente dominio: Retiros

## Notas

- **Afiliaciones** cubre la consulta de afiliados y beneficiarios por el gateway. Además cubre el registro del retiro desde Subsidios, que pasa por el gateway y termina en `sp_registrar_retiro`, de modo que Educación y los reportes lo siguen viendo sin cambios.
- **Retiros** es el reemplazo del procedimiento y de la bitácora heredados por un almacén propio. Hasta que ese criterio se cumpla, el legacy sigue siendo la fuente de verdad del retiro.
- El estado de **Afiliaciones** que devuelve `GET /api/v1/migration/status` es el que figura en esta tabla. `./rollback.sh affiliations` lo devuelve a `LEGACY` en menos de 3 minutos y Subsidios vuelve al camino directo de `sp_registrar_retiro`.
- Un dominio solo avanza si se cumple su criterio completo. Si durante la ventana aparece una diferencia o un retiro perdido, el contador se reinicia y se ejecuta el rollback de ese dominio.
