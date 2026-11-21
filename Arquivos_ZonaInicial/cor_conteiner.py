#!/usr/bin/env pybricks-micropython
from pybricks.hubs import EV3Brick
from pybricks.iodevices import I2CDevice
from pybricks.parameters import Port, Button
from pybricks.tools import wait
from pybricks.messaging import BluetoothMailboxServer, TextMailbox
import json

PORTA_SENSOR = Port.S1
REG_COR = 0x42
     
class SensorHiTechnic:
    """HiTechnic Color V2 lido direto pelo I2C. Tem o mesmo .rgb() do ColorSensor."""

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

    def leitura_completa(self):
        """Registradores do HiTechnic Color V2 a partir de 0x42:
           0x42 = número da cor (0-17), 0x43 = R, 0x44 = G, 0x45 = B, 0x46 = W."""
        try:
            d = self._dev.read(REG_COR, 5)
            return d[0], (d[1], d[2], d[3]), d[4]
        except OSError:
            return -1, (0, 0, 0), 0

    def rgb(self):
        return self.leitura_completa()[1]
CORES = ["vazio", "preto", "amarelo", "verde", "azul", "vermelho", "marrom"]
AMOSTRAS = 300             # leituras por cor na calibração (~3 s, 10 ms cada)
ARQUIVO = "cores_conteiner.json"

# ------------------------------------------------------------------------------
# FATORES usados para reconhecer a cor
#   - _caracteristicas(rgb): %R, %G, %B (tom da cor) + brilho (R+G+B)
#     comparados com _distancia, igual ao calibrar_cores_baixo.py
#   - W (canal branco do HiTechnic), peso PESO_W
#   - número de cor do próprio HiTechnic (0-17): se não bate, soma PENALIDADE_NUM
# ------------------------------------------------------------------------------
PESO_BRILHO = 0.5
PESO_W = 0.5
PENALIDADE_NUM = 100.0
DISTANCIA_MINIMA_SEGURA = 60.0   # abaixo disso, duas cores calibradas estão parecidas demais
# Intervalo min/max: folga somada para cada lado (em unidades do sensor, 0-255)
MARGEM_INTERVALO = 4

def _caracteristicas(rgb):
    r, g, b = rgb
    total = r + g + b
    if total < 1:
        return (0.0, 0.0, 0.0, 0.0)
    return (r * 100.0 / total, g * 100.0 / total, b * 100.0 / total, float(total))

def _distancia(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2
            + PESO_BRILHO * (a[3] - b[3]) ** 2)

def _vetor(rgb):
    f = _caracteristicas(rgb)
    return (f[0], f[1], f[2], f[3] * PESO_BRILHO ** 0.5)

_referencias = None

def carregar_calibracao():
    global _referencias
    try:
        with open(ARQUIVO) as f:
            dados = json.load(f)
        CALIBRACAO = dados["cores"]
        # Mesmo formato do calibrar_cores_baixo.py: uma lista com um
        # dicionário por sensor (aqui só o índice 0 = S1 do hub 2)
        _referencias = [
            {cor: (_caracteristicas(info["rgb"]), info["w"], info["num"],
                   _intervalo(info))
             for cor, info in CALIBRACAO[i].items()}
            for i in range(len(CALIBRACAO))
        ]
        return True
    except (OSError, ValueError, KeyError, TypeError):
        _referencias = None
        return False

def _intervalo(info):
    """(min[r,g,b,w], max[r,g,b,w]) da calibração, ou None (arquivo antigo)."""
    if "rgb_min" not in info:
        return None
    m = MARGEM_INTERVALO
    lo = [v - m for v in info["rgb_min"]] + [info["w_min"] - m]
    hi = [v + m for v in info["rgb_max"]] + [info["w_max"] + m]
    return lo, hi

def _fora_do_intervalo(valores, intervalo):
    """0 se a leitura está dentro do intervalo; senão, o quanto passou (soma)."""
    lo, hi = intervalo
    fora = 0
    for v, a, b in zip(valores, lo, hi):
        if v < a:
            fora += a - v
        elif v > b:
            fora += v - b
    return fora

