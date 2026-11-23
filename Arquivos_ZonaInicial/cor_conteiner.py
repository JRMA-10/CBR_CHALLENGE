#!/usr/bin/env pybricks-micropython
# ===== CONTEINERS - HUB 2 (HiTechnic Color V2 na porta S1, lido por I2C) =====
# Calibracao no MESMO FORMATO do calibrar_direita.py:
#   {"versao": 2,
#    "Direita": {cor: [{"m": [r, g, b, w], "s": [r, g, b, w]}, ...], ...}}
#   - caracteristicas = [R/soma, G/soma, B/soma, W/255]
#   - cada cor tem varias POSICOES; cada posicao guarda a MEDIA APARADA
#     (descarta os 10% extremos) e o DESVIO.
# A identificacao usa a mesma distancia (z-score) e votacao do sensor_direita.py.
#
# Botoes na calibracao: CENTRO = gravar esta posicao | BAIXO = pular
# Depois de calibrar (ou com calibracao salva), serve o hub 1:
#   Hub 1 manda "LER;<n>"  ->  Hub 2 devolve "COR;<n>;<cor>"
# ==============================================================================
from pybricks.hubs import EV3Brick
from pybricks.iodevices import I2CDevice
from pybricks.parameters import Port, Button
from pybricks.tools import wait
from pybricks.messaging import BluetoothMailboxServer, TextMailbox
import json

PORTA_SENSOR = Port.S1
NOME_SENSOR = 'Direita'
ARQUIVO = 'cores_conteiner.json'
REG_COR = 0x42

# 'vazio' = so o chao (sem conteiner). Conteiners: grave nas posicoes em que o
# robo realmente vai ler. Use BAIXO para pular o que nao existir.
POS_CONTEINER = ['CENTRO', 'MAIS PERTO', 'MAIS LONGE', 'UM POUCO ANTES', 'UM POUCO DEPOIS']
CORES = [
    ('amarelo',  POS_CONTEINER),
    ('verde',    POS_CONTEINER),
    ('azul',     POS_CONTEINER),
    ('marrom',   POS_CONTEINER),
    ('vermelho', POS_CONTEINER),
    ('vazio',    ['CHAO 1', 'CHAO 2', 'CHAO 3']),
    ('preto',    POS_CONTEINER),
]
APARAR = 0.10                                 # descarta 10% mais baixos e 10% mais altos
AMOSTRAS = 300                                # por posicao (~3 s)
DESVIO_MINIMO = [0.012, 0.012, 0.012, 0.015]  # evita uma cor "estreita" demais

# ---------- Classificacao (iguais ao sensor_direita.py) ----------
PESO_CARACT = [1.0, 1.0, 1.0, 0.4]  # [R, G, B proporcionais, brilho]
MARGEM_CONFIANCA = 1.6     # 2a cor precisa estar 1.6x mais longe para o voto ser "confiavel"
LIMITE_REJEICAO = 400.0    # longe de todas as cores calibradas -> 'vazio'
VOTOS_MINIMOS = 1.5        # vencedora com menos votos que isso -> 'vazio'


class SensorHiTechnic:
    """HiTechnic Color V2 lido direto pelo I2C."""

    def __init__(self, porta):
        self._dev = None
        for endereco in (0x01, 0x08):
            try:
                dev = I2CDevice(porta, endereco)
                dev.read(0x00, 1)          # leitura de teste
                self._dev = dev
                break
            except OSError:
                pass
        if self._dev is None:
            raise OSError("HiTechnic nao encontrado")

    def rgbw(self):
        """0x42 = numero da cor, 0x43 = R, 0x44 = G, 0x45 = B, 0x46 = W."""
        try:
            d = self._dev.read(REG_COR, 5)
            return [float(d[1]), float(d[2]), float(d[3]), float(d[4])]
        except OSError:
            return [0.0, 0.0, 0.0, 0.0]


