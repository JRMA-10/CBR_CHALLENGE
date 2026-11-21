#!/usr/bin/env pybricks-micropython
# HUB 2: le os 3 sensores HiTechnic Color e informa as cores ao Hub 1.
#   Porta 1 (S1) = Direita
#   Porta 2 (S2) = Centro
#   Porta 3 (S3) = Esquerda
#
# Protocolo (caixa de texto "conteiner"):
#   Hub 1 manda:   "LER;<n>"
#   Hub 2 devolve: "COR;<n>;<esq>,<centro>,<dir>"   (ex.: "COR;3;azul,vazio,verde")
#
# Este hub e o SERVIDOR: rode este arquivo primeiro, depois o programa do Hub 1.
from pybricks.hubs import EV3Brick
from pybricks.parameters import Port
from pybricks.iodevices import Ev3devSensor
from pybricks.messaging import BluetoothMailboxServer, TextMailbox
from pybricks.tools import wait
import json

ev3 = EV3Brick()

MAILBOX_CONTEINER = "conteiner"
ARQUIVO_CALIBRACAO = "calibracao_cores.json"

# (nome mostrado, porta, nome da tabela no calibracao_cores.json)
# A ordem desta lista e a ordem da mensagem: esquerda, centro, direita.
SENSORES = [
    ("esquerda", Port.S3, "Esquerda"),
    ("centro",   Port.S2, "Meio"),
    ("direita",  Port.S1, "Direita"),
]


def carregar_calibracao():
    try:
        with open(ARQUIVO_CALIBRACAO, "r") as f:
            return json.load(f)
    except Exception:
        print("Sem calibracao, usando so os numeros.")
        return {}


calibracao = carregar_calibracao()
sensores = [(nome, Ev3devSensor(porta), calibracao.get(chave, {})) for nome, porta, chave in SENSORES]

def ler_numero(sensor):
    leitura = sensor.read("COLOR")
    return leitura[0] if isinstance(leitura, (tuple, list)) else int(leitura)


def ler_cores():
    """Devolve [cor_esq, cor_centro, cor_dir]."""
    cores = []
    for _, sensor, tabela in sensores:
        num = ler_numero(sensor)
        cores.append(tabela.get(str(num), "n" + str(num)))
    return cores

# ---------------- Conexao ----------------
ev3.screen.clear()
ev3.screen.print("Hub 2: esperando")
servidor = BluetoothMailboxServer()
caixa = TextMailbox(MAILBOX_CONTEINER, servidor)
servidor.wait_for_connection()
ev3.screen.print("Hub 1 conectado!")
ev3.speaker.beep(1000, 100)

# ---------------- Loop ----------------
while True:
    caixa.wait()
    pedido = caixa.read()
    if not pedido or not pedido.startswith("LER;"): continue
    num = pedido[4:]
    cores = ler_cores()
    caixa.send("COR;%s;%s" % (num, ",".join(cores)))

    ev3.screen.clear()
    ev3.screen.print("E: " + cores[0])
    ev3.screen.print("C: " + cores[1])
    ev3.screen.print("D: " + cores[2])
