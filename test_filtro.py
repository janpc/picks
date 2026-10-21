# Ejecuta: python3 test_filtro.py  (tras cambiar las reglas de picks.py)
from datetime import datetime, timedelta
from types import SimpleNamespace as M
from picks import es_apuesta, agrupar

SI = [
    "🎾 #TEAMSLAMTIPS - WTA WUHAN🇨🇳\n\n👉🏼 Li Gana el encuentro\n\n📈 Cuota 1,50 📍STAKE 5💎\n\n📎 Podéis realizar la apuesta AQUÍ",
    "💡¡Nueva Apuesta!💡\n\nMasters Shanghai: Alex de Miñaur vs Karen Khachanov\n\nhttps://www.pensadordeapuestas.com/x/\n\nTipster: SergiTenis",
    "⚽️ Atalanta - Pafos \n➡️ Atalanta Gana el partido \n\n💰CUOTA 1.67 📊STAKE 5\n✅ MEJOR CUOTA EN BET365 ✅",
    "#Pick1\n🏆 Challenger Antofagasta\n🆚 Justo - Comesaña\n➡️ Justo\n📈 @2.91\n🏠 Pinnacle\n💰 Stake 0.5/10\n🚫 Cuota mínima: @2.5",
    "Pick 18\nStake 0.50\nPinnacle. Cuota mínima 1.72",
    "Pick 19\nStake 1\n\nVamos con esta apuesta para mañana.",
    "s3 LIVE https://www.betfair.es/apuestas/futbol/cs-timisul",
    "s3 https://betway.es/es/en/sports/event/17305224",
    "🏆 PFL\n🆚 Patrick Ocheme vs Cornel Thompson\n➡️ Cornel Thompson\n📈 @2.80\n🏠 Winamax\n💰 Stake 1/10\n\n🥊Pick #10",
    "🔔 PREPARTIDO !! (LBTENNIS)\n\n\n\n",
    "🔔PRE !! 💸\n\nCH Olbia Q - Catania Q \n\nStake 3",
    "➡️ Davidovich Fokina ML\n📈 @2\n🏠 Winamax\n💰 Stake 1.50/10",
    "Vamos con un Live.\n\nStake 1",
    "🏆 Pick 14: España ACB\n🆚 Breogan - Joventut\n📈 @1.86",
    "Pick 27 - 08/2026:\n\n🇮🇹 Nápoles - Como\n⚽️ EMPATE\n🔹 Stake 1\n💰 Cuota 3",
    "Os dejo esta combinada en directo. Stake 1",
    "¿Hoy se lía en el derbi de Londres? Cuota 23",
    "Partidazo esta noche. Ya podéis ver mi análisis y crear apuesta aquí 👈🏽",
    "Mi apuesta para hoy.\n\n❤️ si la sigues!!",
]
NO = [
    "✅✅✅✅ ¡STAKAZO 10!💎#TEAMSLAMTIPS💎\n\n¡STAKAZO ERRORAZO DE CUOTA ACERTADO! marcaban las cuotas",
    "🎾 PROGRAMACIÓN DEL CANAL HOY\n\n➡️ STAKE 5 GRATUITO💎 | 13:00h\n➡️ STAKAZO 10💎 | 16:00h",
    "📎 Análisis FREE 🔎.md 💬ARGUMENTACIÓN DEL PICK FREE",
    "De haberse retirado al acabar el set, @SergiTenisFree hubiese acertado la cuota 2,25 de Ruud.",
    "¡Funbet cuota 7\ufe0f\u20e3 para la 2ª jornada de la Champions League!",
    "• PARLAY CUOTA 4.00 ✅",
    "🤩¡NOS LLEVAMOS EL STAKAZO DEL PACK A CUOTON 1.86, TOP!",
    "6-7, 7-6, 6-1. Finalmente se hizo justicia y Justo nos dio esta @2.91 ✅",
    "Vamos con 2 picks en 2'.\n\nEl primero Stake 0.5 Pinnacle, Winamax, Bet365",
    "Pick en 2'. Winamax\nMejor cuota Bet365",
    "📊 Estadísticas Septiembre\n\nPronósticos: 22\nUnidades: +8.24 ✅\nYield +47.1%",
    "Picks pendientes:\n\nCuarto de Eala @1.84 stk1\nGanadora BJKC Rep.Checa @2 stk1",
    "Habia meditado si entrar con la victoria de Dilek a 2.45. 1.66x1.66 = 2.75",
    "@2.00   S3 ✅ \n\nBastante liquidez entraba en betfair",
    "Cuota 2.80 mandada con stake 4, cuando la cuota real ya era 1.25.",
    "s3 +17.5 hándicap de la primera mitad y la ganan..! ",
    "Y ya acabamos de pillar el primer BOMBAZO super liquido @2.80 que la real es 1.3 🔥🔥",
    "🔶 WINAMAX — de 99€ a 49,50€",
    "Ernesta Kareckaite 🔵\nLeon Shahbazyan ❌\nJane Osigwe ✅\n\nResultados del mes: -4.71u",
    "🎾\nA.ANDREEV ✅\n\nOtro gran acierto por aquí ✅",
    "📢 A las 12:05 dejaré un prepartido CHALLENGER.",
    "⚠️ Todo interesado en acceder al Premium 🏦 LB Pinnacle",
    "Resumen del día:\n\n- Khachanov + Vacherot +1.41✅\n\n+5.86 unidades ✅",
    "¿Quién creéis que será el Pichichi esta temporada?\nAnonymous Poll\n\nRaphinha @1,90\n\nKylian Mbappé @2,10",
    "Datos de septiembre:\n📈 14 apuestas | 8 acertadas - 6 falladas (57,1% acierto)\n📊 Yield: +311%",
    "📋 Picks 24 de agosto, RESULTADOS:\n\n👉 Bolonia - Lazio (X) @3.1 ❌\n👉 Clermont - Sochaux (X) @3 ✅",
    "Seguimos sumando con la Champions!! ✅ Faltaron 2 córners del PSG para la cuota 7!!!",
    "🇪🇸\nEn poco más de 1 hora arranca nuestro pick!",
    "🔥 DEXTER PICKS \n\n📊 Nuevo tipster con estadísticas públicas\n\n🟢 ¡ACCESO TOTALMENTE GRATUITO!\n\n🔗 https://t.me/+N-HiM_TVyXk4ZjY0\n\n\nPick FREE Winamax !! 21:00h",
]
FOTO_SI = ["", "Se juega en 3h… coronamos con Sascha!?"]
FOTO_NO = ["3-0 para Happek ✅\n\nVuelve a salir muy fácil.", "🔴 Gunduz/Yigenler que empezaron 0-2 abajo",
           "¿Vamos con un Free? \n\nLlegamos a 300 seguidores en la web y sale. \n\nEs un click, en la ⭐️"]

