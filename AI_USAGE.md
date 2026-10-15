# Uso de inteligencia artificial

## Uso 1
- Herramienta: Claude Code (Claude Opus)
- Para qué se usó: analizar RETO.md y RUBRICA.md, planear el reparto del trabajo entre los dos integrantes y preparar el repositorio Git
- Prompt principal (resumido): "ayúdame a hacer el reto según las reglas, es en parejas y debe haber commits de los dos en GitHub"
- Qué produjo: un plan con el reparto de commits por integrante, el diseño del gateway y la inicialización del repositorio
- Qué modificó o corrigió el equipo: el repositorio Git que se detectaba era la carpeta personal completa del usuario y no la del kit; antes del primer commit creamos un repositorio nuevo solo en la carpeta del kit, para no subir archivos personales

## Uso 2
- Herramienta: Claude Code (Claude Opus)
- Para qué se usó: construir el adapter legacy y el gateway FastAPI con el modelo canónico, los tokens por consumidor y la auditoría
- Prompt principal (resumido): "implementa el gateway del contrato con adapter, modelo canónico, autenticación por token y auditoría enmascarada"
- Qué produjo: el código de src/adapter y src/app y el servicio gateway en docker-compose.yml
- Qué modificó o corrigió el equipo: comprobamos con las huellas de .validator.json que nombre, estado y empresa coincidieran, y ejecutamos scripts/schema-change.sh para confirmar que las respuestas eran idénticas antes y después del cambio de esquema

## Uso 3
- Herramienta: Claude Code (Claude Opus)
- Para qué se usó: implementar los retiros idempotentes por requestId y la cola de retiros aceptados mientras la base legacy está caída
- Prompt principal (resumido): "el POST de retiros no puede duplicar ni perder retiros cuando se detiene legacy-db"
- Qué produjo: el almacén SQLite del gateway, el worker que reintenta la cola y la respuesta 503 LEGACY_UNAVAILABLE
- Qué modificó o corrigió el equipo: al detener legacy-db medimos que el 503 tardaba unos 4 segundos, por encima del límite de 3; la causa era la resolución DNS del contenedor detenido, así que se resuelve el host con tiempo límite y se conecta por IP, y ahora responde en menos de 1 segundo

## Uso 4
- Herramienta: Claude Code (Claude Opus)
- Para qué se usó: redactar el README con las once secciones obligatorias y revisarlo con ./validator entregables
- Prompt principal (resumido): "llena el README según la plantilla y verifica que pase el validador"
- Qué produjo: el README con configuración, arquitectura, uso, pruebas y enlaces a la documentación
- Qué modificó o corrigió el equipo: el validador no encontraba las rutas en la sección Uso porque tomaba como títulos los comentarios con # dentro del bloque de código; reescribimos la sección como una lista con un ejemplo por ruta
