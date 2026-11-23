#!/usr/bin/env pybricks-micropython
# Teste do seguidor de limiar (PID) + comunicacao com o hub 2.
#   1. Rode o hub2.py no hub 2.
#   2. Rode este arquivo no hub 1 e espere "Hub 2 OK!".
#   3. Coloque o robo com S3 no verde e S4 no amarelo e aperte o botao do CENTRO.
#   O robo segue o limiar ate ver vermelho e mostra os conteiners lidos.
from pybricks.parameters import Button
from pybricks.tools import wait
from funcoes import Funcoes

VEL = 250   # velocidade base
KP = 60     # forca da correcao

es = Funcoes()

es.ev3.screen.clear()
es.conectar_hub2()   # se falhar, o PID roda mesmo assim (sem ler conteiners)

es.ev3.screen.print("CENTRO p/ iniciar")
while Button.CENTER not in es.ev3.buttons.pressed():
    wait(10)
while Button.CENTER in es.ev3.buttons.pressed():
    wait(10)

es.ev3.screen.clear()
es.ev3.screen.print("Seguindo...")
cores_fim = es.leitura_conteiners(vel=VEL, kp=KP)

es.ev3.screen.clear()
es.ev3.screen.print("Fim:", cores_fim)
es.ev3.screen.print("Lidos:", len(es.conteiners))
for c in es.conteiners:
    es.ev3.screen.print(c)
print("Cores no fim:", cores_fim)
print("Conteiners:", es.conteiners)
es.ev3.speaker.beep(800, 300)
wait(10000)
