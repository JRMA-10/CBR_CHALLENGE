#!/usr/bin/env pybricks-micropython
from pybricks.hubs import EV3Brick
from pybricks.ev3devices import ColorSensor
from pybricks.parameters import Port, Button
from pybricks.tools import wait
import json

CORES = ["vermelho", "verde", "azul", "amarelo", "branco", "preto"]
AMOSTRAS = 50 
ARQUIVO = "cores_baixo_calibradas.json"

LIMIARES = ["amarelo_verde_centro"] # Vamos tirar isso aqui


SENSOR_CENTRO_AMARELO = 2
SENSOR_CENTRO_VERDE = 1

VERDE_RGB = [None, None, None, None]              # RGB do verde de cada sensor
AMARELO_RGB = [None, None, None, None]            # RGB do amarelo de cada sensor

# Limiar AMARELO/VERDE entre os sensores centrais (divisa entre S2 e S3)
LIMIAR_CENTRO_AMARELO_RGB = None   # RGB do S3 (meio-direito, amarelo) na posição calibrada
LIMIAR_CENTRO_VERDE_RGB = None     # RGB do S2 (meio-esquerdo, verde) na posição calibrada
NOTA_CENTRO_AMARELO = 1.0          # nota verde/amarelo do S3 na posição calibrada
NOTA_CENTRO_VERDE = 0.0            # nota verde/amarelo do S2 na posição calibrada

PESO_BRILHO = 0.5


# Comparação de cores (usada no teste e em outros programas)

def _caracteristicas(rgb): #Recebe como parâmetro as informações do JSON
    r, g, b = rgb
    total = r + g + b
    if total < 1:
        return (0.0, 0.0, 0.0, 0.0)
    return (r * 100.0 / total, g * 100.0 / total, b * 100.0 / total, float(total))

def _distancia(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2
            + PESO_BRILHO * (a[3] - b[3]) ** 2)

_referencias = None

def carregar_calibracao():
    global _referencias, LIMIAR_CENTRO_AMARELO_RGB, LIMIAR_CENTRO_VERDE_RGB
    global NOTA_CENTRO_AMARELO, NOTA_CENTRO_VERDE
    try:
        with open(ARQUIVO) as f:
            dados = json.load(f)
        CALIBRACAO = dados["cores"]
    except (OSError, ValueError, KeyError):
        _referencias = None
        return False
    _referencias = [
        {cor: _caracteristicas(rgb) for cor, rgb in CALIBRACAO[i].items()}
        for i in range(4)
    ]
    for i in range(4):
        VERDE_RGB[i] = CALIBRACAO[i]["verde"]
        AMARELO_RGB[i] = CALIBRACAO[i]["amarelo"]

    limiares_salvos = dados.get("limiares")
    ia, iv = SENSOR_CENTRO_AMARELO, SENSOR_CENTRO_VERDE
    if (limiares_salvos and
            "amarelo_verde_centro" in limiares_salvos[ia] and
            "amarelo_verde_centro" in limiares_salvos[iv]):
        LIMIAR_CENTRO_AMARELO_RGB = limiares_salvos[ia]["amarelo_verde_centro"]
        LIMIAR_CENTRO_VERDE_RGB = limiares_salvos[iv]["amarelo_verde_centro"]
        NOTA_CENTRO_AMARELO = nota_verde_amarelo(ia, LIMIAR_CENTRO_AMARELO_RGB)
        NOTA_CENTRO_VERDE = nota_verde_amarelo(iv, LIMIAR_CENTRO_VERDE_RGB)
    else:
        LIMIAR_CENTRO_AMARELO_RGB = AMARELO_RGB[ia]
        LIMIAR_CENTRO_VERDE_RGB = VERDE_RGB[iv]
        NOTA_CENTRO_AMARELO, NOTA_CENTRO_VERDE = 1.0, 0.0
    return True


def _vetor(rgb):
    f = _caracteristicas(rgb)
    return (f[0], f[1], f[2], f[3] * PESO_BRILHO ** 0.5)