fallos = [t for t in SI if not es_apuesta(t)] + [t for t in NO if es_apuesta(t)] \
       + [t for t in FOTO_SI if not es_apuesta(t, True, True)] + [t for t in FOTO_NO if es_apuesta(t, True, True)]
assert not fallos, fallos

# agrupar: álbum junto, fotos seguidas juntas, texto suelto aparte
t0 = datetime(2026, 1, 1)
ms = [M(grouped_id=7, photo=1, date=t0), M(grouped_id=7, photo=1, date=t0), M(grouped_id=None, photo=None, date=t0),
      M(grouped_id=None, photo=1, date=t0), M(grouped_id=None, photo=1, date=t0 + timedelta(seconds=60)),
      M(grouped_id=None, photo=1, date=t0 + timedelta(minutes=10))]
assert [len(g) for g in agrupar(ms)] == [2, 1, 2, 1], [len(g) for g in agrupar(ms)]
print("ok")

# estadísticas
from picks import ganancia, tabla
h = [dict(nombre="A", stake=2, cuota=1.5, res="ganada"), dict(nombre="A", stake=1, cuota=2, res="perdida"),
     dict(nombre="A", stake=1, cuota=None, res="nula"), dict(nombre="B", stake=1, cuota=3, res=None)]
assert [ganancia(p) for p in h] == [1.0, -1, 0, 0]
assert "1✅ 1❌ 1➖ · +0.00u · yield +0%" in tabla(h) and "1 pendientes" in tabla(h), tabla(h)
h += [dict(nombre="A", stake=None, cuota=None, res="ganada", unidades=1.29)]  # de un resumen: suma, no entra al yield
assert ganancia(dict(stake=None, cuota=2.0, res="ganada")) == 1.0 and ganancia(dict(stake=None, res="perdida")) == -1
assert ganancia(h[-1]) == 1.29 and "+1.29u · yield +0%" in tabla(h), tabla(h)
print("ok")