def _distancia_total(leitura, w, num, ref):
    car_ref, w_ref, num_ref = ref[0], ref[1], ref[2]
    d = _distancia(leitura, car_ref) + PESO_W * (w - w_ref) ** 2
    if num_ref >= 0 and num != num_ref:
        d += PENALIDADE_NUM
    return d

def identificar_leitura(num, rgb, w, indice_sensor=0):
    """Cor calibrada mais parecida com uma leitura completa do HiTechnic."""
    if _referencias is None and not carregar_calibracao():
        return None
    leitura = _caracteristicas(rgb)
    refs = _referencias[indice_sensor]
    valores = (rgb[0], rgb[1], rgb[2], w)

    # 1) Cores cujo intervalo min/max contém a leitura
    dentro = [c for c, ref in refs.items()
              if ref[3] is not None and _fora_do_intervalo(valores, ref[3]) == 0]
    if len(dentro) == 1:
        return dentro[0]

    # 2) Caiu em mais de um intervalo: desempata pela distância à média.
    #    Caiu em nenhum: fica a cor de intervalo mais próximo
    #    (ou, sem intervalos no arquivo, a de média mais próxima).
    candidatos = dentro if dentro else list(refs.keys())
    melhor, menor = None, None
    for cor in candidatos:
        ref = refs[cor]
        if not dentro and ref[3] is not None:
            d = _fora_do_intervalo(valores, ref[3])
        else:
            d = _distancia_total(leitura, w, num, ref)
        if menor is None or d < menor:
            menor, melhor = d, cor
    return melhor

def cores_parecidas(calibracao_sensor):
    """Usa _vetor para achar pares de cores calibradas próximas demais
    (risco de confundir). Devolve [(cor1, cor2, distancia), ...]."""
    nomes = list(calibracao_sensor.keys())
    vetores = {c: _vetor(calibracao_sensor[c]["rgb"]) for c in nomes}
    pares = []
    for i in range(len(nomes)):
        for j in range(i + 1, len(nomes)):
            va, vb = vetores[nomes[i]], vetores[nomes[j]]
            d = sum((va[k] - vb[k]) ** 2 for k in range(4))
            if d < DISTANCIA_MINIMA_SEGURA:
                pares.append((nomes[i], nomes[j], d))
    return pares

def intervalos_sobrepostos(calibracao_sensor):
    """Pares de cores cujos intervalos min/max se cruzam em R, G, B e W
    (uma leitura poderia cair nas duas). Devolve [(cor1, cor2), ...]."""
    nomes = list(calibracao_sensor.keys())
    ints = {c: _intervalo(calibracao_sensor[c]) for c in nomes}
    pares = []
    for i in range(len(nomes)):
        for j in range(i + 1, len(nomes)):
            a, b = ints[nomes[i]], ints[nomes[j]]
            if a is None or b is None:
                continue
            if all(a[0][k] <= b[1][k] and b[0][k] <= a[1][k] for k in range(4)):
                pares.append((nomes[i], nomes[j]))
    return pares

def identificar_conteiner(sensor, indice_sensor=0):
    """Uma leitura do sensor -> cor."""
    num, rgb, w = sensor.leitura_completa()
    return identificar_leitura(num, rgb, w, indice_sensor)

def ler_conteiner(sensor, leituras=7, intervalo_ms=15):
    """Faz várias leituras e devolve a cor que mais apareceu (filtra leituras falsas)."""
    votos = {}
    for _ in range(leituras):
        cor = identificar_conteiner(sensor)
        votos[cor] = votos.get(cor, 0) + 1
        wait(intervalo_ms)
    return max(votos, key=lambda c: votos[c])


# ------------------------------------------------------------------------------
# Programa de calibração (tudo aparece na tela do hub)
# ------------------------------------------------------------------------------
ALTURA_LINHA = 14

def esperar_botao_meio(ev3):
    while Button.CENTER not in ev3.buttons.pressed():
        wait(20)
    while Button.CENTER in ev3.buttons.pressed():
        wait(20)