def _posicao_verde_amarelo(i, rgb):
    # Projeta a leitura na reta verde -> amarelo: 0 = verde, 1 = amarelo
    v, a, x = _vetor(VERDE_RGB[i]), _vetor(AMARELO_RGB[i]), _vetor(rgb)
    va = [a[k] - v[k] for k in range(4)]
    vx = [x[k] - v[k] for k in range(4)]
    norma = sum(c * c for c in va)
    if norma <= 0:
        return 0.5
    return sum(va[k] * vx[k] for k in range(4)) / norma

def nota_verde_amarelo(indice_sensor, rgb):
    # 0.0 = verde, 1.0 = amarelo (contínuo entre 0 e 1)
    if _referencias is None and not carregar_calibracao():
        return 0.5
    t = _posicao_verde_amarelo(indice_sensor, rgb)
    return min(1.0, max(0.0, t))

def erro_limiar_centro(rgb_sensor_amarelo, rgb_sensor_verde):
    # Divisa AMARELO/VERDE entre os sensores centrais:
    # S3 (meio-direito) no amarelo e S2 (meio-esquerdo) no verde.
    #   0 = exatamente como na calibração (S3 no amarelo, S2 no verde)
    #   + = robô foi para o lado do AMARELO (S2 começou a ver amarelo)
    #   - = robô foi para o lado do VERDE   (S3 começou a ver verde)
    # Vai de -1 a +1.
    if _referencias is None and not carregar_calibracao():
        return 0.0
    na = nota_verde_amarelo(SENSOR_CENTRO_AMARELO, rgb_sensor_amarelo)
    nv = nota_verde_amarelo(SENSOR_CENTRO_VERDE, rgb_sensor_verde)
    erro = ((na - NOTA_CENTRO_AMARELO) + (nv - NOTA_CENTRO_VERDE)) / 2.0
    return min(1.0, max(-1.0, erro * 2.0))

def identificar_cor(indice_sensor, rgb):
    # Retorna o nome da cor calibrada mais parecida com a leitura rgb do sensor
    if _referencias is None and not carregar_calibracao():
        return None
    leitura = _caracteristicas(rgb)
    melhor = None
    menor = None
    for cor, ref in _referencias[indice_sensor].items():
        d = _distancia(leitura, ref)
        if menor is None or d < menor:
            menor = d
            melhor = cor
    return melhor



def esperar_botao_meio(ev3):
    while Button.CENTER not in ev3.buttons.pressed():
        wait(20)
    while Button.CENTER in ev3.buttons.pressed():
        wait(20)

ALTURA_LINHA = 14          # pixels entre linhas na tela (178 x 128 -> cabem 9 linhas)

def tela(ev3, linhas):
    ev3.screen.clear()
    for n, linha in enumerate(linhas[:9]):
        ev3.screen.draw_text(2, n * ALTURA_LINHA, linha[:18])
    print(" | ".join(linhas))

def ler_media(sensor):
    soma = [0, 0, 0]
    for _ in range(AMOSTRAS):
        r, g, b = sensor.rgb()
        soma[0] += r
        soma[1] += g
        soma[2] += b
        wait(10)
    return tuple(int(round(v / AMOSTRAS)) for v in soma)

def ler_e_mostrar(ev3, sensores, passo, titulo, indices=(0, 1, 2, 3)):
    # Lê apenas os sensores de 'indices', mostra os RGB na tela e espera o MEIO
    tela(ev3, [passo, titulo, "", "Lendo..."])
    valores = [None, None, None, None]
    for i in indices:
        valores[i] = ler_media(sensores[i])
    linhas = [passo, titulo]
    for i in indices:
        r, g, b = valores[i]
        linhas.append("S%d %3d %3d %3d" % (i + 1, r, g, b))
    linhas += ["", "MEIO = continuar"]
    tela(ev3, linhas)
    ev3.speaker.beep(frequency=1200, duration=100)
    esperar_botao_meio(ev3)
    return valores

def salvar(calibracao, limiares):
    with open(ARQUIVO, "w") as f:
        json.dump({"cores": calibracao, "limiares": limiares}, f)

