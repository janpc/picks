import os, json, re, asyncio, subprocess
from telethon import TelegramClient
from telethon.sessions import StringSession

DESTINO = "me"  # Mensajes guardados, o el @ de tu canal privado
STATE = "state.json"

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
    # ponytail: heurística de fotos, si se cuelan capturas que no son apuestas, mirar la imagen con Claude
    if canal_fotos and foto and len(texto) <= 60 and not re.search("[✅❌🔴]", texto):
        return True
    return bool(SI.search(texto))


def clasificar(textos):
    lista = "\n\n".join(f"[{i}] {t[:1500]}" for i, t in enumerate(textos))
    prompt = ("Mensajes de canales de apuestas de Telegram, en orden. Devuelve SOLO un JSON con la lista de "
              "números de los mensajes que publican una apuesta nueva para jugar (pick gratuito). "
              "No cuentes resultados, resúmenes, estadísticas, promociones del VIP ni avisos de que viene un pick. "
              "[foto] = el mensaje lleva una imagen.\n\n" + lista)
    out = subprocess.run(["claude", "-p", prompt, "--model", "haiku"],
                         capture_output=True, text=True, timeout=180, check=True).stdout
    return {int(i) for i in json.loads(re.search(r"\[[\d,\s]*\]", out).group())}


async def main():
    canales = [c.strip() for c in os.environ["CANALES"].split(",") if c.strip()]
    fotos = {c.strip() for c in os.environ.get("CANALES_FOTO", "").split(",") if c.strip()}
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}

    async with TelegramClient(StringSession(os.environ["TG_SESSION"]),
                              int(os.environ["API_ID"]), os.environ["API_HASH"]) as client:
        await client.get_dialogs()  # para poder usar IDs numéricos
        nuevos = []  # (canal, mensaje)
        for canal in canales:
            chat = int(canal) if canal.lstrip("-").isdigit() else canal
            ultimo = state.get(canal)
            if ultimo is None:  # primera vez: apunta dónde está y no reenvía lo antiguo
                msgs = await client.get_messages(chat, limit=1)
                state[canal] = msgs[0].id if msgs else 0
                continue
            async for m in client.iter_messages(chat, min_id=ultimo, reverse=True):
                nuevos.append((canal, m))
                state[canal] = m.id

        textos = [f"({c}) {m.raw_text or ''}{' [foto]' if m.photo else ''}" for c, m in nuevos]
        try:
            elegidos = clasificar(textos) if nuevos else set()
        except Exception as e:
            print("Claude falló, uso las reglas:", e)
            elegidos = {i for i, (c, m) in enumerate(nuevos)
                        if es_apuesta(m.raw_text or "", bool(m.photo), c in fotos)}
        print(f"{len(nuevos)} mensajes nuevos, {len(elegidos)} apuestas")
        for i in sorted(elegidos):
            if i < len(nuevos):
                await nuevos[i][1].forward_to(DESTINO)

    json.dump(state, open(STATE, "w"))


if __name__ == "__main__":
    asyncio.run(main())
