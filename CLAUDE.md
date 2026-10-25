# Picks — contexto

Userbot de Telegram (Telethon, con la cuenta del usuario) que corre en GitHub Actions cada 5 min y reenvía a "Mensajes guardados" solo las apuestas gratuitas de canales de tipsters. El usuario habla español.

## Decisiones tomadas
- GitHub Actions en vez de servidor. El repo TIENE que ser público (minutos ilimitados): estuvo privado y el 2026-10-18 se agotaron los 2.000 min gratis ("recent account payments have failed"). El cron real salta cada 2–4 h, así que cada job se queda conectado 5h40m (`DURACION`) revisando cada minuto, y el cron horario deja otro en cola que lo releva. Si aun así falla, migrar a Oracle Cloud Always Free con systemd.
- Notificaciones: lo que reenvía la cuenta del usuario no le suena. Un bot (`BOT_TOKEN`, admin del canal DESTINO) reenvía desde el canal al chat del usuario con el bot.
- Claude (`MODELO = "sonnet"`) recibe por canal 5 mensajes de contexto y los nuevos agrupados (`agrupar`: álbumes y fotos seguidas ≤2 min). Espera 45 s si el canal aún está publicando.
- Datos en Supabase (`schema.sql`, acceso por REST con `db()`): `canales` (id, nombre, fotos, ultimo_id), `picks`, `kv` (id de la tabla fijada). Los secretos CANALES/CANALES_FOTO y la caché ya no se usan.
- Bot con menú de botones (`pantalla()`): estadísticas, pendientes, canales, añadir/quitar canal. Solo responde al usuario. El long-poll de getUpdates (50 s) sustituye al sleep del bucle.
- Clasificación: `claude -p --model haiku` con la suscripción del usuario (`CLAUDE_CODE_OAUTH_TOKEN`), un único lote por ejecución. Si falla, reglas regex `SI` + `es_apuesta()` en `picks.py`.
- `CANALES_FOTO`: canales donde la apuesta es solo una foto (KrlosTM, el de Zverev): foto + texto ≤60 chars sin ✅❌🔴.

- Estadísticas: Claude devuelve `{picks:[{n,pick,cuota,stake}], resultados:[{id,res,cuota}]}`; los picks enviados se guardan en la tabla `picks` y los resultados se emparejan con los PENDIENTES del canal. A los 15 días sin resultado = "sin resultado" (tipsters que esconden fallos). Se publica cada resultado y una tabla fijada (`kv.tabla`) en el grupo del secreto `STATS`. Si Claude falla, esa apuesta no cuenta. Los resúmenes («Resumen del día» con una línea por apuesta) crean picks ya resueltos (`sueltos`, con `unidades` del tipster y stake null); Claude ve YA RESUELTOS de 2 días para no duplicar. El yield solo usa apuestas con stake conocido.

## Canales analizados (formato de sus picks)
SLAMTIPS ("📈 Cuota 1,50"), Pensador Apuestas ("¡Nueva Apuesta!" + link), JJ ("💰CUOTA 1.67"), Pensador Challenger/MMA/ATP/Baloncesto ("📈 @1.61", "Pick N"), Pensador WTA FREE ("Pick 18 / Stake 0.50"), PickHub ("s3 https://..."), canal Zverev (fotos), KrlosTM (foto sin texto), LBTENNIS ("🔔 PREPARTIDO !!"), Pensador Fútbol Europeo ("Stake 1" sola), Pensador Bot ("Pick 27 - 08/2026", casi sin picks gratis desde sept.), Tercera Apuestas ("…Stake 1", "Cuota 23", "crear apuesta aquí").

## Reglas al cambiar el filtro
- Añadir los ejemplos nuevos a `test_filtro.py` y que `python3 test_filtro.py` diga `ok`.
- Resultados (✅❌), programación, promociones VIP y avisos ("Pick en 2'") NO deben pasar.

## Estado
En marcha desde 2026-10-16: repo janpc/picks, 6 secretos puestos, workflow ejecutándose. CANALES = 15 canales gratuitos; CANALES_FOTO = AleixTenis (el de Zverev, -1001342757110) y KrlosTM (-1001093062692). Destino: canal privado cuyo nombre está en el secreto DESTINO (vacío = Mensajes guardados). Claude descarga y mira las fotos (`--allowedTools Read`). Token OAuth arreglado el 2026-10-16 (estaba partido en 2 líneas; el script ahora quita espacios).