def modo_teste(ev3, sensores):
    carregar_calibracao()
    ev3.speaker.beep(frequency=1000, duration=150)
    while Button.CENTER not in ev3.buttons.pressed():
        linhas = ["TESTE (meio=sair)", "cor / nota V-A"]
        rgbs = [s.rgb() for s in sensores]
        for i in range(4):
            cor = identificar_cor(i, rgbs[i])
            if i in (SENSOR_CENTRO_VERDE, SENSOR_CENTRO_AMARELO):
                linhas.append("S%d %s %.2f" % (i + 1, cor, nota_verde_amarelo(i, rgbs[i])))
            else:
                linhas.append("S%d %s" % (i + 1, cor))
        erro = erro_limiar_centro(rgbs[SENSOR_CENTRO_AMARELO], rgbs[SENSOR_CENTRO_VERDE])
        linhas += ["centro: %+.2f" % erro, "(0 = S2:V | S3:A)"]
        ev3.screen.clear()
        for n, linha in enumerate(linhas):
            ev3.screen.draw_text(2, n * ALTURA_LINHA, linha[:18])
        wait(150)

def main():
    ev3 = EV3Brick()
    tela(ev3, ["CALIBRACAO", "SENSORES DE BAIXO", "", "Iniciando..."])
    ev3.speaker.beep(frequency=800, duration=100)
    sensores, faltando = [], []
    for nome, porta in (("S1", Port.S1), ("S2", Port.S2), ("S3", Port.S3), ("S4", Port.S4)):
        try:
            sensores.append(ColorSensor(porta))
        except OSError:
            faltando.append(nome)
    if faltando:
        tela(ev3, ["ERRO!", "Sensor de cor", "nao encontrado:", " ".join(faltando), "",
                   "Confira os cabos", "MEIO = sair"])
        ev3.speaker.beep(frequency=300, duration=600)
        esperar_botao_meio(ev3)
        return
    total = len(CORES) + len(LIMIARES)
    passo = 0

    # 1) CORES: os 4 sensores em cima da cor
    calibracao = [{}, {}, {}, {}]
    for cor in CORES:
        passo += 1
        rotulo = "Passo %d/%d" % (passo, total)
        tela(ev3, [rotulo, "CORES", "Coloque os 4", "sensores no:", "", cor.upper(), "",
                   "Aperte o MEIO"])
        ev3.speaker.beep(frequency=600, duration=100)
        esperar_botao_meio(ev3)
        valores = ler_e_mostrar(ev3, sensores, rotulo, cor.upper())
        for i in range(4):
            calibracao[i][cor] = valores[i]

    # 2) LIMIAR: lê APENAS o meio-esquerdo (S2 no verde) e o meio-direito (S3 no amarelo)
    limiares = [{}, {}, {}, {}]
    passo += 1
    rotulo = "Passo %d/%d" % (passo, total)
    tela(ev3, [rotulo, "LIMIAR CENTRO",
               "Meio-Dir (S%d):" % (SENSOR_CENTRO_AMARELO + 1),
               "  -> no AMARELO",
               "Meio-Esq (S%d):" % (SENSOR_CENTRO_VERDE + 1),
               "  -> no VERDE",
               "(S1 e S4 livres)",
               "Aperte o MEIO"])
    ev3.speaker.beep(frequency=600, duration=100)
    esperar_botao_meio(ev3)

    indices_centro = (SENSOR_CENTRO_VERDE, SENSOR_CENTRO_AMARELO)
    valores = ler_e_mostrar(ev3, sensores, rotulo, "LIM CENTRO", indices=indices_centro)
    for i in indices_centro:
        limiares[i]["amarelo_verde_centro"] = valores[i]

    # 3) SALVA e mostra o resumo do limiar central
    salvar(calibracao, limiares)
    carregar_calibracao()
    tela(ev3, ["SALVO!", ARQUIVO[:18],
               "Limiar Central:",
               "S%d (Amar)=%.2f" % (SENSOR_CENTRO_AMARELO + 1, NOTA_CENTRO_AMARELO),
               "S%d (Verd)=%.2f" % (SENSOR_CENTRO_VERDE + 1, NOTA_CENTRO_VERDE),
               "(S1 e S4 ignorados)",
               "", "MEIO = teste"])
    ev3.speaker.beep(frequency=1500, duration=200)
    esperar_botao_meio(ev3)

    modo_teste(ev3, sensores)


if __name__ == "__main__":
    main()