def caracteristicas(v):
    """[R/soma, G/soma, B/soma, brilho 0..1] - igual ao calibrar_direita.py."""
    r, g, b, w = v
    soma = r + g + b + 1.0
    return [r / soma, g / soma, b / soma, w / 255.0]


def carregar_calibracao():
    try:
        with open(ARQUIVO, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def salvar_calibracao(dados):
    with open(ARQUIVO, 'w') as f:
        json.dump(dados, f)


def gravar_posicao(sensor):
    """Le AMOSTRAS vezes; media e desvio APARADOS de cada caracteristica."""
    for _ in range(10):                   # descarta leituras iniciais
        sensor.rgbw()
        wait(20)
    canais = [[], [], [], []]
    for _ in range(AMOSTRAS):
        f = caracteristicas(sensor.rgbw())
        for i in range(4):
            canais[i].append(f[i])
        wait(10)
    corte = int(AMOSTRAS * APARAR)
    media = []
    desvio = []
    for i in range(4):
        vals = sorted(canais[i])
        if corte > 0:
            vals = vals[corte:len(vals) - corte]
        n = len(vals)
        m = sum(vals) / n
        var = sum((x - m) * (x - m) for x in vals) / n
        media.append(m)
        desvio.append(max(DESVIO_MINIMO[i], var ** 0.5))
    return {'m': [round(x, 4) for x in media], 's': [round(x, 4) for x in desvio]}


def classificar_cor(calibracao, vetor_lido):
    """(cor, distancia, margem). margem = dist(2a cor) / dist(vencedora)."""
    tabela = calibracao.get(NOME_SENSOR, {})
    if not tabela:
        return 'vazio', 0.0, 99.0
    f = caracteristicas(vetor_lido)
    melhor = {}
    for cor, perfis in tabela.items():
        d_cor = 1e9
        for p in perfis:                     # compara com TODAS as posicoes da cor
            m = p['m']
            sd = p['s']
            d = 0.0
            for i in range(4):
                z = (f[i] - m[i]) / sd[i]
                d += z * z * PESO_CARACT[i]
            if d < d_cor:
                d_cor = d
        melhor[cor] = d_cor
    ordem = sorted(melhor.items(), key=lambda x: x[1])
    cor1, d1 = ordem[0]
    d2 = ordem[1][1] if len(ordem) > 1 else d1 * 10 + 1
    margem = (d2 + 1.0) / (d1 + 1.0)
    if d1 > LIMITE_REJEICAO:
        return 'vazio', d1, margem
    return cor1, d1, margem


def ler_conteiner(sensor, calibracao, max_amostras=10, votos_para_decidir=3.0):
    """Votacao ponderada pela confianca (igual ao ler_hitech_direita)."""
    votos = {}
    for i in range(1, max_amostras + 1):
        cor, _, margem = classificar_cor(calibracao, sensor.rgbw())
        peso = 1.0 if margem >= MARGEM_CONFIANCA else 0.3
        votos[cor] = votos.get(cor, 0.0) + peso
        if i >= 3:
            ordem = sorted(votos.values(), reverse=True)
            seg = ordem[1] if len(ordem) > 1 else 0.0
            if ordem[0] >= votos_para_decidir and seg <= ordem[0] * 0.34:
                break
        wait(8)
    cor = max(votos, key=votos.get)
    if votos[cor] < VOTOS_MINIMOS:
        cor = 'vazio'
    return cor

# ------------------------------------------------------------------------------
# Tela / botoes
# ------------------------------------------------------------------------------
ALTURA_LINHA = 14


def tela(ev3, linhas):
    ev3.screen.clear()
    for n, linha in enumerate(linhas[:9]):
        ev3.screen.draw_text(2, n * ALTURA_LINHA, linha[:18])
    print(" | ".join(linhas))


def esperar_botao(ev3, botoes):
    while True:
        p = ev3.buttons.pressed()
        for b in botoes:
            if b in p:
                while b in ev3.buttons.pressed():
                    wait(20)
                return b
        wait(20)


def calibrar(ev3, sensor):
    calibracao = carregar_calibracao()
    perfis_sensor = {}
    for cor, posicoes in CORES:
        lista = []
        for pos in posicoes:
            tela(ev3, [NOME_SENSOR, cor.upper(), pos, "", "CENTRO=gravar", "BAIXO=pular"])
            ev3.speaker.beep(600, 80)
            if esperar_botao(ev3, (Button.CENTER, Button.DOWN)) == Button.DOWN:
                continue
            tela(ev3, [NOME_SENSOR, cor.upper(), pos, "", "Lendo..."])
            perfil = gravar_posicao(sensor)
            lista.append(perfil)
            print("{} | {:8s} {:15s} -> media {} desvio {}".format(
                NOME_SENSOR, cor, pos, perfil['m'], perfil['s']))
            ev3.speaker.beep(1200, 80)
        if lista:
            perfis_sensor[cor] = lista

    calibracao['versao'] = 2
    calibracao[NOME_SENSOR] = perfis_sensor
    salvar_calibracao(calibracao)
    tela(ev3, ["SALVO!", ARQUIVO, "", "MEIO = teste"])
    ev3.speaker.beep(1500, 200)
    esperar_botao(ev3, (Button.CENTER,))
    return calibracao


def modo_teste(ev3, sensor, calibracao):
    ultima = None
    while Button.CENTER not in ev3.buttons.pressed():
        cor = ler_conteiner(sensor, calibracao)
        if cor != ultima:
            tela(ev3, ["TESTE (meio=sair)", "", cor.upper()])
            ultima = cor
        wait(100)
    while Button.CENTER in ev3.buttons.pressed():
        wait(20)


# ------------------------------------------------------------------------------
# COMUNICACAO COM O HUB 1 (este hub = HUB 2 = servidor)
# ------------------------------------------------------------------------------
MAILBOX = "conteiner"


def servir_hub1(ev3, sensor, calibracao):
    servidor = BluetoothMailboxServer()
    caixa = TextMailbox(MAILBOX, servidor)
    tela(ev3, ["HUB 2", "Esperando hub 1", "conectar..."])
    servidor.wait_for_connection()
    tela(ev3, ["HUB 2", "Conectado!", "", "Aguardando pedido"])
    ev3.speaker.beep(1000, 100)

    while True:
        try:
            caixa.wait()
            msg = caixa.read()
        except OSError:
            tela(ev3, ["HUB 2", "Conexao caiu"])
            ev3.speaker.beep(300, 500)
            return
        if not msg or not msg.startswith("LER"):
            continue
        partes = msg.split(";")
        n = partes[1] if len(partes) > 1 else "0"
        cor = ler_conteiner(sensor, calibracao)
        caixa.send("COR;%s;%s" % (n, cor))
        tela(ev3, ["HUB 2", "Pedido " + n, "", cor.upper()])


def main():
    ev3 = EV3Brick()
    tela(ev3, ["CONTEINERS", "", "Iniciando..."])
    try:
        sensor = SensorHiTechnic(PORTA_SENSOR)
    except OSError:
        tela(ev3, ["ERRO!", "Sensor de cor", "nao encontrado", "",
                   "Confira o cabo", "MEIO = sair"])
        ev3.speaker.beep(300, 600)
        esperar_botao(ev3, (Button.CENTER,))
        return

    calibracao = carregar_calibracao()
    if calibracao.get('versao') == 2 and calibracao.get(NOME_SENSOR):
        tela(ev3, ["CONTEINERS", "Calibracao salva", "encontrada", "",
                   "MEIO = usar", "CIMA = calibrar"])
        if esperar_botao(ev3, (Button.CENTER, Button.UP)) == Button.UP:
            calibracao = calibrar(ev3, sensor)
            modo_teste(ev3, sensor, calibracao)
    else:
        calibracao = calibrar(ev3, sensor)
        modo_teste(ev3, sensor, calibracao)

    servir_hub1(ev3, sensor, calibracao)


if __name__ == "__main__":
    main()
