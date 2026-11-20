#!/usr/bin/env pybricks-micropython
from pybricks.hubs import EV3Brick
from pybricks.ev3devices import Motor, ColorSensor
from pybricks.parameters import Port, Button
from pybricks.tools import wait, StopWatch
import json

ev3 = EV3Brick()

motor_esq = Motor(Port.D)
motor_dir = Motor(Port.C)

s1 = ColorSensor(Port.S1)
s2 = ColorSensor(Port.S2)
s3 = ColorSensor(Port.S3)
s4 = ColorSensor(Port.S4)
sensores = [s1, s2, s3, s4]

ARQUIVO_CALIBRACAO = "cores_baixo_calibradas.json"
_referencias = None
PESO_BRILHO = 0.5


def _caracteristicas(rgb):
    r, g, b = rgb
    total = r + g + b
    if total < 1:
        return (0.0, 0.0, 0.0, 0.0)
    return (
        r * 100.0 / total,
        g * 100.0 / total,
        b * 100.0 / total,
        float(total),
    )


def _distancia(a, b):
    return (
        (a[0] - b[0]) ** 2
        + (a[1] - b[1]) ** 2
        + (a[2] - b[2]) ** 2
        + PESO_BRILHO * (a[3] - b[3]) ** 2
    )


def carregar_calibracao():
    global _referencias
    try:
        with open(ARQUIVO_CALIBRACAO) as f:
            dados = json.load(f)
        calibracao = dados["cores"]
    except (OSError, ValueError, KeyError):
        _referencias = None
        return False
    _referencias = [
        {cor: _caracteristicas(rgb) for cor, rgb in calibracao[i].items()}
        for i in range(4)
    ]
    return True


carregar_calibracao()


def identificar_cor(indice_sensor, rgb):
    if _referencias is None and not carregar_calibracao():
        return "desconhecido"
    leitura = _caracteristicas(rgb)
    melhor = None
    menor = None
    for cor, ref in _referencias[indice_sensor].items():
        d = _distancia(leitura, ref)
        if menor is None or d < menor:
            menor = d
            melhor = cor
    return melhor


def parar():
    motor_esq.hold()
    motor_dir.hold()
    wait(40)


def leitura_conteiners(
    vel=400,
    kp=100.0,
    ki=0.5,
    kd=15.0,
    correcao_max=70.0,
    suavizacao=0.75,
):
    dt_relogio = StopWatch()

    correcao = 0.0
    integral = 0.0
    erro_anterior = 0.0

    while True:
        c3 = identificar_cor(2, s3.rgb())  # Sensor 3 (índice 2)
        c4 = identificar_cor(3, s4.rgb())  # Sensor 4 (índice 3)

        if (
            identificar_cor(0, s1.rgb()) == "vermelho"
            or identificar_cor(1, s2.rgb()) == "vermelho"
            or c3 == "vermelho"
            or c4 == "vermelho"
        ):
            break

        # Erro no limiar entre Sensor 3 (esperado no verde) e Sensor 4 (esperado no amarelo)
        if c3 == "verde" and c4 == "amarelo":
            erro = 0.0
        elif c3 == "verde" and c4 == "verde":
            erro = -0.5
        elif c3 == "amarelo" and c4 == "amarelo":
            erro = 0.5
        elif c3 == "amarelo" and c4 == "verde":
            erro = 1.0
        else:
            erro = 0.0

        dt_ms = max(dt_relogio.time(), 1)
        dt_relogio.reset()
        dt = dt_ms / 1000.0

        p = kp * erro

        integral += erro * dt
        integral = max(-50.0, min(50.0, integral))
        i_termo = ki * integral

        derivada = (erro - erro_anterior) / dt
        d_termo = kd * derivada
        erro_anterior = erro

        alvo = max(-correcao_max, min(correcao_max, p + i_termo + d_termo))
        correcao = suavizacao * correcao + (1.0 - suavizacao) * alvo

        motor_esq.run(vel + correcao)
        motor_dir.run(vel - correcao)
        wait(10)

    parar()


ev3.screen.clear()
ev3.screen.print("TESTE PID")

leitura_conteiners(
    vel=320,
    kp=120.0,
    ki=0.5,
    kd=25.0,
    correcao_max=80.0,
    suavizacao=0.75,
)