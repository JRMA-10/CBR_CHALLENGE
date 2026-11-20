#!/usr/bin/env pybricks-micropython
# Calibracao das cores dos 3 sensores HiTechnic Color no Hub 2:
#   Porta 1 (S1) = Direita
#   Porta 2 (S2) = Meio (Frente)
#   Porta 3 (S3) = Esquerda
#
# Para cada sensor e cada cor (incluindo 'vazio', sem cubo na frente):
# posicione o cubo (ou deixe sem cubo no caso de 'vazio') e aperte o botao do CENTRO.
# O resultado vai para calibracao_cores.json.

from pybricks.hubs import EV3Brick
from pybricks.parameters import Button, Port
from pybricks.iodevices import Ev3devSensor
from pybricks.tools import wait
import json

# Tenta usar o mux_sensores se existir no seu projeto; senão usa direto nas portas S1, S2 e S3
try:
    from mux_sensores import iniciar, valores, carregar_calibracao, salvar_calibracao
except ImportError:
    MAPA_PORTAS = {1: Port.S1, 2: Port.S2, 3: Port.S3, 4: Port.S4}

    def iniciar(sensores_dict):
        lista = []
        for canal, (nome, _) in sorted(sensores_dict.items()):
            s = Ev3devSensor(MAPA_PORTAS[canal])
            lista.append((nome, s))
        return lista

    def valores(sensor):
        # Modo COLOR retorna o índice da cor (0 a 17) na primeira posição
        leitura = sensor.read('COLOR')
        num = leitura[0] if isinstance(leitura, (tuple, list)) else int(leitura)
        return (None, (num,))

    def carregar_calibracao():
        try:
            with open('calibracao_cores.json', 'r') as f:
                return json.load(f)
        except Exception:
            return {}

    def salvar_calibracao(dados):
        with open('calibracao_cores.json', 'w') as f:
            json.dump(dados, f)


# 3 sensores HiTechnic: Direita (S1), Meio/Frente (S2) e Esquerda (S3)
SENSORES_COR = {
    1: ('Direita', 'ht-nxt-color-v2'),
    2: ('Meio', 'ht-nxt-color-v2'),
    3: ('Esquerda', 'ht-nxt-color-v2'),
}

# Inclui 'vazio' para calibrar a leitura quando NÃO há cubo na frente do sensor
CORES = ['vazio', 'vermelho', 'amarelo', 'azul', 'verde', 'preto', 'branco']
AMOSTRAS = 200

ev3 = EV3Brick()


def esperar_centro():
    while Button.CENTER not in ev3.buttons.pressed():
        wait(10)
    while Button.CENTER in ev3.buttons.pressed():
        wait(10)


calibracao = carregar_calibracao()

for nome, sensor in iniciar(SENSORES_COR):
    # contagem[numero][cor] = quantas vezes o numero apareceu sobre aquela cor
    contagem = {}
    for cor in CORES:
        ev3.screen.clear()
        ev3.screen.print('Sensor: ' + nome)
        if cor == 'vazio':
            ev3.screen.print('Deixe SEM CUBO')
            ev3.screen.print('(VAZIO)')
        else:
            ev3.screen.print('Coloque cubo')
            ev3.screen.print(cor.upper())
        ev3.screen.print('e aperte CENTRO')
        esperar_centro()

        ev3.screen.print('lendo...')
        vistos = {}
        for _ in range(AMOSTRAS):
            numero = valores(sensor)[1][0]
            vistos[numero] = vistos.get(numero, 0) + 1
            contagem.setdefault(numero, {})
            contagem[numero][cor] = contagem[numero].get(cor, 0) + 1
            wait(15)
        print(nome, cor, 'numeros lidos (numero: vezes):', vistos)
        ev3.speaker.beep()

    # Cada numero fica com a cor em que ele mais apareceu
    tabela = {}
    for numero, cores in contagem.items():
        tabela[str(numero)] = max(cores, key=cores.get)
        if len(cores) > 1:
            print('ATENCAO', nome, ': numero', numero, 'apareceu em', cores,
                  '-> ficou', tabela[str(numero)])

    print(nome, 'tabela:', tabela)
    calibracao[nome] = tabela
    salvar_calibracao(calibracao)

ev3.screen.clear()
ev3.screen.print('Calibracao salva!')
print('Salvo em calibracao_cores.json:', calibracao)
wait(2000)