#!/usr/bin/env pybricks-micropython
from z_robo_mestre import RoboMestre

if __name__ == "__main__":#
    robo = RoboMestre()
    robo.ev3.speaker.beep()
    robo.mapa_rgb(5)
    robo.ev3.speaker.beep()