# Picks

Lee tus canales de Telegram cada 5 minutos (GitHub Actions) y te reenvía solo las apuestas gratuitas a "Mensajes guardados".
Claude decide qué es apuesta; si falla, se usan las reglas de `picks.py`.

## Puesta en marcha

1. **Credenciales de Telegram**: entra en https://my.telegram.org → API development tools → apunta `api_id` y `api_hash`.
2. **Sesión y lista de canales**: `python3 crear_sesion.py`. Copia la cadena larga final (TG_SESSION) y los IDs de los canales que quieras.
3. **Token de Claude**: `npm install -g @anthropic-ai/claude-code && claude setup-token` → copia el token.
4. **Secretos** (repo → Settings → Secrets and variables → Actions → New repository secret):

   | Secreto | Valor |
   |---|---|
   | `API_ID` | el api_id |
   | `API_HASH` | el api_hash |
   | `TG_SESSION` | la cadena del paso 2 |
   | `CANALES` | IDs separados por comas: `-1001234,-1005678,...` |
   | `CANALES_FOTO` | de esos, los que publican la apuesta solo en foto (ej. KrlosTM) |
   | `CLAUDE_CODE_OAUTH_TOKEN` | el token del paso 3 |

5. **Probar**: pestaña Actions → picks → Run workflow. La 1ª vez solo apunta dónde está cada canal; desde la 2ª reenvía.
6. **Silenciar** los canales originales en Telegram y activar notificaciones solo de Mensajes guardados (o del canal de `DESTINO`).

## Mantenimiento

- Si cambias las reglas: `python3 test_filtro.py` debe decir `ok`.
- GitHub pausa el cron tras 60 días sin commits: te avisa por email, se reactiva con un clic.
- Retraso normal: 5–15 min. Las apuestas en directo pueden llegar tarde.
