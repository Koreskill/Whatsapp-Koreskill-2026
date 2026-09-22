# Reglas de desarrollo

Leer este archivo completo antes de modificar el repositorio.

## Principios obligatorios

- Mantener el producto, el código y el despliegue simples.
- Usar Python, Django, PostgreSQL y Django Templates.
- Usar HTMX o JavaScript vanilla solo cuando aporten valor concreto.
- No usar Node.js como backend, SPA, React, Vue, Angular, Next.js, NestJS, Kubernetes ni microservicios innecesarios.
- Preferir funcionalidad nativa de Django antes de agregar dependencias.
- No reemplazar funcionalidad existente que ya funciona sin una razón concreta.
- No editar archivos directamente en producción. Todo cambio fluye de local a Git, GitHub, Dokploy y el VPS.
- No guardar ni exponer secretos, tokens, contraseñas o claves en código, commits, logs o respuestas.
- Configurar secretos y servicios mediante variables de entorno.

## Arquitectura

- `users`: autenticación y, solo cuando sea necesario, datos de usuarios.
- `crm`: leads, pipeline, requisitos inmobiliarios, tareas, notas y actividad comercial.
- Zernio es el puente entre Meta (WhatsApp/Instagram/Messenger) y el CRM: el CRM implementa su propia interfaz de chat, que replica las conversaciones que llegan por Zernio (decisión 2026-09-22; reemplaza el plan anterior de usar Chatwoot).
- `crm/messaging.py:deliver_message()` es el único camino para mandar un mensaje saliente (envía por Zernio y recién después persiste). Nada nuevo debe insertar un `Message` saliente por su cuenta: admin, vistas de chat y el agente de IA pasan todos por ahí.
- `WebhookEvent` reclama cada evento de Zernio por su id antes de procesarlo (Zernio entrega at-least-once). `ContactIdentity` (platform, external_id) resuelve el mismo lead entre canales que no comparten teléfono.
- El agente de IA (`crm/agent.py`) ya está integrado, vía OpenAI directo, con doble interruptor: `AgentConfig.enabled` por canal y `Conversation.ai_enabled` por hilo — los dos tienen que estar en `True` para que conteste. Los canales arrancan apagados (migración `0005_seed_agent_configs`); activarlos es una decisión manual desde el admin, después de revisar el `system_prompt`.
- `/pipeline/` es el tablero visual de leads por etapa (drag-and-drop en JS vanilla, sin librerías).
- No implementar multitenancy complejo hasta que exista una necesidad real.

## Flujo para cada cambio

1. Inspeccionar todo el repositorio y el estado de Git.
2. Identificar la arquitectura y los archivos relevantes.
3. Explicar brevemente el cambio antes de implementarlo.
4. Mantener el alcance en la fase solicitada.
5. Crear migraciones cuando cambien modelos.
6. Ejecutar `python manage.py makemigrations --check`.
7. Ejecutar `python manage.py migrate`.
8. Ejecutar `python manage.py check`.
9. Ejecutar `python manage.py test`.
10. Informar archivos modificados y cualquier verificación no ejecutada.

## Base de datos y modelos

- Producción usa PostgreSQL mediante `DATABASE_URL`; no hardcodear credenciales.
- SQLite puede usarse como fallback de desarrollo y tests.
- Evitar tablas y campos especulativos.
- Las correcciones humanas deberán prevalecer sobre futuras extracciones de IA.
- La IA nunca debe completar información sin evidencia; usar `null` cuando el dato sea desconocido.

## Seguridad y despliegue

- Mantener activas las protecciones de autenticación, CSRF y validación de Django.
- Los webhooks futuros deberán autenticarse.
- No registrar cuerpos o cabeceras que puedan contener secretos o datos sensibles innecesarios.
- Django escucha en `0.0.0.0:8000`; Traefik/Dokploy administra HTTPS y routing.
- `main` corresponde a producción y `develop` a staging. No experimentar en `main` ni en producción.
