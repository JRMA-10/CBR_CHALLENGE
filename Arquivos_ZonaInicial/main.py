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
    while relogio.time() < tempo_limite_ms:
        sensor = sensor_extremo(es.ler_cores(), cor)
        if sensor != -1:
            break
        es.andar_frente(vel)
        wait(10)
    es.parar()
    return sensor


def main():
    es = Estrategia()

    es.ev3.screen.clear()
    es.ev3.screen.print("Etapa 1 Iniciada")
    es.ev3.speaker.beep(600, 100)
    print("Iniciando maquina de estados da Etapa 1 com calibração JSON...")

    # Guardados entre voltas do loop (usados no ESTADO_ALINHAMENTO)
    cor_borda = None
    lado_borda = None

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
                es.estado_atual = es.ESTADO_AVANCO_VERMELHO
                print("Transicao: Movendo em direcao à linha vermelha.")

            elif viu_vermelho:
                es.alinhar_extremos("vermelho", 0 if c0 == "vermelho" else 3, tempo_limite_ms=4000)
                es.andar_tras(300)
                es.girar_90_esquerda()
                es.andar_frente()

            else:
                # Vendo verde ou nada: segue em frente
                es.andar_frente()

        elif es.estado_atual == es.ESTADO_AVANCO_VERMELHO:
            es.andar_frente()

            if viu_vermelho:
                es.parar()
                sensor_inf = 0 if c0 == "vermelho" else (3 if c3 == "vermelho" else -1)
                if sensor_inf != -1:
                    es.alinhar_extremos("vermelho", sensor_inf, tempo_limite_ms=4000)

                es.ev3.speaker.beep(1200, 400)
                print("Linha vermelha encontrada! Fim da Etapa 1.")
                es.estado_atual = es.ESTADO_VERMELHO_DETECTADO

            elif viu_azul or viu_amarelo:
                # Guarda AGORA qual lado viu a borda
                cor_borda = "azul" if viu_azul else "amarelo"
                lado_borda = "esquerda" if (cores[0] == cor_borda or cores[1] == cor_borda) else "direita"
                print("Borda", cor_borda, "a", lado_borda, ". Corrigindo...")
                es.estado_atual = es.ESTADO_ALINHAMENTO

        elif es.estado_atual == es.ESTADO_ALINHAMENTO:
            for v in (es.VEL // 2, es.VEL // 4):
                es.andar_frente(v)
                wait(60)
            es.parar()

            es._recuar_suave(90, vel=150)
            sinal = 1 if lado_borda == "esquerda" else -1   # +1 = vira à direita
            indices = (0, 1) if lado_borda == "esquerda" else (2, 3)
            es.motor_esq.reset_angle(0)
            while abs(es.motor_esq.angle()) < 120:   # ~ limite de correção
                ainda_ve = any(es.identificar_cor(i, es.sensores[i].rgb()) == cor_borda for i in indices)
                if not ainda_ve and abs(es.motor_esq.angle()) > 30: break
                es.motor_esq.run(sinal * 150)
                es.motor_dir.run(-sinal * 150)
                wait(10)
            es.parar()

            es.estado_atual = es.ESTADO_AVANCO_VERMELHO

        elif es.estado_atual == es.ESTADO_VERMELHO_DETECTADO:
            es.andar_tras(700)
            wait(100)
            es.girar_90_esquerda()

            sensor_amarelo = avancar_ate(es, "amarelo", vel=300, tempo_limite_ms=6000)

            if sensor_amarelo != -1:
                es.alinhar_extremos("amarelo", sensor_amarelo, tempo_limite_ms=4000)
                es.andar_frente_tempo(370)
                es.girar_90_esquerda()
                es.estado_atual = es.ESTADO_LEITURA_CONTEINERS
                es.ev3.speaker.beep(800, 300)
            else:
                print("Amarelo nao encontrado. Encerrando.")
                es.ev3.speaker.beep(200, 600)
                break

        elif es.estado_atual == es.ESTADO_LEITURA_CONTEINERS:
            cores_fim = es.leitura_conteiners(vel=400, correcao_max=25, passo=15, suavizacao=0.7, tempo_limite_ms=9200, parar_em="vermelho")

            sensor_verm = sensor_extremo(cores_fim, "vermelho")
            if sensor_verm != -1:
                es.alinhar_extremos("vermelho", sensor_verm, tempo_limite_ms=4000)

            es.andar_tras(300)
            es.girar_90_esquerda()

            sensor_azul = avancar_ate(es, "azul", vel=300, tempo_limite_ms=6000)
            if sensor_azul != -1:
                es.alinhar_extremos("azul", sensor_azul, tempo_limite_ms=4000)

            break

        wait(15)

    es.parar()

main()