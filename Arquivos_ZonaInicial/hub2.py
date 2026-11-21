#!/usr/bin/env pybricks-micropython
# HUB 2: le o sensor HiTechnic Color da DIREITA (Porta 1) e informa a cor ao Hub 1.
#
# As cores sao decididas com a calibracao do "cores_conteiner.json"
# (feita pelo cor_conteiner.py). O sensor faz 5 amostras e a cor que
# mais se repete e a enviada.
#
# Protocolo (caixa de texto "conteiner"):
#   Hub 1 manda:   "LER;<n>"
#   Hub 2 devolve: "COR;<n>;<cor>"   (ex.: "COR;3;azul")
#
# Este hub e o SERVIDOR: rode este arquivo primeiro, depois o programa do Hub 1.
from pybricks.hubs import EV3Brick
from pybricks.parameters import Port
from pybricks.messaging import BluetoothMailboxServer, TextMailbox
from pybricks.tools import wait
import cor_conteiner as cc

ev3 = EV3Brick()

MAILBOX_CONTEINER = "conteiner"
AMOSTRAS_POR_LEITURA = 5
INTERVALO_AMOSTRA_MS = 15

PORTA_SENSOR = Port.S1      # sensor da direita
INDICE_CALIBRACAO = 0       # indice do S1 no cores_conteiner.json

# ---------------- Calibracao ----------------
ev3.screen.clear()
if not cc.carregar_calibracao():
    ev3.screen.print("SEM CALIBRACAO!")
    ev3.screen.print("Rode o")
    ev3.screen.print("cor_conteiner.py")
    ev3.speaker.beep(300, 800)
    raise SystemExit

# ---------------- Sensor ----------------
try:
    sensor = cc.SensorHiTechnic(PORTA_SENSOR)
except OSError:
    ev3.screen.print("Sem sensor S1!")
    ev3.speaker.beep(300, 800)
    raise SystemExit


def cor_mais_frequente():
    """5 amostras do sensor; devolve a cor que mais se repetiu."""
    votos = {}
    for _ in range(AMOSTRAS_POR_LEITURA):
        num, rgb, w = sensor.leitura_completa()
        cor = cc.identificar_leitura(num, rgb, w, INDICE_CALIBRACAO) or "erro"
        votos[cor] = votos.get(cor, 0) + 1
        wait(INTERVALO_AMOSTRA_MS)
    return max(votos, key=lambda c: votos[c])


# ---------------- Conexao ----------------
ev3.screen.print("Hub 2: esperando")
servidor = BluetoothMailboxServer()
caixa = TextMailbox(MAILBOX_CONTEINER, servidor)
servidor.wait_for_connection()
ev3.screen.print("Hub 1 conectado!")
ev3.speaker.beep(1000, 100)

# ---------------- Loop ----------------
while True:
    try:
        caixa.wait()
        pedido = caixa.read()
    except OSError:
        ev3.screen.print("Conexao caiu")
        ev3.speaker.beep(300, 500)
        break
    if not pedido or not pedido.startswith("LER;"):
        continue
    num = pedido[4:]
    cor = cor_mais_frequente()
    caixa.send("COR;%s;%s" % (num, cor))

    ev3.screen.clear()
    ev3.screen.print("Pedido " + num)
    ev3.screen.print(cor.upper())