def tela(ev3, linhas):
    ev3.screen.clear()
    for n, linha in enumerate(linhas[:9]):
        ev3.screen.draw_text(2, n * ALTURA_LINHA, linha[:18])
    print(" | ".join(linhas))

def ler_media(sensor):
    """Lê AMOSTRAS vezes: média, MÍNIMO e MÁXIMO do RGB e do W,
    e o número HiTechnic mais comum."""
    for _ in range(5):          # descarta as primeiras leituras
        sensor.leitura_completa()
        wait(10)
    soma = [0, 0, 0]
    soma_w = 0
    rgb_min = [255, 255, 255]
    rgb_max = [0, 0, 0]
    w_min, w_max = 255, 0
    contagem_num = {}
    for _ in range(AMOSTRAS):
        num, (r, g, b), w = sensor.leitura_completa()
        for k, v in enumerate((r, g, b)):
            rgb_min[k] = min(rgb_min[k], v)
            rgb_max[k] = max(rgb_max[k], v)
        w_min = min(w_min, w)
        w_max = max(w_max, w)
        soma[0] += r
        soma[1] += g
        soma[2] += b
        soma_w += w
        contagem_num[num] = contagem_num.get(num, 0) + 1
        wait(10)
    return {
        "rgb": [int(round(v / AMOSTRAS)) for v in soma],
        "w": int(round(soma_w / AMOSTRAS)),
        "rgb_min": rgb_min,
        "rgb_max": rgb_max,
        "w_min": w_min,
        "w_max": w_max,
        "num": max(contagem_num, key=lambda c: contagem_num[c]),
    }

def salvar(calibracao):
    # calibracao = [{cor: {"rgb": [r,g,b], "w": w, "num": n,
    #                      "rgb_min": [...], "rgb_max": [...], "w_min": .., "w_max": ..}}, ...]
    with open(ARQUIVO, "w") as f:
        json.dump({"cores": calibracao}, f)

def modo_teste(ev3, sensor):
    carregar_calibracao()
    ev3.speaker.beep(frequency=1000, duration=150)
    while Button.CENTER not in ev3.buttons.pressed():
        num, rgb, w = sensor.leitura_completa()
        cor = ler_conteiner(sensor)
        ev3.screen.clear()
        ev3.screen.draw_text(2, 0, "TESTE (meio=sair)")
        ev3.screen.draw_text(2, 2 * ALTURA_LINHA, "RGB %d %d %d" % rgb)
        ev3.screen.draw_text(2, 3 * ALTURA_LINHA, "W %d  num %d" % (w, num))
        ev3.screen.draw_text(2, 5 * ALTURA_LINHA, str(cor).upper())
        wait(100)

# ------------------------------------------------------------------------------
# COMUNICAÇÃO COM O HUB 1 (este hub = HUB 2 = servidor)
#   Hub 1 manda:   "LER;<n>"          (n = número do pedido)
#   Hub 2 devolve: "COR;<n>;<cor>"    (ex.: "COR;3;azul")
# ------------------------------------------------------------------------------
MAILBOX = "conteiner"

def servir_hub1(ev3, sensor):
    carregar_calibracao()
    servidor = BluetoothMailboxServer()
    caixa = TextMailbox(MAILBOX, servidor)
    tela(ev3, ["HUB 2", "Esperando hub 1", "conectar..."])
    servidor.wait_for_connection()
    tela(ev3, ["HUB 2", "Conectado!", "", "Aguardando pedido"])
    ev3.speaker.beep(frequency=1000, duration=100)

    while True:
        try:
            caixa.wait()                 # trava até chegar mensagem do hub 1
            msg = caixa.read()
        except OSError:
            tela(ev3, ["HUB 2", "Conexao caiu"])
            ev3.speaker.beep(frequency=300, duration=500)
            return
        if not msg or not msg.startswith("LER"):
            continue
        partes = msg.split(";")
        n = partes[1] if len(partes) > 1 else "0"
        cor = ler_conteiner(sensor)
        caixa.send("COR;%s;%s" % (n, cor))
        tela(ev3, ["HUB 2", "Pedido " + n, "", str(cor).upper()])

