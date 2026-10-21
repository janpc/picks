import os, json, re, time, html, asyncio, subprocess, traceback, urllib.request
from telethon import TelegramClient, utils
from telethon.sessions import StringSession

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
              "(anulada/devuelta). Pon la cuota si el resultado la dice, y las unidades (con signo) si las dice.\n"
              "sueltos: resultados de los NUEVOS (p.ej. un 'Resumen del día' con una línea por apuesta) de apuestas "
              "que NO están en PENDIENTES ni en YA RESUELTOS: una entrada por apuesta (n = el NUEVO donde sale), "
              "sin el total del día. "
              "stake y cuota solo si se dicen.\n"
              "Devuelve SOLO este JSON (números sin comillas, null si no aparecen):\n"
              '{"picks": [{"n": 0, "pick": "Heerenveen +1.5 goles (Heerenveen-Excelsior)", "cuota": 1.5, "stake": 5}], '
              '"resultados": [{"id": 12, "res": "ganada", "cuota": null, "unidades": null}], '
              '"sueltos": [{"n": 3, "pick": "Benjamin Bonzi", "res": "ganada", "unidades": 1.95, "stake": null, "cuota": null}]}'
              '\n\n' + lista)
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


def ganancia(p):
    if p.get("unidades") is not None:  # las dice el tipster (resúmenes)
        return p["unidades"]
    stake = p.get("stake") or 1  # sin stake ni unidades se cuenta como 1u (no entra al yield)
    if p["res"] == "ganada" and p.get("cuota"):
        return stake * (p["cuota"] - 1)
    return -stake if p["res"] == "perdida" else 0


def tabla(hist):
    filas = {}
    for p in hist:
        filas.setdefault(p["nombre"], []).append(p)
    lineas = []
    for nombre, ps in filas.items():
        n = {r: sum(p["res"] == r for p in ps) for r in ("ganada", "perdida", "nula", "sin resultado", None)}
        u = sum(ganancia(p) for p in ps)
        # yield solo con las de stake conocido (en los resúmenes casi nunca se dice)
        conocidas = [p for p in ps if p.get("stake") and (p["res"] == "perdida" or (
            p["res"] == "ganada" and (p.get("cuota") or p.get("unidades") is not None)))]
        apostado = sum(p["stake"] for p in conocidas)
        lineas.append((u, f"<b>{html.escape(nombre)}</b>\n{n['ganada']}✅ {n['perdida']}❌ {n['nula']}➖ · {u:+.2f}u · yield "
                          + (f"{100 * sum(map(ganancia, conocidas)) / apostado:+.0f}%" if apostado else "–")
                          + (f" · {n['sin resultado']} sin resultado publicado" if n["sin resultado"] else "")
                          + (f" · {n[None]} pendientes" if n[None] else "")))
    return "📊 <b>Estadísticas</b>\n\n" + "\n\n".join(l for _, l in sorted(lineas, key=lambda x: -x[0]))


