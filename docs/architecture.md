# Arquitectura

## Contexto

La Caja de Compensación opera sobre una base legacy que se volvió el punto de integración de todo. Educación y los reportes nocturnos la leen directamente, y Subsidios escribe retiros con un procedimiento que no es idempotente. Un cambio de columna rompe varias aplicaciones, y la dirección no acepta una migración Big Bang. La política es que ninguna aplicación nueva se conecte directamente a la base. Por eso se construye una capa de transición que permite modernizar dominio por dominio sin apagar el negocio y con retorno posible.

## Componentes

- **legacy-db:** PostgreSQL con las tablas heredadas y el procedimiento de retiro. Es la fuente de verdad durante la transición.
- **gateway:** API REST en el puerto 8082. Autentica con un token por consumidor (portal, subsidios, móvil), aplica permisos, audita cada petición en `logs/audit.log` con el documento enmascarado y entrega errores con formato uniforme.
- **adapter:** módulo dentro de `src/` que es el único que conoce tablas, columnas, códigos y el procedimiento legacy. Traduce entre el esquema heredado y el modelo canónico.
- **Almacén propio del gateway:** guarda las claves de idempotencia (`requestId`) y la cola persistente de retiros aceptados mientras la base está caída. Un worker los aplica al recuperarse la base, una sola vez.
- **portal-client, subsidios-app y la app móvil:** consumen el gateway por HTTP. Subsidios conserva además el camino directo a `sp_registrar_retiro` para el rollback.
- **educacion-app:** sin cambios, lee la base y comprueba que los retiros hechos por el gateway quedan visibles.
- **tests:** servicio con perfil `test` que prueba la API en funcionamiento y deja el reporte JUnit en `test-results/`.

## Modelo canónico

El gateway expone un vocabulario independiente del esquema heredado. El afiliado tiene `document`, `fullName`, `status` y `company` con `id` y `name`. El beneficiario tiene `document`, `fullName` y `relationship`. La empresa tiene `id`, `name` y `activeMembers`. Los códigos de una letra se traducen en el adapter: `A`, `R` y `S` pasan a `ACTIVE`, `RETIRED` y `SUSPENDED`, y los códigos de parentesco pasan a nombres legibles. El nombre completo se arma con las partes presentes, porque segundos nombres y apellidos pueden ser nulos. Ningún consumidor ve nombres de tablas ni de columnas.

## Cambio de esquema

El DBA renombra la tabla maestra de afiliados a `PERSON_MASTER`, y las columnas de documento y estado a `DOCUMENT_NUMBER` y `STATUS_CODE`, y actualiza el procedimiento de retiro. El adapter detecta el esquema vigente al consultar la estructura de la base y usa el nombre que exista, de modo que antes y después del cambio las respuestas del gateway son idénticas. Otras columnas, como las de beneficiarios y la bitácora, conservan su nombre. Solo el adapter cambia, y el portal, los contratos y el modelo canónico quedan intactos.

## Alternativas descartadas

- **Migración Big Bang a una base nueva:** descartada porque obliga a apagar el negocio, mover todas las aplicaciones a la vez y no ofrece un camino de retorno si algo falla.
- **Que cada aplicación nueva consulte la base directamente:** descartada porque repite el acoplamiento actual, cualquier cambio de esquema volvería a romper a varios consumidores, y viola la política de arquitectura.
- **Vistas de compatibilidad en la base con los nombres viejos:** descartada porque oculta el cambio pero deja la base como punto de integración, y exigiría que el DBA mantenga las vistas indefinidamente.
- **Modificar Educación para que use el gateway:** descartada porque Educación no puede modificarse, y el reto exige que siga funcionando sin cambios contra el legacy.
