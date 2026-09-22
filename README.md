# CRM inmobiliario

CRM simple para corredores e inmobiliarias. La experiencia prevista es: mensaje → lead → calificación → pipeline → visita → negociación → cierre.

Esta primera fase contiene la base Django, autenticación, modelos del CRM y administración. No incluye todavía OpenAI, Chatwoot ni canales de Meta.

## Stack

- Python 3.12
- Django 5.2 LTS
- PostgreSQL en producción
- Django Templates
- Gunicorn y WhiteNoise
- Docker

## Estructura

```text
config/       Configuración, URLs y entrada WSGI/ASGI
users/        Autenticación (usa el modelo User nativo de Django)
crm/          Lead, PipelineStage, Task y Note
templates/    Templates compartidos y login
```

## Instalación local

Se requiere Python 3.12 y PostgreSQL. Para una prueba rápida local, si se omite `DATABASE_URL`, Django utiliza SQLite.

```bash
python -m venv .venv
```

Activar el entorno en Linux/macOS:

```bash
source .venv/bin/activate
```

En Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Instalar y configurar:

```bash
python -m pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

En PowerShell, reemplazar `cp` por `Copy-Item`. Django no lee `.env` automáticamente: cargar esas variables desde la terminal, el editor o la plataforma. Esto evita una dependencia de configuración adicional.

Abrir `http://127.0.0.1:8000/login/`. Después del ingreso, la primera fase dirige al administrador de Django.

## Variables de entorno

Copiar `.env.example` sin versionar `.env`.

- `DEBUG`: `True` solo en desarrollo.
- `SECRET_KEY`: obligatoria cuando `DEBUG=False`.
- `ALLOWED_HOSTS`: hosts separados por coma.
- `CSRF_TRUSTED_ORIGINS`: URLs HTTPS completas separadas por coma.
- `DATABASE_URL`: por ejemplo `postgresql://usuario:clave@host:5432/base`.
- Las variables de OpenAI y Chatwoot están reservadas para fases futuras y no se usan todavía.

## Verificación

```bash
python manage.py makemigrations --check
python manage.py migrate
python manage.py check
python manage.py test
```

## Docker

Construir la imagen:

```bash
docker build -t crm-inmobiliario .
```

Ejecutarla con un PostgreSQL accesible mediante `DATABASE_URL`:

```bash
docker run --env-file .env -p 8000:8000 crm-inmobiliario
```

El contenedor aplica migraciones, recolecta archivos estáticos e inicia Gunicorn en `0.0.0.0:8000`.

## Deployment con Dokploy

1. Conectar el repositorio GitHub a Dokploy.
2. Crear o vincular una base PostgreSQL.
3. Configurar las variables de `.env.example` como secretos de Dokploy.
4. Usar `DEBUG=False`, una `SECRET_KEY` robusta y el dominio real en `ALLOWED_HOSTS`.
5. Configurar `CSRF_TRUSTED_ORIGINS=https://crm.DOMINIO.com`.
6. Exponer internamente el puerto `8000` y asociar el dominio en Traefik.
7. Desplegar desde Git; nunca editar el contenedor o el VPS manualmente.

## Producción y staging

- `main` → `crm.DOMINIO.com` (producción).
- `develop` → `staging-crm.DOMINIO.com` (staging).
- Cada entorno debe tener su propia base, secretos y dominio.
- Probar migraciones y cambios en staging antes de promoverlos a `main`.

## Backups de PostgreSQL

Configurar en el VPS una tarea programada externa al contenedor Django que ejecute `pg_dump` contra la base de producción. Guardar copias cifradas fuera del VPS, aplicar una política de retención y probar restauraciones periódicamente. No incluir dumps ni credenciales en Git. Dokploy o el proveedor de la base puede administrar la programación; documentar allí la frecuencia y el destino elegidos.

## Administración

El administrador permite ordenar y activar etapas del pipeline, gestionar leads y operar tareas y notas. La migración inicial crea:

1. Nuevo
2. Contactado
3. Calificado
4. Propiedades enviadas
5. Visita
6. Negociación
7. Cerrado
8. Perdido

Los valores iniciales de operación son Compra, Alquiler, Venta y Tasación.
