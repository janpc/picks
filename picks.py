import os, json, re, time, asyncio, subprocess, traceback, urllib.request
from telethon import TelegramClient, utils
from telethon.sessions import StringSession

STATE = "state.json"
MODELO = "sonnet"  # ponytail: sonnet por las fotos; "haiku" si se agota el límite de la suscripción

# Plan B si Claude falla: reglas por canal
SI = re.compile(r"""
  ^[^\w\n✅❌]*(cuota\s*:?\s*|@\s*)\d+([.,]\d+)?[^\n✅❌]{0,30}$   # 📈 Cuota 1,50 / 📈 @2.91 / 📈 @2 (línea corta, sin ✅❌)
| ^\W*pick\s*\d+                                            # Pick 18 / #Pick21
| ^\W*s\d+\b.*https?://                                     # s3 https://betway...
| ^\W*pre(partido)?\b                                       # 🔔 PREPARTIDO !! / 🔔PRE !!
| \b(stake|cuota)\s*\d+([.,]\d+)?\s*$                       # ...Stake 1 / ...Cuota 23 (al final de la línea)
| crear\ apuesta | mi\ apuesta\ para\ hoy                   # Tercera Apuestas
| nueva\ apuesta                                            # ¡Nueva Apuesta!
""", re.I | re.M | re.X)


def es_apuesta(texto, foto=False, canal_fotos=False):
    # ponytail: heurística de fotos, solo si Claude falla (Claude sí mira la imagen)
    if canal_fotos and foto and len(texto) <= 60 and not re.search("[✅❌🔴]", texto):
        return True
    return bool(SI.search(texto))


def clasificar(lista):
    prompt = ("Filtras canales de tipsters de Telegram para un usuario. Abajo, por canal, van los últimos mensajes "
              "ya vistos (CONTEXTO, solo para entender) y los NUEVOS numerados [n]. Un [n] puede ser un álbum o una "
              "ráfaga con varias fotos: decide sobre el conjunto. Abre cada foto con Read y léela entera.\n"
              "picks: los NUEVOS que publican una apuesta gratuita que el usuario pueda copiar YA con lo que se ve: "
              "evento + selección concreta (y normalmente cuota o stake), en texto o en la imagen. Si no se sabe QUÉ "
              "apostar, no es un pick.\n"
              "NO son picks: boletos con la selección tapada, borrosa o recortada (fardar del VIP); boletos ya resueltos "
              "(✅❌, 'ganada', 'cobrado', marcador final) o capturas de ganancias/importes; anuncios de otros canales "
              "o tipsters aunque digan 'gratis'; avisos de que viene un pick ('Pick FREE 21:00h', 'en 2 minutos'); "
              "estadísticas, resúmenes, programación, promociones VIP o de pago, encuestas, memes. Usa el contexto: una "
              "foto tras 'pick de hoy 👇' es la apuesta; una foto tras ✅ o 'otro acierto' es un resultado.\n"
              "resultados: de los PENDIENTES de cada canal, los que los NUEVOS dan por resueltos: ganada, perdida o nula "
              "(anulada/devuelta). Pon la cuota si el resultado la dice.\n"
              "Devuelve SOLO este JSON (cuota y stake numéricos, null si no aparecen):\n"
              '{"picks": [{"n": 0, "pick": "Heerenveen +1.5 goles (Heerenveen-Excelsior)", "cuota": 1.5, "stake": 5}], '
              '"resultados": [{"id": 12, "res": "ganada", "cuota": null}]}\n\n' + lista)
    env = {**os.environ, "CLAUDE_CODE_OAUTH_TOKEN": "".join(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").split())}
    r = subprocess.run(["claude", "-p", prompt, "--model", MODELO, "--allowedTools", "Read"],
                       capture_output=True, text=True, timeout=600, env=env)
    if r.returncode:
        raise RuntimeError(r.stderr or r.stdout)
    return json.loads(r.stdout[r.stdout.index("{"):r.stdout.rindex("}") + 1])


def agrupar(msgs):
    """Junta álbumes y fotos seguidas (≤2 min) en un solo grupo, para analizarlas juntas."""
    grupos = []
    for m in msgs:
        p = grupos[-1][-1] if grupos else None
        if p and ((m.grouped_id and m.grouped_id == p.grouped_id)
                  or (m.photo and p.photo and (m.date - p.date).total_seconds() <= 120)):
            grupos[-1].append(m)
        else:
            grupos.append([m])
    return grupos


def linea(m, foto=None):
    return (m.raw_text or "").strip() + (f" [foto: {foto}]" if foto else " [foto]" if m.photo else "")


def avisar(token, chat, desde, ids):
    """El bot reenvía desde el canal a tu chat con él: así sí suena la notificación."""
    data = json.dumps({"chat_id": chat, "from_chat_id": desde, "message_ids": ids}).encode()
    urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{token}/forwardMessages", data,
                                                  {"Content-Type": "application/json"}), timeout=30)


