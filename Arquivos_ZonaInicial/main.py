#!/usr/bin/env pybricks-micropython
from pybricks.tools import wait, StopWatch
from classes import Estrategia


def sensor_extremo(cores, cor):
    """Devolve 0 (lado esquerdo) ou 3 (lado direito) conforme quem viu a cor; -1 se ninguém."""
    if cores[0] == cor or cores[1] == cor:
        return 0
    if cores[2] == cor or cores[3] == cor:
        return 3
    return -1


def avancar_ate(es, cor, vel=300, tempo_limite_ms=6000):
    """Anda para frente lendo os sensores até ver a cor. Devolve 0/3 ou -1 se não achou."""
    relogio = StopWatch()
    sensor = -1
    es.andar_frente(vel)
    while relogio.time() < tempo_limite_ms:
        sensor = sensor_extremo(es.ler_cores(), cor)
        if sensor != -1:
            break
    es.parar()
    return sensor

def corrigir_borda(es, cor_borda, lado_borda):
    """Gira para longe da borda (azul/amarelo) que apareceu no caminho."""
    es.parar()
    sinal = 1 if lado_borda == "esquerda" else -1   # +1 = vira à direita
    indices = (0, 1) if lado_borda == "esquerda" else (2, 3)
    es.motor_esq.reset_angle(0)
    while abs(es.motor_esq.angle()) < 120:   # ~ limite de correção
        ainda_ve = any(es.identificar_cor(i, es.sensores[i].rgb()) == cor_borda for i in indices)
        if not ainda_ve and abs(es.motor_esq.angle()) > 30:
            break
        es.motor_esq.run(sinal * 150)
        es.motor_dir.run(-sinal * 150)
        wait(10)
    es.parar()


def seguir_ate_vermelho(es, alinhar=True, tempo_limite_ms=15000):
    """
    REUTILIZÁVEL: anda para frente até o vermelho, desviando das bordas
    azul/amarelo no caminho, e (opcional) alinha no vermelho.
    Pode ser chamada de qualquer estado. Devolve True se achou o vermelho.
    """
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
            corrigir_borda(es, cor_borda, lado_borda)
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
    es = Estrategia()

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

            sensor_amarelo = avancar_ate(es, "amarelo", vel=300, tempo_limite_ms=6000)

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

            sensor_azul = avancar_ate(es, "azul", vel=300, tempo_limite_ms=6000)
            if sensor_azul != -1:
                es.alinhar_extremos("azul", sensor_azul, tempo_limite_ms=4000)

            break

        elif es.estado_atual == es.ESTADO_ENTREGA_CUBOS: 
            # 1. Anda até ver o verde e alinha nele
            sensor_verde = avancar_ate(es, 'verde', 300, 6000)
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