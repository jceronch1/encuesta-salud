# Sistema de Encuesta de Salud

Aplicación web local para cargar cuestionarios PDF de factores de riesgo psicosocial intralaboral **Forma A**, detectar las respuestas marcadas y almacenarlas de forma estructurada en MySQL.

![Tecnologías del Sistema de Encuesta de Salud](output/infografia-tecnologias-encuesta-salud.png)

## Funciones principales

- Carga individual o por lotes de hasta 250 archivos PDF.
- Lectura de las 123 preguntas mediante texto vectorial u OMR sobre la imagen escaneada.
- Detección de respuestas en blanco, ambiguas o marcadas más de una vez.
- Revisión manual de preguntas dudosas sin inventar respuestas.
- Edición manual del ID cuando no puede leerse automáticamente.
- Eliminación de encuestas cargadas, tengan o no respuestas.
- Prevención de archivos duplicados mediante SHA-256.
- Consulta de estadísticas globales, dominios y dimensiones.
- Exportación de la información a CSV.
- Generación del cuestionario PDF sin respuestas marcadas.

## Tecnologías utilizadas

- **Frontend:** HTML5, CSS3 y JavaScript.
- **Backend:** Python, FastAPI y Uvicorn.
- **Base de datos:** MySQL, SQLAlchemy y PyMySQL.
- **Procesamiento de PDF:** PyMuPDF y OMRChecker.
- **Visión OMR:** OpenCV y NumPy.

## Instalación en Windows

### 1. Requisitos

Antes de comenzar, instale:

- Python 3.12.
- MySQL 8 o una versión compatible.
- Git.

Compruebe las instalaciones desde PowerShell:

```powershell
python --version
mysql --version
git --version
```

### 2. Descargar el Sistema de Encuesta de Salud

```powershell
git clone https://github.com/jceronch1/encuesta-salud.git
Set-Location encuesta-salud
```

### 3. Crear el entorno de Python

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.web.txt
```

El entorno `.venv` mantiene las dependencias del sistema separadas de las demás aplicaciones instaladas en el equipo.

### 4. Preparar MySQL

La aplicación necesita una base llamada `encuesta-salud`. Si todavía no existe, créela desde el cliente de MySQL con una cuenta administrativa:

```sql
CREATE DATABASE `encuesta-salud`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

Use una cuenta exclusiva para la aplicación. En este proyecto el usuario previsto es `sigendin`; su contraseña debe mantenerse únicamente en el archivo local `.env` y nunca debe publicarse en GitHub.

### 5. Configurar la conexión

Copie el archivo de ejemplo:

```powershell
Copy-Item .env.example .env
```

Abra `.env` y complete los datos locales:

```dotenv
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=sigendin
DB_PASSWORD=SU_CONTRASENA_LOCAL
DB_NAME=encuesta-salud

APP_HOST=127.0.0.1
APP_PORT=8000
UPLOAD_DIR=data/uploads
MAX_FILE_SIZE_MB=50
MAX_BATCH_FILES=250
PROCESSING_WORKERS=2
```

El archivo `.env` está excluido de Git para proteger la contraseña.

### 6. Crear las tablas

Ejecute una sola vez el inicializador con una cuenta MySQL que tenga permiso para crear tablas. Sustituya `ADMIN`, `CLAVE` y, si es necesario, el servidor:

```powershell
$env:DATABASE_ADMIN_URL = "mysql+pymysql://ADMIN:CLAVE@127.0.0.1:3306/encuesta-salud?charset=utf8mb4"
& .\.venv\Scripts\python.exe scripts\bootstrap_database.py
Remove-Item Env:DATABASE_ADMIN_URL
```

Después de crear las tablas, el usuario de la aplicación solo necesita permisos `SELECT`, `INSERT`, `UPDATE` y `DELETE` sobre la base `encuesta-salud`.

### 7. Iniciar la aplicación

```powershell
.\start-web.ps1
```

Abra en el navegador:

- Aplicación: <http://127.0.0.1:8000>
- Documentación de la API: <http://127.0.0.1:8000/api/docs>

Para detener el servidor, presione `Ctrl+C` en PowerShell.

## Uso básico

1. Abra la aplicación en el navegador.
2. Arrastre uno o varios cuestionarios PDF al área de carga.
3. Espere a que cada archivo figure como procesado o pendiente de revisión.
4. Abra el detalle para verificar el ID y las respuestas dudosas.
5. Corrija manualmente los campos que el sistema no haya podido reconocer.
6. Consulte las estadísticas o exporte los datos a CSV.

## Almacenamiento y privacidad

- Los PDF se guardan localmente en `data/uploads/`.
- Las respuestas y metadatos se guardan en MySQL.
- `.env`, `data/` y los archivos temporales no se publican en Git.
- El ID se almacena como texto para conservar posibles ceros iniciales.
- Se recomienda respaldar conjuntamente MySQL y `data/uploads/`.
- El servidor escucha solamente en `127.0.0.1` de forma predeterminada.

## Alcance de los resultados

Las gráficas muestran distribuciones descriptivas de respuestas por categoría. No calculan por sí solas una clasificación clínica ni sustituyen la interpretación de un profesional. Las marcas múltiples, ausentes o con baja confianza quedan señaladas para revisión manual.

## Pruebas

Para ejecutar las pruebas propias de la aplicación:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests -q
```

## Documentación adicional

- [Descripción técnica y API](WEB_APP.md)
- [Infografía sobre el proceso de visión OMR](output/infografia-punto-5-vision-omr.png)
- [PDF del cuestionario sin respuestas](output/pdf/Cuestionario_Forma_A_Sin_Respuestas.pdf)

## Créditos y licencia

El motor de reconocimiento parte del proyecto de código abierto [OMRChecker](https://github.com/Udayraj123/OMRChecker). Se conserva la licencia MIT incluida en [LICENSE](LICENSE).
