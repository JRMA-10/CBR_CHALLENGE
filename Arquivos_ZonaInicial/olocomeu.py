#!/usr/bin/env pybricks-micropython
from pybricks.hubs import EV3Brick
from pybricks.ev3devices import Motor, ColorSensor
from pybricks.parameters import Port, Stop
from pybricks.tools import wait, StopWatch
import json
import math
from pybricks.messaging import BluetoothMailboxClient, TextMailbox

ev3 = EV3Brick()
conteiners = []          # cores dos conteiners, na ordem em que foram lidos
ultima_salva = [None]    # última cor colocada na lista

# ==============================================================================
# CONFIGURAÇÃO DE HARDWARE
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
    return (r * 100.0 / total, g * 100.0 / total, b * 100.0 / total, float(total))

def _distancia(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2
            + PESO_BRILHO * (a[3] - b[3]) ** 2)

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
    return melhor

# ==============================================================================
# PARÂMETROS E VELOCIDADES
# ==============================================================================
VEL = 700
VEL_GIRO = 200

ESTADO_BUSCA_VERDE = 1
ESTADO_AVANCO_VERMELHO = 2
ESTADO_ALINHAMENTO = 3
ESTADO_VERMELHO_DETECTADO = 4

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

# ==============================================================================
# NOVA FUNÇÃO DE ALINHAMENTO COM BASE NO SENSOR INFORMANTE
# ==============================================================================
def alinhar_extremos(cor_alvo, sensor_informante, vel_giro=VEL_GIRO, tempo_limite_ms=4000):
    parar()
    wait(50)
    relogio = StopWatch()

    if sensor_informante == 0:
        sensor_oposto = s4
        indice_oposto = 3
        # Extrema esquerda viu. Gira direita no eixo para a extrema direita alcançar.
        vel_esq = vel_giro
        vel_dir = -vel_giro
    elif sensor_informante == 3:
        sensor_oposto = s1
        indice_oposto = 0
        # Extrema direita viu. Gira esquerda no eixo para a extrema esquerda alcançar.
        vel_esq = -vel_giro
        vel_dir = vel_giro
    else:
        # Se um dos sensores centrais invocou a função, aborta a rotação.
        return 

    while relogio.time() < tempo_limite_ms:
        cor_atual_oposta = identificar_cor(indice_oposto, sensor_oposto.rgb())
        print(cor_atual_oposta)
        
        if cor_atual_oposta == cor_alvo:
            break
            
        motor_esq.run(vel_esq)
        motor_dir.run(vel_dir)
        wait(10)
        
    parar()
    wait(50)

