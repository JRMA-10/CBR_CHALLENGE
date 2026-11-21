#!/usr/bin/env pybricks-micropython
from pybricks.hubs import EV3Brick
from pybricks.ev3devices import Motor, ColorSensor
from pybricks.parameters import Port, Stop
from pybricks.tools import wait, StopWatch
import json

class Estrategia: 
    def __init__(self):
        # Robô
        self.ev3 = EV3Brick()
        
        #Motores: 
        self.motor_esq = Motor(Port.C)
        self.motor_dir = Motor(Port.D)
        
        #Sensores: 
        self.s1 = ColorSensor(Port.S1)
        self.s2 = ColorSensor(Port.S2)
        self.s3 = ColorSensor(Port.S3)
        self.s4 = ColorSensor(Port.S4)
        self.sensores = [self.s1, self.s2, self.s3, self.s4]
        
        # Arquivos de calibração
        self.ARQUIVO_CALIBRACAO = "cores_baixo_calibradas.json"
        self._referencias = None
        self.PESO_BRILHO = 0.5
        self.carregar_calibracao()
        
        # Configuração: 
        self.VEL = 1000
        self.VEL_GIRO = 350

        # Estados: 
        self.ESTADO_BUSCA_VERDE = 1
        self.ESTADO_AVANCO_VERMELHO = 2
        self.ESTADO_ALINHAMENTO = 3
        self.ESTADO_VERMELHO_DETECTADO = 4
        self.ESTADO_LEITURA_CONTEINERS = 5

        self.estado_atual = self.ESTADO_BUSCA_VERDE

    # FUNÇÕES DE CALIBRAÇÃO
    @staticmethod
    def _caracteristicas(rgb):
        r, g, b = rgb
        total = r + g + b
        if total < 1:
            return (0.0, 0.0, 0.0, 0.0)
        return (r * 100.0 / total, g * 100.0 / total, b * 100.0 / total, float(total))

    def _distancia(self, a, b):
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2
                + self.PESO_BRILHO * (a[3] - b[3]) ** 2)

    def carregar_calibracao(self):
        try:
            with open(self.ARQUIVO_CALIBRACAO) as f:
                dados = json.load(f)
            CALIBRACAO = dados["cores"]
        except (OSError, ValueError, KeyError):
            self._referencias = None
            return False
        self._referencias = [
            {cor: self._caracteristicas(rgb) for cor, rgb in CALIBRACAO[i].items()}
            for i in range(4)
        ]
        return True

    def identificar_cor(self, indice_sensor, rgb):
        if self._referencias is None and not self.carregar_calibracao():
            return "desconhecido"
        leitura = self._caracteristicas(rgb)
        melhor = None
        menor = None
        for cor, ref in self._referencias[indice_sensor].items():
            d = self._distancia(leitura, ref)
            if menor is None or d < menor:
                menor = d
                melhor = cor
        return melhor

    def ler_cores(self):
        """Lê os 4 sensores e devolve a lista de cores."""
        return [self.identificar_cor(i, self.sensores[i].rgb()) for i in range(4)]
    
    # FUNÇÕES DE MOVIMENTAÇÃO
    def parar(self):
        self.motor_esq.hold()
        self.motor_dir.hold()
        wait(40)

    def andar_frente(self, vel=None):
        if vel is None:
            vel = self.VEL
        self.motor_esq.run(vel)
        self.motor_dir.run(vel)

    def andar_tras(self, tempo_ms=700, vel=None):
        if vel is None:
            vel = self.VEL
        self.motor_esq.run(-vel)
        self.motor_dir.run(-vel)
        wait(tempo_ms)
        self.parar()

    def andar_frente_tempo(self, tempo_ms, vel=None):
        self.andar_frente(vel)
        wait(tempo_ms)
        self.parar()

    def girar_90_esquerda(self):
        self.parar()
        wait(50)
        self.motor_esq.run_angle(-self.VEL_GIRO, 210, wait=False)
        self.motor_dir.run_angle(self.VEL_GIRO, 210, wait=True)
        self.parar()
    
    def girar_90_direita(self):
        self.parar()
        wait(50)
        self.motor_esq.run_angle(self.VEL_GIRO, 210, wait=False)
        self.motor_dir.run_angle(-self.VEL_GIRO, 210, wait=True)
        self.parar()
        
    # ALINHAMENTO: 
    def alinhar_extremos(self, cor_alvo, sensor_informante, tempo_limite_ms=4000):
        # Se nehum dos sensores disponíveis: 
        if sensor_informante not in (0, 3): return

        self.parar()
        # Recua um pouco: garante que os dois sensores fiquem antes da faixa
        self._recuar_suave(60, vel=120)
        
        # Passada 1: aproximação em velocidade média
        self._passada_alinhamento(cor_alvo, vel=int(self.VEL_GIRO * 0.6), tempo_limite_ms=tempo_limite_ms)
        
        # Recua só um pouquinho e refaz devagar para precisão
        self._recuar_suave(35, vel=80)
        self._passada_alinhamento(cor_alvo, vel=60, tempo_limite_ms=tempo_limite_ms)
        self.parar()

    def _recuar_suave(self, graus, vel=100):
        """Ré curta e lenta, sem tranco."""
        self.motor_esq.run_angle(-vel, graus, then=Stop.HOLD, wait=False)
        self.motor_dir.run_angle(-vel, graus, then=Stop.HOLD, wait=True)
        wait(50)

    def _passada_alinhamento(self, cor_alvo, vel=100, tempo_limite_ms=4000,
    confirmacoes=2, rampa_ms=200):
        relogio = StopWatch()
        esq_ok = dir_ok = False
        cont_esq = cont_dir = 0

        while not (esq_ok and dir_ok) and relogio.time() < tempo_limite_ms:
            fator = min(1.0, 0.3 + 0.7 * relogio.time() / rampa_ms)
            v = int(vel * fator)

            if not esq_ok:
                if self.identificar_cor(0, self.s1.rgb()) == cor_alvo:
                    cont_esq += 1
                else:
                    cont_esq = 0
                if cont_esq >= confirmacoes:
                    esq_ok = True
                    self.motor_esq.hold()
                else:
                    self.motor_esq.run(v)

            if not dir_ok:
                if self.identificar_cor(3, self.s4.rgb()) == cor_alvo:
                    cont_dir += 1
                else:
                    cont_dir = 0
                if cont_dir >= confirmacoes:
                    dir_ok = True
                    self.motor_dir.hold()
                else:
                    self.motor_dir.run(v)

            wait(5)

        self.motor_esq.hold()
        self.motor_dir.hold()
        wait(50)

    def leitura_conteiners(
    self, 
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
            c3 = self.identificar_cor(2, self.s3.rgb())  # Sensor 3 (índice 2)
            c4 = self.identificar_cor(3, self.s4.rgb())  # Sensor 4 (índice 3)

            if (
                self.identificar_cor(0, self.s1.rgb()) == "vermelho"
                or self.identificar_cor(1, self.s2.rgb()) == "vermelho"
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

            self.motor_esq.run(vel + correcao)
            self.motor_dir.run(vel - correcao)
            wait(10)

        self.parar()