def ganancia(p):
    if p["res"] == "ganada" and p.get("cuota"):
        return p["stake"] * (p["cuota"] - 1)
    return -p["stake"] if p["res"] == "perdida" else 0


def tabla(hist):
    filas = {}
    for p in hist:
        filas.setdefault(p["nombre"], []).append(p)
    lineas = []
    for nombre, ps in filas.items():
        n = {r: sum(p["res"] == r for p in ps) for r in ("ganada", "perdida", "nula", "sin resultado", None)}
        u = sum(ganancia(p) for p in ps)
        apostado = sum(p["stake"] for p in ps if p["res"] == "perdida" or (p["res"] == "ganada" and p.get("cuota")))
        lineas.append((u, f"<b>{nombre}</b>\n{n['ganada']}✅ {n['perdida']}❌ {n['nula']}➖ · {u:+.2f}u · yield "
                          + (f"{100 * u / apostado:+.0f}%" if apostado else "–")
                          + (f" · {n['sin resultado']} sin resultado publicado" if n["sin resultado"] else "")
                          + (f" · {n[None]} pendientes" if n[None] else "")))
    return "📊 <b>Estadísticas</b>\n\n" + "\n\n".join(l for _, l in sorted(lineas, key=lambda x: -x[0]))


async def publicar(client, stats, state, resueltos):
    for p in resueltos:
        icono = {"ganada": "✅", "perdida": "❌", "nula": "➖"}[p["res"]]
        await client.send_message(stats, f"{icono} {p['nombre']}: {p['pick']} @{p.get('cuota') or '?'} "
                                         f"· stake {p['stake']} → {ganancia(p):+.2f}u")
    texto = tabla(state["_picks"])
    try:
        await client.edit_message(stats, state["_tabla"], texto, parse_mode="html")
    except Exception:  # aún no existe o la han borrado: se crea y se fija
        m = await client.send_message(stats, texto, parse_mode="html")
        state["_tabla"] = m.id
        await client.pin_message(stats, m, notify=False)


