# Picks — contexto

Userbot de Telegram (Telethon, con la cuenta del usuario) que corre en GitHub Actions cada 5 min y reenvía a "Mensajes guardados" solo las apuestas gratuitas de canales de tipsters. El usuario habla español.

## Decisiones tomadas
- GitHub Actions (repo público, minutos ilimitados) en vez de servidor. El cron real salta cada 2–4 h, así que cada job se queda conectado 5h40m (`DURACION`) revisando cada minuto, y el cron horario deja otro en cola que lo releva. Si aun así falla, migrar a Oracle Cloud Always Free con systemd.
- Notificaciones: lo que reenvía la cuenta del usuario no le suena. Un bot (`BOT_TOKEN`, admin del canal DESTINO) reenvía desde el canal al chat del usuario con el bot.
- Claude (`MODELO = "sonnet"`) recibe por canal 5 mensajes de contexto y los nuevos agrupados (`agrupar`: álbumes y fotos seguidas ≤2 min). Espera 45 s si el canal aún está publicando.
- Estado (último ID por canal) en `actions/cache`, no en commits.
- Clasificación: `claude -p --model haiku` con la suscripción del usuario (`CLAUDE_CODE_OAUTH_TOKEN`), un único lote por ejecución. Si falla, reglas regex `SI` + `es_apuesta()` en `picks.py`.
- `CANALES_FOTO`: canales donde la apuesta es solo una foto (KrlosTM, el de Zverev): foto + texto ≤60 chars sin ✅❌🔴.

## Canales analizados (formato de sus picks)
SLAMTIPS ("📈 Cuota 1,50"), Pensador Apuestas ("¡Nueva Apuesta!" + link), JJ ("💰CUOTA 1.67"), Pensador Challenger/MMA/ATP/Baloncesto ("📈 @1.61", "Pick N"), Pensador WTA FREE ("Pick 18 / Stake 0.50"), PickHub ("s3 https://..."), canal Zverev (fotos), KrlosTM (foto sin texto), LBTENNIS ("🔔 PREPARTIDO !!"), Pensador Fútbol Europeo ("Stake 1" sola), Pensador Bot ("Pick 27 - 08/2026", casi sin picks gratis desde sept.), Tercera Apuestas ("…Stake 1", "Cuota 23", "crear apuesta aquí").

## Reglas al cambiar el filtro
- Añadir los ejemplos nuevos a `test_filtro.py` y que `python3 test_filtro.py` diga `ok`.
- Resultados (✅❌), programación, promociones VIP y avisos ("Pick en 2'") NO deben pasar.

## Estado
En marcha desde 2026-10-16: repo janpc/picks, 6 secretos puestos, workflow ejecutándose. CANALES = 15 canales gratuitos; CANALES_FOTO = AleixTenis (el de Zverev, -1001342757110) y KrlosTM (-1001093062692). Destino: canal privado cuyo nombre está en el secreto DESTINO (vacío = Mensajes guardados). Claude descarga y mira las fotos (`--allowedTools Read`). Token OAuth arreglado el 2026-10-16 (estaba partido en 2 líneas; el script ahora quita espacios).
