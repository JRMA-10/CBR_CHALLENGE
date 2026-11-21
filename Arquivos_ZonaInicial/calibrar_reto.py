#!/usr/bin/env pybricks-micropython
# Mede a proporcao REAL entre as rodas (diferenca_dir).
#   1. Coloque o robo no chao, encostado numa regua/parede reta.
#   2. Aperte CENTRO: os motores ficam soltos e os encoders zeram.
#   3. EMPURRE o robo com a mao, bem RETO, por ~1 metro.
#   4. Aperte CENTRO de novo: a tela mostra o diferenca_dir certo.
#   Repita 2-3 vezes e use a media em classes.py (self.diferenca_dir).
from pybricks.hubs import EV3Brick
from pybricks.ev3devices import Motor
from pybricks.parameters import Port, Button
from pybricks.tools import wait

ev3 = EV3Brick()
motor_esq = Motor(Port.C)
motor_dir = Motor(Port.D)


def esperar_centro():
    while Button.CENTER not in ev3.buttons.pressed():
        wait(10)
    while Button.CENTER in ev3.buttons.pressed():
        wait(10)


while True:
    ev3.screen.clear()
    ev3.screen.print("CENTRO e empurre")
    ev3.screen.print("o robo RETO")
    esperar_centro()

    motor_esq.stop()     # solta os motores (giram livres)
    motor_dir.stop()
    motor_esq.reset_angle(0)
    motor_dir.reset_angle(0)
    ev3.speaker.beep(800, 100)

    ev3.screen.clear()
    ev3.screen.print("Empurrando...")
    ev3.screen.print("CENTRO p/ medir")
    esperar_centro()

    a_esq = motor_esq.angle()
    a_dir = motor_dir.angle()
    ev3.screen.clear()
    ev3.screen.print("esq:", a_esq)
    ev3.screen.print("dir:", a_dir)
    if a_esq != 0:
        razao = a_dir / a_esq
        ev3.screen.print("diferenca_dir =")
        ev3.screen.print("%.3f" % razao)
        print("esq", a_esq, "dir", a_dir, "diferenca_dir =", razao)
    else:
        ev3.screen.print("esq nao girou")
    ev3.speaker.beep(1200, 200)
    ev3.screen.print("CENTRO: de novo")
    esperar_centro()
