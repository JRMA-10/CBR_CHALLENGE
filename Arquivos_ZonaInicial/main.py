#!/usr/bin/env pybricks-micropython
from pybricks.tools import wait, StopWatch
from funcoes import Funcoes

def sensor_extremo(cores, cor):
    if cores[0] == cor or cores[1] == cor: return 0
    if cores[2] == cor or cores[3] == cor: return 3
    return -1

def avancar_ate(es, cor, vel=None):
    """Vai para frente enquanto nenhum sensor vê a cor.
    Devolve 0 (viu à esquerda) ou 3 (viu à direita)."""
    sensor = sensor_extremo(es.ler_cores(), cor)
    while sensor == -1:
        es.andar_frente(vel)
        wait(10)
        sensor = sensor_extremo(es.ler_cores(), cor)
    es.parar()
    return sensor
        
def seguir_ate_vermelho(es, alinhar=True, tempo_limite_ms=15000):
    relogio = StopWatch()
    while relogio.time() < tempo_limite_ms:
        cores = es.ler_cores()

        if "vermelho" in cores:
            es.parar()
            sensor_inf = sensor_extremo(cores, "vermelho")
            if alinhar and sensor_inf != -1:
                es.alinhar_extremos("vermelho", sensor_inf, tempo_limite_ms=4000)
            es.ev3.speaker.beep(1200, 400)
            return True

        if "azul" in cores or "amarelo" in cores:
            cor_borda = "azul" if "azul" in cores else "amarelo"
            lado_borda = "esquerda" if (cores[0] == cor_borda or cores[1] == cor_borda) else "direita"
            print("Borda", cor_borda, "a", lado_borda, ". Corrigindo...")
            continue

        es.andar_frente()
        wait(10)

    es.parar()
    print("Vermelho nao encontrado no tempo limite.")
    return False


def ir_para_vermelho(es, proximo_estado):
    """Manda a máquina para o ESTADO_AVANCO_VERMELHO e diz para qual
    estado ir depois de chegar no vermelho."""
    es.estado_apos_vermelho = proximo_estado
    es.estado_atual = es.ESTADO_AVANCO_VERMELHO


def main():
    es = Funcoes()

    es.ev3.screen.clear()
    es.ev3.screen.print("Etapa 1 Iniciada")
    es.ev3.speaker.beep(600, 100)
    print("Iniciando maquina de estados da Etapa 1 com calibração JSON...")
    es.conectar_hub2()

    # Estado para onde ir depois que o ESTADO_AVANCO_VERMELHO achar o vermelho
    es.estado_apos_vermelho = es.ESTADO_VERMELHO_DETECTADO

    while True:
        cores = es.ler_cores()
        c0, c3 = cores[0], cores[3]

        viu_azul = "azul" in cores
        viu_amarelo = "amarelo" in cores
        viu_vermelho = "vermelho" in cores

        if es.estado_atual == es.ESTADO_BUSCA_VERDE:
            if viu_azul or viu_amarelo:
                es.parar()
                es.ev3.speaker.beep(400, 400)
                wait(500)

                cor_alvo = "azul" if viu_azul else "amarelo"

                sensor_inf = -1
                if c0 == cor_alvo:
                    sensor_inf = 0
                elif c3 == cor_alvo:
                    sensor_inf = 3

                if sensor_inf != -1:
                    es.alinhar_extremos(cor_alvo, sensor_inf, tempo_limite_ms=4000)

                es.andar_tras()

                if viu_azul:
                    es.girar_90_esquerda()
                else:
                    es.girar_90_direita()

                wait(500)
                ir_para_vermelho(es, es.ESTADO_VERMELHO_DETECTADO)
                print("Transicao: Movendo em direcao à linha vermelha.")

            elif viu_vermelho:
                es.alinhar_extremos("vermelho", 0 if c0 == "vermelho" else 3, tempo_limite_ms=4000)
                es.andar_tras(300)
                es.girar_90_esquerda()
                es.andar_frente()
                es.estado_atual = es.ESTADO_VERMELHO_DETECTADO

            else:
                # Vendo verde ou nada: segue em frente
                es.andar_frente()

        elif es.estado_atual == es.ESTADO_AVANCO_VERMELHO:
            # Reutilizável: para usar de outro estado, chame
            #   ir_para_vermelho(es, <estado depois do vermelho>)
            if seguir_ate_vermelho(es):
                print("Vermelho encontrado -> estado", es.estado_apos_vermelho)
                es.estado_atual = es.estado_apos_vermelho
            else:
                break

        elif es.estado_atual == es.ESTADO_VERMELHO_DETECTADO:
            es.andar_tras(500)
            wait(100)
            es.girar_90_esquerda()

            sensor_amarelo = avancar_ate(es, "amarelo", vel=300)

            if sensor_amarelo != -1:
                es.alinhar_extremos("amarelo", sensor_amarelo, tempo_limite_ms=4000)
                es.andar_frente_tempo(200)
                es.girar_90_esquerda()
                es.estado_atual = es.ESTADO_LEITURA_CONTEINERS
                es.ev3.speaker.beep(800, 300)
            else:
                print("Amarelo nao encontrado. Encerrando.")
                es.ev3.speaker.beep(200, 600)
                break

        elif es.estado_atual == es.ESTADO_LEITURA_CONTEINERS:
            cores_fim = es.leitura_conteiners(vel=250, kp=60)

            sensor_verm = sensor_extremo(cores_fim, "vermelho")
            if sensor_verm != -1:
                es.alinhar_extremos("vermelho", sensor_verm, tempo_limite_ms=4000)

            es.andar_tras(300)
            es.girar_90_esquerda()

            sensor_azul = avancar_ate(es, "azul", vel=300)
            if sensor_azul != -1:
                es.alinhar_extremos("azul", sensor_azul, tempo_limite_ms=4000)

            break

        elif es.estado_atual == es.ESTADO_ENTREGA_CUBOS: 
            # 1. Anda até ver o verde e alinha nele
            sensor_verde = avancar_ate(es, 'verde', 300)
            if sensor_verde != -1:
                es.alinhar_extremos('verde', sensor_verde, tempo_limite_ms=4000)

            # 2. Ré
            es.andar_tras()

            # 3. Gira para o lado indicado pela estratégia
            lado = es.melhor_escolha()
            print("Entrega: cubo", es.cor_bloco, "-> girando para", lado)
            if lado == 'esquerda':
                es.girar_90_esquerda()
            else:
                es.girar_90_direita()

            # 4. Percorre o limiar verde/amarelo (para ao ver vermelho)
            es.leitura_conteiners()

            es.parar()
            break
        
        wait(15)


    es.parar()

    # Mostra na tela do hub as cores dos conteiners, na ordem em que foram lidos
    es.ev3.screen.clear()
    es.ev3.screen.print("CONTEINERS:")
    if not es.conteiners:
        es.ev3.screen.print("nenhum lido")
    for i, cor in enumerate(es.conteiners[:7], 1):
        es.ev3.screen.print("%d %s" % (i, cor))
    print("Conteiners:", es.conteiners)
    es.ev3.speaker.beep(1200, 150)

    # Mantém a tela até apertar um botão (senão o programa fecha e apaga)
    while not es.ev3.buttons.pressed():
        wait(100)

main()