def esperar_botao(ev3, botoes):
    while True:
        p = ev3.buttons.pressed()
        for b in botoes:
            if b in p:
                while b in ev3.buttons.pressed():
                    wait(20)
                return b
        wait(20)

def main():
    ev3 = EV3Brick()
    tela(ev3, ["CALIBRACAO", "CONTEINERS", "", "Iniciando..."])
    try:
        sensor = SensorHiTechnic(PORTA_SENSOR)
    except OSError:
        tela(ev3, ["ERRO!", "Sensor de cor", "nao encontrado", "",
                   "Confira o cabo", "MEIO = sair"])
        ev3.speaker.beep(frequency=300, duration=600)
        esperar_botao_meio(ev3)
        return

    if carregar_calibracao():
        tela(ev3, ["CONTEINERS", "Calibracao salva", "encontrada", "",
                   "MEIO = usar", "CIMA = calibrar"])
        if esperar_botao(ev3, (Button.CENTER, Button.UP)) == Button.CENTER:
            servir_hub1(ev3, sensor)
            return

    calibracao = [{}]       # um dicionário por sensor (como no calibrar_cores_baixo.py)
    total = len(CORES)
    for n, cor in enumerate(CORES, 1):
        rotulo = "Passo %d/%d" % (n, total)
        if cor == "vazio":
            instrucao = ["SEM conteiner", "na frente"]
        else:
            instrucao = ["Conteiner:", cor.upper()]
        tela(ev3, [rotulo, ""] + instrucao + ["", "Aperte o MEIO"])
        ev3.speaker.beep(frequency=600, duration=100)
        esperar_botao_meio(ev3)

        tela(ev3, [rotulo, cor.upper(), "", "Lendo..."])
        info = ler_media(sensor)
        calibracao[0][cor] = info
        r, g, b = info["rgb"]
        lo, hi = info["rgb_min"], info["rgb_max"]
        tela(ev3, [rotulo, cor.upper(), "RGB %d %d %d" % (r, g, b),
                   "min %d %d %d" % tuple(lo), "max %d %d %d" % tuple(hi),
                   "W %d-%d num %d" % (info["w_min"], info["w_max"], info["num"]),
                   "", "MEIO = continuar"])
        ev3.speaker.beep(frequency=1200, duration=100)
        esperar_botao_meio(ev3)

    salvar(calibracao)

    # Confere com _vetor se alguma cor ficou parecida demais com outra
    pares = cores_parecidas(calibracao[0])
    if pares:
        linhas = ["ATENCAO!", "Cores parecidas:"]
        for c1, c2, d in pares[:5]:
            linhas.append("%s/%s %d" % (c1[:6], c2[:6], d))
        linhas += ["", "MEIO = continuar"]
        tela(ev3, linhas)
        ev3.speaker.beep(frequency=400, duration=400)
        esperar_botao_meio(ev3)

    # Confere se algum intervalo min/max ficou cruzado com outro
    cruzados = intervalos_sobrepostos(calibracao[0])
    if cruzados:
        linhas = ["ATENCAO!", "Intervalos cruzam:"]
        for c1, c2 in cruzados[:5]:
            linhas.append("%s / %s" % (c1[:7], c2[:7]))
        linhas += ["", "MEIO = continuar"]
        tela(ev3, linhas)
        ev3.speaker.beep(frequency=400, duration=400)
        esperar_botao_meio(ev3)

    tela(ev3, ["SALVO!", ARQUIVO, "", "MEIO = teste"])
    ev3.speaker.beep(frequency=1500, duration=200)
    esperar_botao_meio(ev3)

    modo_teste(ev3, sensor)
    while Button.CENTER in ev3.buttons.pressed():
        wait(20)
    servir_hub1(ev3, sensor)

if __name__ == "__main__":
    main()
