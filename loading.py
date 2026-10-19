"""
loading.py  -  Pantalla de carga de Geeckz (gato alien + nombre de la marca)

Necesita el archivo  geeckz.png  en la misma carpeta (si no esta, muestra solo el nombre).

PRUEBA RAPIDA (Pydroid):  abre este archivo y dale Run -> carga falsa de ~7 s. Toca para salir.

USO EN EL JUEGO:
    import loading
    loading.run(mi_funcion_de_carga)     # mi_funcion_de_carga(report) llama report(0.0..1.0, "texto")
"""
import pygame
import os
import sys
import time
import threading

BG = (18, 32, 33)
BAR_X0, BAR_X1 = 0.25, 0.75          # barra: de 25% a 75% del ancho de la imagen
BAR_Y, BAR_H = 650 / 720.0, 12 / 720.0


class LoadingScreen:
    def __init__(self, title="Geeckz", screen=None):
        if not pygame.get_init():
            pygame.init()
        if not pygame.font.get_init():
            pygame.font.init()
        if screen is None:
            try:
                screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            except Exception:
                screen = pygame.display.set_mode((960, 540))
        self.screen = screen
        self.sw, self.sh = screen.get_size()
        self.title = title
