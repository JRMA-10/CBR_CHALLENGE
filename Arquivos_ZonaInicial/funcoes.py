#!/usr/bin/env pybricks-micropython
from pybricks.hubs import EV3Brick
from pybricks.ev3devices import Motor, ColorSensor
from pybricks.parameters import Port, Stop
from pybricks.tools import wait, StopWatch
import json
from pybricks.messaging import BluetoothMailboxClient, TextMailbox

class Funcoes: 
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
        self.diferenca_dir = 0.550

        # Estados: 
        self.ESTADO_BUSCA_VERDE = 1
        self.ESTADO_AVANCO_VERMELHO = 2
        self.ESTADO_ALINHAMENTO = 3
        self.ESTADO_VERMELHO_DETECTADO = 4
        self.ESTADO_LEITURA_CONTEINERS = 5
        self.ESTADO_ENTREGA_CUBOS = 6

        self.estado_atual = self.ESTADO_BUSCA_VERDE
        
        # Lista de conteiners (posição 1..5, "vazio" quando não tem):
        self.conteiners = []
        self.MAX_CONTEINERS = 5
        # Leitura por tempo: tempo até o 1º conteiner e entre um e outro (ms).
        # AJUSTE medindo no tapete com a velocidade usada no seguidor.
        self.TEMPO_ATE_PRIMEIRO_MS = 800
        self.TEMPO_POR_CONTEINER_MS = 1600
        # Qual sensor do hub 2 olha os conteiners: 0=esq, 1=centro, 2=dir
        self.SENSOR_CONTEINER = 1

        # Comunicação com o hub 2 (sensor HiTechnic dos conteiners).
        # Hub 1 manda "LER;<n>", hub 2 devolve "COR;<n>;<cor>" (hub2.py).
        self.NOME_HUB2 = "ev3dev"       # <-- nome Bluetooth do hub 2
        self.MAILBOX_CONTEINER = "conteiner"
        self.cliente_bt = None
        self.caixa_conteiner = None
        self._num_pedido = 0
        
        # Cor do bloco atual: 
        self.cor_bloco = ''
        
        # Posicionamento: 
        self.linha = 0
        self.coluna = 0

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
        self.motor_dir.run(vel * self.diferenca_dir)

    def andar_tras(self, tempo_ms=700, vel=None):
        if vel is None:
            vel = self.VEL
        self.motor_esq.run(-vel)
        self.motor_dir.run(-vel * self.diferenca_dir)
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
        self.motor_dir.run_angle(self.VEL_GIRO * self.diferenca_dir, 210, wait=True)
        self.parar()
    
    def girar_90_direita(self):
        self.parar()
        wait(50)
        self.motor_esq.run_angle(self.VEL_GIRO, 210, wait=False)
        self.motor_dir.run_angle(-self.VEL_GIRO * self.diferenca_dir, 210, wait=True)
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
        self.motor_dir.run_angle(-vel * self.diferenca_dir, graus, then=Stop.HOLD, wait=True)
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

    # COMUNICAÇÃO COM O HUB 2
    def conectar_hub2(self):
        """Conecta no hub 2 (rode o hub2.py nele antes). Devolve True se conectou."""
        self.ev3.screen.print("Conectando hub 2")
        try:
            self.cliente_bt = BluetoothMailboxClient()
            self.caixa_conteiner = TextMailbox(self.MAILBOX_CONTEINER, self.cliente_bt)
            self.cliente_bt.connect(self.NOME_HUB2)
        except OSError:
            self.caixa_conteiner = None
            self.ev3.screen.print("Hub 2 FALHOU")
            self.ev3.speaker.beep(300, 500)
            return False
        self.ev3.screen.print("Hub 2 OK!")
        self.ev3.speaker.beep(1000, 100)
        return True

    def _cor_do_conteiner(self, resposta_hub2):
        """Pega, da resposta "esq,centro,dir" do hub 2, a cor do sensor dos conteiners."""
        partes = resposta_hub2.split(",")
        if len(partes) == 1:
            return partes[0]
        if self.SENSOR_CONTEINER < len(partes):
            return partes[self.SENSOR_CONTEINER]
        return "erro"

    def leitura_conteiners(self, vel=250, kp=60):
        """Segue o LIMIAR verde|amarelo (S3 no verde, S4 no amarelo) até ver
        vermelho, lendo os conteiners pelo hub 2 POR TEMPO.

        Seguidor (proporcional simples):
          S3 verde   + S4 amarelo -> no limiar: reto
          S3 verde   + S4 verde   -> saiu p/ esquerda: vira à direita
          S3 amarelo + S4 amarelo -> entrou no amarelo: vira à esquerda
          qualquer outra leitura  -> mantém a última correção

        Leitura por tempo: depois de TEMPO_ATE_PRIMEIRO_MS, cada janela de
        TEMPO_POR_CONTEINER_MS é uma posição (1..5). A cor que mais apareceu
        na janela é a do conteiner; se nenhuma cor apareceu, fica "vazio".
        Posições não alcançadas (vermelho antes) também ficam "vazio".
        """
        IGNORAR = ("vazio", "erro", "None", "")
        erro = 0
        self.conteiners = []
        votos = {}                   # cor -> quantas leituras na janela atual
        pedido_pendente = None
        hora_pedido = 0
        relogio = StopWatch()
        cores = []

        def fechar_janela():
            if votos:
                cor = max(votos, key=votos.get)
            else:
                cor = "vazio"
            self.conteiners.append(cor)
            print("Posicao", len(self.conteiners), ":", cor, votos)
            votos.clear()

        while True:
            cores = self.ler_cores()
            c3, c4 = cores[2], cores[3]

            if "vermelho" in cores:
                break

            # ---------- Seguidor do limiar ----------
            if c3 == "verde" and c4 == "amarelo":
                erro = 0
            elif c3 == "verde" and c4 == "verde":
                erro = 1
            elif c3 == "amarelo" and c4 == "amarelo":
                erro = -1
            # senão: mantém o erro anterior

            correcao = kp * erro   # > 0 = vira à direita
            self.motor_esq.run(vel + correcao)
            self.motor_dir.run(vel - correcao)

            # ---------- Janela de tempo da posição atual ----------
            t = relogio.time() - self.TEMPO_ATE_PRIMEIRO_MS
            if t >= 0 and len(self.conteiners) < self.MAX_CONTEINERS:
                posicao = int(t // self.TEMPO_POR_CONTEINER_MS)   # 0..4
                while len(self.conteiners) < posicao and len(self.conteiners) < self.MAX_CONTEINERS:
                    fechar_janela()

            # ---------- Hub 2: pedir / receber a cor ----------
            if self.caixa_conteiner is not None:
                try:
                    if pedido_pendente is None:
                        self._num_pedido += 1
                        pedido_pendente = self._num_pedido
                        hora_pedido = relogio.time()
                        self.caixa_conteiner.send("LER;%d" % pedido_pendente)
                    else:
                        esperado = "COR;%d;" % pedido_pendente
                        resposta = self.caixa_conteiner.read()
                        if resposta and resposta.startswith(esperado):
                            pedido_pendente = None
                            cor = self._cor_do_conteiner(resposta[len(esperado):])
                            # só conta se já estiver dentro de uma janela
                            if (t >= 0 and len(self.conteiners) < self.MAX_CONTEINERS
                                    and cor not in IGNORAR):
                                votos[cor] = votos.get(cor, 0) + 1
                        elif relogio.time() - hora_pedido > 1000:
                            pedido_pendente = None
                except OSError:
                    pass

            wait(5)

        self.parar()

        # Fecha a janela em andamento e completa as posições que faltaram
        if relogio.time() >= self.TEMPO_ATE_PRIMEIRO_MS and len(self.conteiners) < self.MAX_CONTEINERS:
            fechar_janela()
        while len(self.conteiners) < self.MAX_CONTEINERS:
            self.conteiners.append("vazio")

        print("Conteiners:", self.conteiners)
        return cores

    def melhor_escolha(self): 
        cor_bloco = self.cor_bloco
        posicao = 0
        linha = self.linha
        
        # Posição do conteiner da cor do cubo na lista (0 = primeiro lido)
        if cor_bloco in self.conteiners:
            posicao = self.conteiners.index(cor_bloco)
        
        decisao = linha - posicao
        if decisao >= 0: return 'esquerda'
        elif decisao < 0: return 'direita'
    