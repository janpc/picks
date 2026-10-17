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
              "Devuelve SOLO un JSON con los números de los NUEVOS que publican una apuesta gratuita para jugar ahora: "
              "un pick concreto (partido/selección + cuota o stake) o la captura de un boleto aún sin resolver.\n"
              "NO cuentes: boletos ya resueltos (✅❌, 'ganada', 'cobrado', marcador final), capturas de ganancias, "
              "estadísticas o resúmenes, programación, promociones del VIP o de pago, avisos de que viene un pick, "
              "encuestas, memes. Usa el contexto: una foto tras 'pick de hoy 👇' es la apuesta; una foto tras ✅ o "
              "'otro acierto' es un resultado.\n\n" + lista)
    env = {**os.environ, "CLAUDE_CODE_OAUTH_TOKEN": "".join(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").split())}
    r = subprocess.run(["claude", "-p", prompt, "--model", MODELO, "--allowedTools", "Read"],
                       capture_output=True, text=True, timeout=600, env=env)
    if r.returncode:
        raise RuntimeError(r.stderr or r.stdout)
    return {int(i) for i in json.loads(re.search(r"\[[\d,\s]*\]", r.stdout.split("```json")[-1]).group())}


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


async def ciclo(client, canales, fotos, state, nombres, destino, yo):
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
                         + "\n".join(f"- {linea(m)[:300]}" for m in contexto[canal]) + "\nNUEVOS:")
        partes = []
        for m in g:
            foto = m.photo and await m.download_media(file=os.path.abspath(f"fotos/{m.chat_id}_{m.id}.jpg"))
            partes.append(linea(m, foto))
        texto.append(f"[{i}] " + "\n".join(partes)[:2000])
    try:
        elegidos = clasificar("\n".join(texto))
    except Exception as e:
        print("Claude falló, uso las reglas:", e)
        elegidos = {i for i, (c, g) in enumerate(grupos)
                    if any(es_apuesta(m.raw_text or "", bool(m.photo), c in fotos) for m in g)}
    print(time.strftime("%H:%M"), f"{len(grupos)} grupos nuevos, {len(elegidos)} apuestas")

    bot = os.environ.get("BOT_TOKEN", "").strip()
    for i in sorted(elegidos):
        if i < len(grupos):
            enviados = await client.forward_messages(destino, grupos[i][1])
            if bot and destino != "me":
                try:
                    avisar(bot, yo, utils.get_peer_id(destino), [e.id for e in enviados])
                except Exception as e:
                    print("El bot no pudo avisar:", e)
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
        yo = (await client.get_me()).id
        while True:
            try:
                await ciclo(client, canales, fotos, state, nombres, destino, yo)
            except Exception:
                traceback.print_exc()
            json.dump(state, open(STATE, "w"))
            if time.time() > fin:
                break
            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