def api(token, metodo, datos, timeout=30):
    """Bot API de Telegram."""
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/{metodo}", json.dumps(datos).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def db(metodo, ruta, datos=None):
    """Supabase (PostgREST): db("GET", "picks?res=is.null")."""
    key = os.environ["SUPABASE_KEY"].strip()
    h = {"apikey": key, "Content-Type": "application/json",
         "Prefer": "return=representation,resolution=merge-duplicates"}
    if key.startswith("eyJ"):  # clave legacy service_role
        h["Authorization"] = "Bearer " + key
    req = urllib.request.Request(os.environ["SUPABASE_URL"].strip().rstrip("/").removesuffix("/rest/v1") + "/rest/v1/" + ruta,
                                 None if datos is None else json.dumps(datos).encode(), h, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            cuerpo = r.read()
    except urllib.error.HTTPError as e:  # que se vea qué dice Supabase, no solo el código
        raise RuntimeError(f"Supabase {e.code} en {ruta.split('?')[0]}: {e.read().decode()[:300]}") from None
    return json.loads(cuerpo) if cuerpo else None


async def publicar(client, stats, resueltos):
    for p in resueltos:
        icono = {"ganada": "✅", "perdida": "❌", "nula": "➖"}[p["res"]]
        await client.send_message(stats, f"{icono} {p['nombre']}: {p['pick']}" + (f" @{p['cuota']}" if p.get("cuota") else "")
                                  + (f" · stake {p['stake']}" if p.get("stake") else "") + f" → {ganancia(p):+.2f}u")
    texto = tabla(db("GET", "picks?select=*"))
    fila = db("GET", "kv?k=eq.tabla")
    try:
        await client.edit_message(stats, int(fila[0]["v"]), texto, parse_mode="html")
    except Exception:  # aún no existe o la han borrado: se crea y se fija
        m = await client.send_message(stats, texto, parse_mode="html")
        db("POST", "kv", {"k": "tabla", "v": str(m.id)})
        await client.pin_message(stats, m, notify=False)


async def ciclo(client, destino, yo, stats):
    canales = db("GET", "canales?select=*")
    pendientes = {p["id"]: p for p in db("GET", "picks?res=is.null&select=*")}
    hace2d = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 2 * 86400))
    recientes = db("GET", f"picks?res=not.is.null&fecha=gt.{hace2d}&select=canal,pick,res")
    grupos, contexto, nuevo = [], {}, {}  # grupos: (canal, [mensajes])
    for c in canales:
        canal = c["id"]
        chat = int(canal) if canal.lstrip("-").isdigit() else canal
        ultimo = c["ultimo_id"]
        if ultimo is None:  # canal nuevo: apunta dónde está y no reenvía lo antiguo
            msgs = await client.get_messages(chat, limit=1)
            db("PATCH", f"canales?id=eq.{canal}", {"ultimo_id": msgs[0].id if msgs else 0})
            continue
        msgs = [m async for m in client.iter_messages(chat, min_id=ultimo, reverse=True)]
        if not msgs or time.time() - msgs[-1].date.timestamp() < 45:  # aún está publicando: espera al próximo ciclo
            continue
        grupos += [(canal, g) for g in agrupar(msgs)]
        contexto[canal] = reversed(await client.get_messages(chat, limit=5, max_id=ultimo + 1))
        nuevo[canal] = msgs[-1].id
    if not grupos:
        return
    nombres = {c["id"]: c["nombre"] for c in canales}
    fotos = {c["id"] for c in canales if c["fotos"]}

    texto, anterior = [], None
    for i, (canal, g) in enumerate(grupos):
        if canal != anterior:
            anterior = canal
            texto.append(f"\n=== Canal: {nombres[canal]} ===\nCONTEXTO:\n"
                         + "\n".join(f"- {linea(m)[:300]}" for m in contexto[canal]) + "\nPENDIENTES:\n"
                         + "\n".join(f"- id {p['id']}: {p['pick']} @{p['cuota']} stake {p['stake']} ({p['fecha'][:10]})"
                                     for p in pendientes.values() if p["canal"] == canal) + "\nYA RESUELTOS:\n"
                         + "\n".join(f"- {p['pick']}: {p['res']}" for p in recientes if p["canal"] == canal)
                         + "\nNUEVOS:")
        partes = []
        for m in g:
            foto = m.photo and await m.download_media(file=os.path.abspath(f"fotos/{m.chat_id}_{m.id}.jpg"))
            partes.append(linea(m, foto))
        texto.append(f"[{i}] " + "\n".join(partes)[:2000])
    try:
        r = clasificar("\n".join(texto))
        elegidos = {p["n"]: p for p in r.get("picks", []) if isinstance(p.get("n"), int)}
        resultados, sueltos = r.get("resultados", []), r.get("sueltos", [])
    except Exception as e:
        print("Claude falló, uso las reglas:", e)
        elegidos = {i: {} for i, (c, g) in enumerate(grupos)
                    if any(es_apuesta(m.raw_text or "", bool(m.photo), c in fotos) for m in g)}
        resultados, sueltos = [], []
    print(time.strftime("%H:%M"), f"{len(grupos)} grupos nuevos, {len(elegidos)} apuestas, {len(resultados)} resultados")

    bot = os.environ.get("BOT_TOKEN", "").strip()
    for i in sorted(elegidos):
        if i < len(grupos):
            canal, g = grupos[i]
            enviados = await client.forward_messages(destino, g)
            if bot and destino != "me":
                try:
                    api(bot, "forwardMessages", {"chat_id": yo, "from_chat_id": utils.get_peer_id(destino),
                                                 "message_ids": [e.id for e in enviados]})
                except Exception as e:
                    print("El bot no pudo avisar:", e)
            p = elegidos[i]
            if p.get("pick"):  # con las reglas no hay detalles: esa apuesta no cuenta en las estadísticas
                db("POST", "picks", {"canal": canal, "nombre": nombres[canal], "pick": p["pick"],
                                     "cuota": p.get("cuota"), "stake": p.get("stake") or 1})

    resueltos = []
    for r in resultados:
        p = pendientes.get(r.get("id"))
        if p and r.get("res") in ("ganada", "perdida", "nula"):
            p.update(res=r["res"], cuota=p["cuota"] or r.get("cuota"), unidades=r.get("unidades"))
            db("PATCH", f"picks?id=eq.{p['id']}", {k: p[k] for k in ("res", "cuota", "unidades")})
            resueltos.append(p)
    canal_de = {i: c for i, (c, g) in enumerate(grupos)}
    unico = next(iter(contexto)) if len(contexto) == 1 else None
    for r in sueltos:  # n = mensaje del resumen, para saber de qué canal es
        canal = canal_de.get(r.get("n")) or unico
        if canal and r.get("pick") and r.get("res") in ("ganada", "perdida", "nula"):
            p = {"canal": canal, "nombre": nombres[canal], "pick": r["pick"], "res": r["res"],
                 "unidades": r.get("unidades"), "stake": r.get("stake"), "cuota": r.get("cuota")}
            db("POST", "picks", p)
            resueltos.append(p)
    # ponytail: a los 4 días sin resultado se da por no publicado; subir si hay picks de largo plazo
    limite = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 4 * 86400))
    db("PATCH", f"picks?res=is.null&fecha=lt.{limite}", {"res": "sin resultado"})
    if resueltos and stats:
        await publicar(client, stats, resueltos)
    for canal, ultimo in nuevo.items():
        db("PATCH", f"canales?id=eq.{canal}", {"ultimo_id": ultimo})