async def ciclo(client, canales, fotos, state, nombres, destino, yo, stats):
    hist = state.setdefault("_picks", [])
    grupos, contexto, nuevo = [], {}, {}  # grupos: (canal, [mensajes])
    for canal in canales:
        chat = int(canal) if canal.lstrip("-").isdigit() else canal
        ultimo = state.get(canal)
        if ultimo is None:  # primera vez: apunta dónde está y no reenvía lo antiguo
            msgs = await client.get_messages(chat, limit=1)
            state[canal] = msgs[0].id if msgs else 0
            continue
        msgs = [m async for m in client.iter_messages(chat, min_id=ultimo, reverse=True)]
        if not msgs or time.time() - msgs[-1].date.timestamp() < 45:  # aún está publicando: espera al próximo ciclo
            continue
        grupos += [(canal, g) for g in agrupar(msgs)]
        contexto[canal] = reversed(await client.get_messages(chat, limit=5, max_id=ultimo + 1))
        nuevo[canal] = msgs[-1].id
    if not grupos:
        return

    texto, anterior = [], None
    for i, (canal, g) in enumerate(grupos):
        if canal != anterior:
            anterior = canal
            texto.append(f"\n=== Canal: {nombres.get(canal, canal)} ===\nCONTEXTO:\n"
                         + "\n".join(f"- {linea(m)[:300]}" for m in contexto[canal]) + "\nPENDIENTES:\n"
                         + "\n".join(f"- id {p['id']}: {p['pick']} @{p.get('cuota')} stake {p['stake']} "
                                     f"({time.strftime('%d/%m', time.localtime(p['fecha']))})"
                                     for p in hist if p["canal"] == canal and p["res"] is None) + "\nNUEVOS:")
        partes = []
        for m in g:
            foto = m.photo and await m.download_media(file=os.path.abspath(f"fotos/{m.chat_id}_{m.id}.jpg"))
            partes.append(linea(m, foto))
        texto.append(f"[{i}] " + "\n".join(partes)[:2000])
    try:
        r = clasificar("\n".join(texto))
        elegidos = {p["n"]: p for p in r.get("picks", []) if isinstance(p.get("n"), int)}
        resultados = r.get("resultados", [])
    except Exception as e:
        print("Claude falló, uso las reglas:", e)
        elegidos = {i: {} for i, (c, g) in enumerate(grupos)
                    if any(es_apuesta(m.raw_text or "", bool(m.photo), c in fotos) for m in g)}
        resultados = []
    print(time.strftime("%H:%M"), f"{len(grupos)} grupos nuevos, {len(elegidos)} apuestas, {len(resultados)} resultados")

    bot = os.environ.get("BOT_TOKEN", "").strip()
    for i in sorted(elegidos):
        if i < len(grupos):
            canal, g = grupos[i]
            enviados = await client.forward_messages(destino, g)
            if bot and destino != "me":
                try:
                    avisar(bot, yo, utils.get_peer_id(destino), [e.id for e in enviados])
                except Exception as e:
                    print("El bot no pudo avisar:", e)
            p = elegidos[i]
            if p.get("pick"):  # con las reglas no hay detalles: esa apuesta no cuenta en las estadísticas
                hist.append({"id": len(hist), "canal": canal, "nombre": nombres.get(canal, canal), "pick": p["pick"],
                             "cuota": p.get("cuota"), "stake": p.get("stake") or 1, "fecha": time.time(), "res": None})

    por_id, resueltos = {p["id"]: p for p in hist}, []
    for r in resultados:
        p = por_id.get(r.get("id"))
        if p and p["res"] is None and r.get("res") in ("ganada", "perdida", "nula"):
            p["res"], p["cuota"] = r["res"], p.get("cuota") or r.get("cuota")
            resueltos.append(p)
    for p in hist:  # ponytail: a los 4 días sin resultado se da por no publicado; subir si hay picks de largo plazo
        if p["res"] is None and time.time() - p["fecha"] > 4 * 86400:
            p["res"] = "sin resultado"
    if resueltos and stats:
        await publicar(client, stats, state, resueltos)
    state.update(nuevo)


async def main():
    canales = [c.strip() for c in os.environ["CANALES"].split(",") if c.strip()]
    fotos = {c.strip() for c in os.environ.get("CANALES_FOTO", "").split(",") if c.strip()}
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    fin = time.time() + int(os.environ.get("DURACION", "0"))  # 0 = una sola pasada
    os.makedirs("fotos", exist_ok=True)

    async with TelegramClient(StringSession(os.environ["TG_SESSION"]),
                              int(os.environ["API_ID"]), os.environ["API_HASH"]) as client:
        dialogs = await client.get_dialogs()  # para poder usar IDs numéricos
        nombres = {str(d.id): d.name for d in dialogs}
        destino = os.environ.get("DESTINO", "").strip() or "me"  # nombre del canal, o Mensajes guardados
        if destino != "me":
            destino = next(d.entity for d in dialogs if d.name == destino)
        stats = os.environ.get("STATS", "").strip()  # nombre del grupo/canal de estadísticas (opcional)
        stats = stats and next(d.entity for d in dialogs if d.name == stats)
        yo = (await client.get_me()).id
        while True:
            try:
                await ciclo(client, canales, fotos, state, nombres, destino, yo, stats)
            except Exception:
                traceback.print_exc()
            json.dump(state, open(STATE, "w"))
            if time.time() > fin:
                break
            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
