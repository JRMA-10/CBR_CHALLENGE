#!/usr/bin/env pybricks-micropython
# ============ LEITURA DE COR SO DO SENSOR DA DIREITA (HUB 2, porta S1) ============
# Mesma logica do cidade_2.py (classificar_cor + leitura por votacao), mas para
# UM sensor so. Roda sozinho: le em loop e mostra a cor na tela e no terminal.
# Usa a tabela 'Direita' do calibracao_containers.json (containers).
# ==================================================================================
from pybricks.hubs import EV3Brick
from pybricks.parameters import Port
from pybricks.iodevices import Ev3devSensor
from pybricks.tools import wait
import json

PORTA_DIREITA = Port.S1
NOME_SENSOR = 'Direita'
# Sensor da direita le os CONTAINERS: usa a calibracao feita no calibrar_direita.py
ARQUIVO_CALIBRACAO = 'calibracao_containers.json'

# ---------- AJUSTES DA CLASSIFICACAO (iguais ao cidade_2.py) ----------
PESO_CARACT = [1.0, 1.0, 1.0, 0.4]  # [R, G, B proporcionais, brilho]
MARGEM_CONFIANCA = 1.6     # 2a cor precisa estar 1.6x mais longe para o voto ser "confiavel"
LIMITE_REJEICAO = 400.0    # longe de todas as cores calibradas -> 'vazio'
VOTOS_MINIMOS = 1.5        # vencedora com menos votos que isso -> 'vazio'


def caracteristicas(v):
    """[R/soma, G/soma, B/soma, brilho 0..1]"""
    r, g, b, w = v
    soma = r + g + b + 1.0
    return [r / soma, g / soma, b / soma, w / 255.0]


def carregar_calibracao():
    try:
        with open(ARQUIVO_CALIBRACAO, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def iniciar_sensor(porta, nome):
    for tentativa in range(15):          # o sensor I2C as vezes demora para responder
        try:
            s = Ev3devSensor(porta)
            s.read('NORM')
            wait(100)
            return s
        except Exception as e:
            print("Sensor {} ainda nao respondeu ({}), tentando de novo...".format(nome, e))
            wait(300)
    raise Exception("Sensor {} nao responde. Confira o cabo!".format(nome))


def ler_rgbw_norm(sensor):
    leitura = sensor.read('NORM')
    r = float(leitura[0])
    g = float(leitura[1])
    b = float(leitura[2])
    w = float(leitura[3]) if len(leitura) > 3 else (r + g + b) / 3.0
    return [r, g, b, w]


def classificar_cor(calibracao, vetor_lido):
    """
    Retorna (cor, distancia, margem) para o sensor da DIREITA.
    distancia: quanto a leitura difere da cor vencedora (menor = mais parecida).
    margem: dist(2a cor) / dist(vencedora) -> quanto maior, mais certeza.
    """
    tabela = calibracao.get(NOME_SENSOR, {})
    if not tabela:
        return 'vazio', 0.0, 99.0

    melhor = {}
    if calibracao.get('versao') == 2:
        f = caracteristicas(vetor_lido)
        for cor, perfis in tabela.items():
            d_cor = 1e9
            for p in perfis:                 # compara com TODAS as posicoes gravadas da cor
                m = p['m']
                sd = p['s']
                d = 0.0
                for i in range(4):
                    z = (f[i] - m[i]) / sd[i]
                    d += z * z * PESO_CARACT[i]
                if d < d_cor:
                    d_cor = d
            melhor[cor] = d_cor
    else:
        # Calibracao antiga (1 vetor por cor)
        r, g, b, w = vetor_lido
        for cor, ref in tabela.items():
            if len(ref) == 5:
                ref = ref[1:]
            dsoma = (r + g + b) - (ref[0] + ref[1] + ref[2])
            melhor[cor] = ((r - ref[0]) ** 2 + (g - ref[1]) ** 2 + (b - ref[2]) ** 2 +
                           2.0 * (w - ref[3]) ** 2 + 0.5 * dsoma * dsoma)

    ordem = sorted(melhor.items(), key=lambda x: x[1])
    cor1, d1 = ordem[0]
    d2 = ordem[1][1] if len(ordem) > 1 else d1 * 10 + 1
    margem = (d2 + 1.0) / (d1 + 1.0)
    if calibracao.get('versao') == 2 and d1 > LIMITE_REJEICAO:
        return 'vazio', d1, margem
    return cor1, d1, margem


def ler_hitech_direita(sensor, calibracao, max_amostras=10, votos_para_decidir=3.0):
    """
    Votacao ponderada pela confianca, so para o sensor da DIREITA:
    - amostra confiavel = 1 voto; ambigua = 0.3 voto;
    - para quando uma cor tem >= 3 votos sem rival proximo (normalmente 3 amostras);
    - vencedora com poucos votos confiaveis -> 'vazio'.
    Retorna (cor, votos, ultimo_vetor, amostras).
    """
    votos = {}
    vetor = [0, 0, 0, 0]
    i = 0
    for i in range(1, max_amostras + 1):
        vetor = ler_rgbw_norm(sensor)
        cor, _, margem = classificar_cor(calibracao, vetor)
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
    return cor, votos, vetor, i


if __name__ == "__main__":
    ev3 = EV3Brick()
    calibracao = carregar_calibracao()
    print("Calibracao v{} | cores da Direita: {}".format(
        calibracao.get('versao', 1), list(calibracao.get(NOME_SENSOR, {}).keys())))
    sensor = iniciar_sensor(PORTA_DIREITA, NOME_SENSOR)

    ultima = None
    while True:
        cor, votos, vetor, n = ler_hitech_direita(sensor, calibracao)
        print("DIREITA: {:8s} | RGBW {} | votos {} | {} amostras".format(
            cor.upper(), [int(x) for x in vetor], votos, n))
        if cor != ultima:                    # so redesenha a tela quando muda
            ev3.screen.clear()
            ev3.screen.print("SENSOR DIREITA")
            ev3.screen.print(cor.upper())
            ultima = cor
        wait(200)