# ==============================================================================
# SEGUIR A DIVISA VERDE (SENSOR 2) / AMARELO (SENSOR 3)
# ==============================================================================
def leitura_conteiners(vel=300, correcao_max=120, passo=15, suavizacao=0.7,
                       tempo_limite_ms=1100, parar_em=None):
    relogio = StopWatch()
    alvo = 0.0       # correção desejada (positivo = virar para a direita)
    correcao = 0.0   # correção aplicada (filtrada)
    cores = []

    # Leitura dos conteiners pelo hub 2, SEM travar o PID:
    # manda um pedido, segue andando e só confere a resposta nas próximas voltas.
    global _num_pedido
    pedido_pendente = None      # número do pedido que ainda não respondeu
    hora_pedido = 0
    ultima_cor = None           # última cor lida (para saber quando muda)
    repeticoes = 0              # quantas respostas seguidas com a mesma cor
    CONFIRMACOES = 2            # respostas iguais seguidas para aceitar a cor
    IGNORAR = ("vazio", "erro", "None")

    while relogio.time() < tempo_limite_ms:
        # ---------- Hub 2: pedir / receber a cor do conteiner ----------
        if caixa_conteiner is not None:
            try:
                if pedido_pendente is None:
                    _num_pedido += 1
                    pedido_pendente = _num_pedido
                    hora_pedido = relogio.time()
                    caixa_conteiner.send("LER;%d" % pedido_pendente)
                else:
                    esperado = "COR;%d;" % pedido_pendente
                    resposta = caixa_conteiner.read()
                    if resposta and resposta.startswith(esperado):
                        cor_lida = resposta[len(esperado):]
                        pedido_pendente = None
                        if cor_lida == ultima_cor:
                            repeticoes += 1
                        else:
                            ultima_cor = cor_lida
                            repeticoes = 1
                        # Salva quando a cor foi confirmada e é diferente da
                        # última salva (cada conteiner entra uma vez só).
                        # "vazio" entre conteiners libera a mesma cor de novo.
                        if repeticoes == CONFIRMACOES:
                            if cor_lida in IGNORAR:
                                ultima_salva[0] = None
                            elif cor_lida != ultima_salva[0]:
                                conteiners.append(cor_lida)
                                ultima_salva[0] = cor_lida
                                ev3.speaker.beep(1500, 50)
                                print("Conteiner:", cor_lida, conteiners)
                    elif relogio.time() - hora_pedido > 1000:
                        pedido_pendente = None      # sem resposta: pede de novo
            except OSError:
                pass

        cores = [identificar_cor(i, sensores[i].rgb()) for i in range(4)]
        c2 = cores[1]
        c3 = cores[2]

        if parar_em is not None and parar_em in cores:
            break

        if c2 == "verde" and c3 == "amarelo":
            # Alinhado: a correção volta suavemente para zero
            alvo *= 0.5
        elif c2 == "verde" and c3 == "verde":
            # Divisa ficou à direita -> virar levemente para a direita
            alvo = min(alvo + passo, correcao_max)
        elif c2 == "amarelo" and c3 == "amarelo":
            # Divisa ficou à esquerda -> virar levemente para a esquerda
            alvo = max(alvo - passo, -correcao_max)
        elif c2 == "amarelo" and c3 == "verde":
            # Invertido (situação rara): mantém a correção atual
            pass
        # Outras cores/desconhecido: mantém a última correção

        # Filtro passa-baixa: evita trancos nos motores
        correcao = suavizacao * correcao + (1 - suavizacao) * alvo

        motor_esq.run(vel + correcao)
        motor_dir.run(vel - correcao)
        wait(10)

    parar()
    return cores

# ==============================================================================
# COMUNICAÇÃO COM O HUB 2 (sensor HiTechnic dos conteiners)
#   Hub 1 manda:   "LER;<n>"          (n = número do pedido)
#   Hub 2 devolve: "COR;<n>;<cor>"    (ex.: "COR;3;azul")
#   No hub 2 deve estar rodando o cor_conteiner.py (ele espera a conexão).
# ==============================================================================
NOME_HUB2 = "ev3dev"          # <-- nome Bluetooth do hub 2
MAILBOX_CONTEINER = "conteiner"

cliente_bt = None
caixa_conteiner = None
_num_pedido = 0

def conectar_hub2():
    global cliente_bt, caixa_conteiner
    ev3.screen.print("Conectando hub 2")
    cliente_bt = BluetoothMailboxClient()
    caixa_conteiner = TextMailbox(MAILBOX_CONTEINER, cliente_bt)
    cliente_bt.connect(NOME_HUB2)
    ev3.screen.print("Hub 2 OK!")
    ev3.speaker.beep(1000, 100)

def ler_cor_hub2(tempo_limite_ms=1500):
    """Pede uma leitura ao hub 2 e devolve a cor (ou "erro" se não responder)."""
    global _num_pedido
    if caixa_conteiner is None:
        return "erro"
    _num_pedido += 1
    esperado = "COR;%d;" % _num_pedido
    try:
        caixa_conteiner.send("LER;%d" % _num_pedido)
        relogio = StopWatch()
        while relogio.time() < tempo_limite_ms:
            resposta = caixa_conteiner.read()
            # Confere o número para não pegar a resposta de um pedido antigo
            if resposta and resposta.startswith(esperado):
                return resposta[len(esperado):]
            wait(10)
    except OSError:
        pass
    return "erro"

# ==============================================================================
# INICIALIZAÇÃO E LOOP PRINCIPAL
# ==============================================================================
ev3.screen.clear()
ev3.screen.print("Etapa 1 Iniciada")
ev3.speaker.beep(600, 100)

print("Iniciando maquina de estados da Etapa 1 com calibração JSON...")
conectar_hub2()

while True:
    leitura_conteiners(vel=300, tempo_limite_ms=5000, parar_em="vermelho")
    print(conteiners)