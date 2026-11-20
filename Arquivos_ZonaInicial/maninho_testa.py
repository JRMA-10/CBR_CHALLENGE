#!/usr/bin/env pybricks-micropython
from pybricks.hubs import EV3Brick
from pybricks.ev3devices import Motor, ColorSensor
from pybricks.parameters import Port, Stop
from pybricks.tools import wait, StopWatch
import json

ev3 = EV3Brick()

# ==============================================================================
# CONFIGURAÇÃO DE HARDWARE (EV3 - 2 MOTORES E 4 SENSORES)
# ==============================================================================
motor_esq = Motor(Port.C)
motor_dir = Motor(Port.D)

s1 = ColorSensor(Port.S1)
s2 = ColorSensor(Port.S2)
s3 = ColorSensor(Port.S3)
s4 = ColorSensor(Port.S4)
sensores = [s1, s2, s3, s4]

# ==============================================================================
# CARREGAMENTO DO JSON DE CALIBRAÇÃO DE CORES
# ==============================================================================
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
        CALIBRACAO = dados["cores"]
    except (OSError, ValueError, KeyError):
        _referencias = None
        return False
    _referencias = [
        {cor: _caracteristicas(rgb) for cor, rgb in CALIBRACAO[i].items()}
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
    print(melhor)
    return melhor


VEL = 500
VEL_GIRO = 200

ESTADO_BUSCA_VERDE = 1
ESTADO_AVANCO_VERMELHO = 2
ESTADO_ALINHAMENTO = 3
ESTADO_VERMELHO_DETECTADO = 4
ESTADO_LEITURA_CONTEINERS = 5

estado_atual = ESTADO_BUSCA_VERDE


def parar():
    motor_esq.hold()
    motor_dir.hold()
    wait(40)


def andar_frente(vel=VEL):
    motor_esq.run(vel)
    motor_dir.run(vel)


def andar_tras(vel=VEL):
    relogio = StopWatch()
    while relogio.time() < 600:
        motor_esq.run(vel * -1)
        motor_dir.run(vel * -1)
    parar()


def girar_90_esquerda():
    parar()
    wait(50)
    motor_esq.run_angle(-VEL_GIRO, 210, wait=False)
    motor_dir.run_angle(VEL_GIRO, 210, wait=True)
    parar()


def girar_90_direita():
    parar()
    wait(50)
    motor_esq.run_angle(VEL_GIRO, 210, wait=False)
    motor_dir.run_angle(-VEL_GIRO, 210, wait=True)
    parar()


def alinhar_extremos(cor_alvo, sensor_informante, vel_giro=VEL_GIRO, tempo_limite_ms=4000):
    if sensor_informante not in (0, 3):
        return

    parar()
    # Recua um pouco: garante que os dois sensores fiquem antes da faixa
    _recuar_suave(60, vel=120)
    # Passada 1: aproximação em velocidade média
    _passada_alinhamento(cor_alvo, vel=int(vel_giro * 0.6), tempo_limite_ms=tempo_limite_ms)
    # Recua só um pouquinho e refaz devagar para precisão
    _recuar_suave(35, vel=80)
    _passada_alinhamento(cor_alvo, vel=60, tempo_limite_ms=tempo_limite_ms)
    parar()


def _recuar_suave(graus, vel=100):
    """Ré curta e lenta, sem tranco."""
    motor_esq.run_angle(-vel, graus, then=Stop.HOLD, wait=False)
    motor_dir.run_angle(-vel, graus, then=Stop.HOLD, wait=True)
    wait(50)


def _passada_alinhamento(cor_alvo, vel=100, tempo_limite_ms=4000,
                         confirmacoes=2, rampa_ms=200):
    relogio = StopWatch()
    esq_ok = dir_ok = False
    cont_esq = cont_dir = 0

    while not (esq_ok and dir_ok) and relogio.time() < tempo_limite_ms:
        # Rampa de partida: começa em 30% e chega a 100% em rampa_ms
        fator = min(1.0, 0.3 + 0.7 * relogio.time() / rampa_ms)
        v = int(vel * fator)

        if not esq_ok:
            if identificar_cor(0, s1.rgb()) == cor_alvo:
                cont_esq += 1
            else:
                cont_esq = 0
            if cont_esq >= confirmacoes:
                esq_ok = True
                motor_esq.hold()
            else:
                motor_esq.run(v)

        if not dir_ok:
            if identificar_cor(3, s4.rgb()) == cor_alvo:
                cont_dir += 1
            else:
                cont_dir = 0
            if cont_dir >= confirmacoes:
                dir_ok = True
                motor_dir.hold()
            else:
                motor_dir.run(v)

        wait(5)

    motor_esq.hold()
    motor_dir.hold()
    wait(50)


def leitura_conteiners(
    vel=400,
    kp=120.0,
    ki=0.5,
    kd=25.0,
    correcao_max=200,
    suavizacao=0.8,
    tempo_limite_ms=5000,
    parar_em=None,
):
    relogio = StopWatch()
    dt_relogio = StopWatch()

    correcao = 0.0
    integral = 0.0
    erro_anterior = 0.0
    cores = []

    while relogio.time() < tempo_limite_ms:
        cores = [identificar_cor(i, sensores[i].rgb()) for i in range(4)]

        if parar_em is not None and parar_em in cores:
            break

        c2 = cores[1]
        c3 = cores[2]

        # Calcula o erro no limiar amarelo/verde (0 = alinhado na divisa)
        if c2 == "verde" and c3 == "amarelo":
            erro = 0.0
        elif c2 == "verde" and c3 == "verde":
            erro = -0.5
        elif c2 == "amarelo" and c3 == "amarelo":
            erro = 0.5
        elif c2 == "amarelo" and c3 == "verde":
            erro = 1.0
        else:
            erro = 0.0

        dt_ms = max(dt_relogio.time(), 1)
        dt_relogio.reset()
        dt = dt_ms / 1000.0

        # Termo Proporcional
        p = kp * erro

        # Termo Integral com anti-windup
        integral += erro * dt
        integral = max(-50.0, min(50.0, integral))
        i_termo = ki * integral

        # Termo Derivativo
        derivada = (erro - erro_anterior) / dt
        d_termo = kd * derivada
        erro_anterior = erro

        # Saída bruta do PID limitada por correcao_max
        alvo = max(-correcao_max, min(correcao_max, p + i_termo + d_termo))

        # Filtro de suavização na correção aplicada aos motores
        correcao = suavizacao * correcao + (1.0 - suavizacao) * alvo

        motor_esq.run(vel + correcao)
        motor_dir.run(vel - correcao)
        wait(10)

    parar()
    return cores


ev3.screen.clear()
ev3.screen.print("Etapa 1 Iniciada")
ev3.speaker.beep(600, 100)

print("Iniciando maquina de estados da Etapa 1 com calibração JSON...")

while True:
    # 1. Leitura centralizada: coleta e identifica a cor dos 4 sensores ao mesmo tempo
    c0 = identificar_cor(0, sensores[0].rgb())
    c1 = identificar_cor(1, sensores[1].rgb())
    c2 = identificar_cor(2, sensores[2].rgb())
    c3 = identificar_cor(3, sensores[3].rgb())
    cores = [c0, c1, c2, c3]

    viu_verde = "verde" in cores
    viu_azul = "azul" in cores
    viu_amarelo = "amarelo" in cores
    viu_vermelho = "vermelho" in cores

    if estado_atual == ESTADO_BUSCA_VERDE:
        # PRIORIDADE MÁXIMA: Verifica primeiro se encontrou as bordas (Azul/Amarelo)
        if viu_azul or viu_amarelo:
            parar()  # Trava os motores instantaneamente ao detectar a borda
            ev3.speaker.beep(400, 400)
            wait(500)

            cor_alvo = "azul" if viu_azul else "amarelo"

            # Descobre qual dos sensores extremos viu a cor para passar como parâmetro
            sensor_inf = -1
            if c0 == cor_alvo:
                sensor_inf = 0
            elif c3 == cor_alvo:
                sensor_inf = 3

            if sensor_inf != -1:
                alinhar_extremos(cor_alvo, sensor_inf, vel_giro=VEL_GIRO, tempo_limite_ms=4000)

            andar_tras()

            if viu_azul:
                girar_90_esquerda()
            elif viu_amarelo:
                girar_90_direita()

            wait(500)
            estado_atual = ESTADO_AVANCO_VERMELHO
            print("Transicao: Movendo em direcao à linha vermelha.")

        # SECUNDÁRIA: Se não está na borda e está vendo verde, segue
        elif viu_verde:
            andar_frente(VEL)

        # Caso padrão: não vê borda, avança
        elif viu_vermelho:
            alinhar_extremos("vermelho", 0 if c0 == "vermelho" else 3, vel_giro=VEL_GIRO, tempo_limite_ms=4000)
            relogio = StopWatch()
            while relogio.time() < 300:
                andar_tras(VEL)
            parar()
            girar_90_esquerda()
            parar()
            andar_frente(VEL)
            if viu_azul:
                alinhar_extremos("azul", 0 if c0 == "azul" else 3, vel_giro=VEL_GIRO, tempo_limite_ms=4000)
                while relogio.time() < 300:
                    andar_tras(VEL)
                girar_90_esquerda()
            elif viu_amarelo:
                alinhar_extremos("amarelo", 0 if c0 == "amarelo" else 3, vel_giro=VEL_GIRO, tempo_limite_ms=4000)
                while relogio.time() < 370:
                    andar_frente(VEL)
                estado_atual = ESTADO_LEITURA_CONTEINERS
        else:
            andar_frente(VEL)

    elif estado_atual == ESTADO_AVANCO_VERMELHO:
        # Avança sem "wait()" bloqueando o processo de leitura
        andar_frente(VEL)

        if viu_vermelho:
            parar()

            # Alinha no vermelho antes de encerrar
            sensor_inf = 0 if c0 == "vermelho" else (3 if c3 == "vermelho" else -1)
            if sensor_inf != -1:
                alinhar_extremos("vermelho", sensor_inf, vel_giro=VEL_GIRO, tempo_limite_ms=4000)

            ev3.speaker.beep(1200, 400)
            print("Linha vermelha encontrada! Fim da Etapa 1.")
            estado_atual = ESTADO_VERMELHO_DETECTADO

        elif viu_azul or viu_amarelo:
            # Guarda AGORA qual lado viu a borda (na próxima volta do loop a
            # leitura já mudou, porque o robô continuou andando)
            cor_borda = "azul" if viu_azul else "amarelo"
            if cores[0] == cor_borda or cores[1] == cor_borda:
                lado_borda = "esquerda"
            else:
                lado_borda = "direita"
            print("Borda", cor_borda, "a", lado_borda, ". Corrigindo...")
            estado_atual = ESTADO_ALINHAMENTO

    elif estado_atual == ESTADO_ALINHAMENTO:
        for v in (VEL // 2, VEL // 4):
            andar_frente(v)
            wait(60)
        parar()

        _recuar_suave(90, vel=150)
        sinal = 1 if lado_borda == "esquerda" else -1   # +1 = vira à direita
        indices = (0, 1) if lado_borda == "esquerda" else (2, 3)
        motor_esq.reset_angle(0)
        while abs(motor_esq.angle()) < 120:   # ~ limite de correção
            ainda_ve = any(identificar_cor(i, sensores[i].rgb()) == cor_borda
                           for i in indices)
            if not ainda_ve and abs(motor_esq.angle()) > 30:
                break
            motor_esq.run(sinal * 120)
            motor_dir.run(-sinal * 120)
            wait(10)
        parar()

        estado_atual = ESTADO_AVANCO_VERMELHO

    elif estado_atual == ESTADO_VERMELHO_DETECTADO:
        relogio = StopWatch()
        while relogio.time() < 300:
            motor_esq.run(VEL * -1)
            motor_dir.run(VEL * -1)
        parar()
        wait(100)
        girar_90_esquerda()
        parar()

        # Anda para frente LENDO OS SENSORES A CADA VOLTA até achar o amarelo.
        # (viu_amarelo é da leitura antiga do loop principal e não muda aqui dentro)
        relogio = StopWatch()
        sensor_amarelo = -1
        while relogio.time() < 6000:
            leitura = [identificar_cor(i, sensores[i].rgb()) for i in range(4)]
            if "amarelo" in leitura:
                sensor_amarelo = leitura.index("amarelo")
                break
            andar_frente(300)
            wait(10)
        parar()

        if sensor_amarelo != -1:
            # alinhar_extremos só aceita os sensores extremos (0 ou 3)
            sensor_inf = 0 if sensor_amarelo <= 1 else 3
            alinhar_extremos("amarelo", sensor_inf, vel_giro=VEL_GIRO, tempo_limite_ms=4000)
            relogio = StopWatch()
            while relogio.time() < 370:
                andar_frente(VEL)
            girar_90_esquerda()
            estado_atual = ESTADO_LEITURA_CONTEINERS
        else:
            print("Amarelo nao encontrado.")

        # Sai do estado: sem isso o loop repetia ré + giro para sempre
        parar()
        ev3.speaker.beep(800, 300)

    elif estado_atual == ESTADO_LEITURA_CONTEINERS:
        leitura_conteiners(
            vel=400,
            kp=120.0,
            ki=0.5,
            kd=25.0,
            correcao_max=25,
            suavizacao=0.7,
            tempo_limite_ms=9200,
            parar_em="vermelho",
        )
        alinhar_extremos("vermelho", sensor_inf, vel_giro=VEL_GIRO, tempo_limite_ms=4000)

        relogio = StopWatch()
        while relogio.time() < 300:
            andar_tras()

        girar_90_esquerda()
        if not viu_azul:
            andar_frente(VEL)
        alinhar_extremos("azul", sensor_inf, vel_giro=VEL_GIRO, tempo_limite_ms=4000)

        break
    wait(15)