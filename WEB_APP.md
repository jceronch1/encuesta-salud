# Encuesta Salud - aplicación web local

Esta extensión convierte los cuestionarios PDF de factores de riesgo psicosocial intralaboral Forma A en respuestas estructuradas. El flujo está pensado para lotes de hasta 250 PDF por carga y conserva un PDF por persona.

## Qué guarda

- Archivo original en `data/uploads/` con nombre interno aleatorio.
- Nombre original, tamaño, SHA-256, páginas, estado, avisos y método de extracción en `survey_uploads`.
- ID del respondiente y filtros de atención a clientes/jefatura en `surveys`.
- Las preguntas 1 a 123 en `survey_responses`, distinguiendo:
  - `answered`: respuesta detectada.
  - `blank`: faltó una respuesta aplicable.
  - `multiple` o `uncertain`: requiere revisión.
  - `not_applicable`: la pregunta fue omitida por un filtro válido.

La aplicación almacena la posición bruta A-E y su etiqueta. No calcula puntuaciones transformadas ni clasificaciones de riesgo.

## Extracción

1. Para PDFs generados digitalmente como el adjunto, PyMuPDF lee cada `X` y la asocia por coordenadas a su pregunta y columna.
2. Si la capa vectorial está incompleta, se renderiza a 200 DPI mediante el cargador de OMRChecker y se mide la tinta de cada celda.
3. Las marcas ausentes, múltiples o de baja separación quedan en `needs_review`; nunca se reemplazan por una respuesta supuesta.
4. El SHA-256 impide insertar dos veces el mismo PDF.

## Instalación en Windows

Desde PowerShell, en la raíz del repositorio:

```powershell
uv venv .venv --python 3.12
uv pip install --python .venv\Scripts\python.exe -r requirements.web.txt
Copy-Item .env.example .env
```

Edite `.env` con la cuenta MySQL dedicada. No use `root` como cuenta de la aplicación.
Defina también `AUTH_USERNAME` y `AUTH_PASSWORD`: son obligatorios, el servidor no
arranca sin ellos. Protegen con HTTP Basic Auth toda la app (pantalla, API y
`/api/docs`), porque los datos son psicosociales y sensibles.

La base debe existir con `utf8mb4`. Para una instalación nueva, una cuenta administrativa puede crear las tablas una sola vez:

```powershell
$env:DATABASE_ADMIN_URL = "mysql+pymysql://ADMIN:CLAVE@127.0.0.1:3306/encuesta-salud?charset=utf8mb4"
.\.venv\Scripts\python.exe scripts\bootstrap_database.py
Remove-Item Env:DATABASE_ADMIN_URL
```

La cuenta de ejecución requiere únicamente `SELECT`, `INSERT`, `UPDATE` y `DELETE` en ``encuesta-salud``. Las operaciones DDL permanecen separadas.

## Ejecución

```powershell
.\start-web.ps1
```

Abra <http://127.0.0.1:8000>. La documentación interactiva está en <http://127.0.0.1:8000/api/docs>.

La pantalla permite:

- arrastrar uno o muchos PDF;
- seguir los estados `queued`, `processing`, `completed`, `needs_review` y `error`;
- consultar gráficas A-E globales, por los 4 dominios y por las 19 dimensiones de la Forma A;
- buscar por archivo o ID;
- ver las 123 preguntas normalizadas;
- abrir el PDF original, reprocesar y exportar CSV.

Las gráficas son distribuciones descriptivas de respuestas a ítems. Los porcentajes
excluyen los valores `not_applicable` y los pendientes de revisión, que se muestran
por separado. No son una clasificación de riesgo: el sentido de calificación cambia
según la pregunta. La agrupación de dominios y dimensiones sigue la Tabla 23 del
[manual oficial del cuestionario intralaboral Forma A y B](https://www.fondoriesgoslaborales.gov.co/wp-content/uploads/2025/06/2.-Manual-evaluacion-de-factores-de-riesgo-psicosociales-intralaboral-forma-AyB.pdf).

## Verificación con el PDF adjunto

```powershell
.\.venv\Scripts\python.exe scripts\verify_sample.py `
  "C:\Users\usuario\Downloads\Cuestionario_Respuestas_Aleatorias (1).pdf"
```

El control esperado es: ID `653118`, 4 páginas, 114 respuestas aplicables, clientes `Sí`, jefe `No`, sin advertencias.

## API principal

- `GET /api/health`: disponibilidad de MySQL y almacenamiento.
- `POST /api/uploads`: carga multipart de uno o varios PDF.
- `GET /api/uploads`: listado, búsqueda y estados.
- `GET /api/uploads/{id}`: encuesta y respuestas.
- `GET /api/uploads/{id}/file`: PDF original.
- `POST /api/uploads/{id}/reprocess`: reproceso idempotente.
- `GET /api/stats`: contadores del panel.
- `GET /api/analytics`: distribuciones A-E y cobertura global, por dominio y dimensión.
- `GET /api/export.csv`: exportación completa; `value_format=codes` cambia etiquetas por A-E.

## Privacidad y operación

- `.env`, `data/`, temporales y la base no se incluyen en Git.
- Toda la app exige HTTP Basic Auth (`AUTH_USERNAME`/`AUTH_PASSWORD`); sin credenciales validas no se ve ni la pantalla ni la API.
- El ID se almacena como texto para conservar ceros iniciales.
- El servidor escucha en `127.0.0.1` por defecto.
- Haga copias de seguridad coordinadas de MySQL y `data/uploads/`; los metadatos contienen la ruta del PDF.
- El contenido del cuestionario y su aplicación profesional pueden estar sujetos a reglas distintas de la licencia MIT de OMRChecker.