MENU = [[("📊 Estadísticas", "stats"), ("⏳ Pendientes", "pend")], [("📺 Canales", "canales")],
        [("➕ Añadir canal", "add"), ("➖ Quitar canal", "del")]]
VOLVER = [[("⬅️ Menú", "menu")]]


def teclado(filas):
    return {"inline_keyboard": [[{"text": t[:60], "callback_data": d} for t, d in f] for f in filas]}


async def pantalla(client, data, excluir):
    """Lo que muestra el bot al pulsar cada botón: (texto, filas de botones)."""
    if data == "stats":
        ps = db("GET", "picks?select=*")
        return (tabla(ps) if ps else "Aún no hay apuestas."), VOLVER
    if data == "pend":
        ps = db("GET", "picks?res=is.null&order=fecha")
        return ("⏳ <b>Pendientes</b>\n\n" + "\n".join(
            html.escape(f"• {p['nombre']}: {p['pick']} @{p['cuota']} stake {p['stake']}") for p in ps)
            if ps else "Ninguna pendiente."), VOLVER
    if data == "canales":
        cs = db("GET", "canales?order=nombre")
        return "📺 <b>Canales vigilados</b> (📷 = picks en foto)\n\n" + "\n".join(
            f"• {html.escape(c['nombre'])}{' 📷' if c['fotos'] else ''}" for c in cs), VOLVER
    if data == "add":
        vigilados = {c["id"] for c in db("GET", "canales?select=id")}
        cands = [d for d in await client.get_dialogs()
                 if d.is_channel and str(d.id) not in vigilados and d.id not in excluir]
        return "¿Qué canal añado?", [[(d.name, f"a:{d.id}")] for d in cands[:90]] + VOLVER
    if data == "del":
        return "¿Qué canal quito?", [[(c["nombre"], f"q:{c['id']}")] for c in db("GET", "canales?order=nombre")] + VOLVER
    if data.startswith(("a:", "n:")):
        _, canal, *f = data.split(":")
        nombre = next(d.name for d in await client.get_dialogs() if str(d.id) == canal)
        if not f:
            return f"¿<b>{html.escape(nombre)}</b> publica los picks en texto o solo en foto?", \
                [[("📝 Texto", f"n:{canal}:0"), ("📷 Foto", f"n:{canal}:1")]] + VOLVER
        db("POST", "canales", {"id": canal, "nombre": nombre, "fotos": f == ["1"]})
        return f"✅ Añadido <b>{html.escape(nombre)}</b>. Empieza desde su próximo mensaje.", MENU
    if data.startswith("q:"):
        c = db("DELETE", f"canales?id=eq.{data[2:]}")
        return (f"🗑 Quitado <b>{html.escape(c[0]['nombre'])}</b>." if c else "Ya no estaba."), MENU
    return "¿Qué quieres hacer?", MENU


