# Ejecuta una vez en tu ordenador: python3 crear_sesion.py
# Pide tu número y el código de Telegram, e imprime la cadena para el secreto TG_SESSION
# y la lista de tus canales con su ID para el secreto CANALES.
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = int(input("API_ID: "))
api_hash = input("API_HASH: ")
with TelegramClient(StringSession(), api_id, api_hash) as c:
    print("\nTus canales y grupos (ID  nombre):")
    for d in c.iter_dialogs():
        if d.is_channel or d.is_group:
            print(f"{d.id}  {d.name}")
    print("\nTG_SESSION (NO la compartas, da acceso a tu cuenta):\n")
    print(c.session.save())