async def comandos(client, bot, yo, offset, excluir, espera=50):
    """Espera hasta `espera` s a que le escribas o pulses un botón; contesta solo a ti. Devuelve el offset nuevo."""
    ups = (await asyncio.to_thread(api, bot, "getUpdates", {"offset": offset, "timeout": espera}, espera + 15))["result"]
    for u in ups:
        offset = u["update_id"] + 1
        q = u.get("callback_query")
        m = q["message"] if q else u.get("message") or {}
        if (q or m).get("from", {}).get("id") != yo:
            continue
        try:
            texto, filas = await pantalla(client, q["data"] if q else "menu", excluir)
        except Exception as e:
            texto, filas = f"Error: {html.escape(str(e))}", MENU
        datos = {"chat_id": yo, "text": texto[:4000], "parse_mode": "HTML", "reply_markup": teclado(filas)}
        if q:
            api(bot, "answerCallbackQuery", {"callback_query_id": q["id"]})
            try:
                api(bot, "editMessageText", {**datos, "message_id": m["message_id"]})
            except Exception:  # mismo texto que ya había: nada que cambiar
                pass
        else:
            api(bot, "sendMessage", datos)
    return offset


async def main():
    fin = time.time() + int(os.environ.get("DURACION", "0"))  # 0 = una sola pasada
    bot = os.environ.get("BOT_TOKEN", "").strip()
    os.makedirs("fotos", exist_ok=True)

    async with TelegramClient(StringSession(os.environ["TG_SESSION"]),
                              int(os.environ["API_ID"]), os.environ["API_HASH"]) as client:
        dialogs = await client.get_dialogs()  # para poder usar IDs numéricos
        destino = os.environ.get("DESTINO", "").strip() or "me"  # nombre del canal, o Mensajes guardados
        if destino != "me":
            destino = next(d.entity for d in dialogs if d.name == destino)
        stats = os.environ.get("STATS", "").strip()  # nombre del grupo/canal de estadísticas (opcional)
        stats = stats and next(d.entity for d in dialogs if d.name == stats)
        yo = (await client.get_me()).id
        offset = 0
        excluir = {utils.get_peer_id(e) for e in (destino, stats) if e and e != "me"}
        if bot:
            api(bot, "setMyCommands", {"commands": [{"command": "start", "description": "Menú"}]})
        while True:
            try:
                await ciclo(client, destino, yo, stats)
            except Exception:
                traceback.print_exc()
            if time.time() > fin:
                break
            try:
                offset = await comandos(client, bot, yo, offset, excluir) if bot else await asyncio.sleep(60) or 0
            except Exception:
                traceback.print_exc()
                await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
