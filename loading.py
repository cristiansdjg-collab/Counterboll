"""
loading.py  -  Pantalla de carga animada para ATTACK ON THE ALIENS

Una navecita vuela tocando planetas (puntitos) y la barra de carga es un RAYO
con caritas de marcianitos que se van encendiendo.

PRUEBA RAPIDA (Pydroid):  abre este archivo y dale Run -> corre una carga falsa de ~7 s.
Toca la pantalla o pulsa una tecla para salir.

USO EN EL JUEGO (despues):
    import loading
    loading.run(mi_funcion_de_carga, title="ATTACK ON THE ALIENS")
    # mi_funcion_de_carga(report) hace el trabajo pesado y llama report(0.0..1.0, "texto")
"""
import pygame
import math
import random
import sys
import time
import threading

LOGICAL_H = 360          # el dibujo se hace a baja resolucion y se escala (rinde mejor)

# ---------------------------------------------------------------- sprites de marcianitos (8x8)
# X = cuerpo, E = ojos, M = boca
ALIENS = [
    [".X....X.",
     "..X..X..",
     ".XXXXXX.",
     "XXXXXXXX",
     "XEEXXEEX",
     "XXXXXXXX",
     ".XMMMMX.",
     "..XXXX.."],
    ["..X..X..",
     "...XX...",
     "..XXXX..",
     ".XXXXXX.",
     "XEXXXXEX",
     "XXXXXXXX",
     ".X.XX.X.",
     "X.X..X.X"],
    ["..XXXX..",
     ".XXXXXX.",
     "XXXXXXXX",
     "XXXEEXXX",
     "XXXEEXXX",
     "XXXXXXXX",
     ".XMMMMX.",
     "X.X..X.X"],
]
ALIEN_COLORS = [(120, 255, 110), (255, 120, 220), (255, 220, 80), (110, 220, 255), (255, 150, 70)]
PLANET_COLORS = [(0, 240, 255), (255, 150, 30), (210, 100, 255), (120, 200, 255),
                 (120, 230, 90), (255, 80, 200), (255, 210, 60), (255, 70, 90)]


def _alien_surf(rows, color, scale=2, dim=False):
    h, w = len(rows), len(rows[0])
    s = pygame.Surface((w * scale, h * scale), pygame.SRCALPHA)
    body = (62, 66, 92) if dim else color
    eye = (30, 32, 50) if dim else (15, 10, 40)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == ".":
                continue
            c = body if ch == "X" else eye
            pygame.draw.rect(s, c, (x * scale, y * scale, scale, scale))
    return s


def _glow(color, r):
    s = pygame.Surface((r * 2, r * 2))
    for i in range(r, 0, -1):
        k = (1.0 - i / float(r)) ** 2 * 0.9
        pygame.draw.circle(s, (int(color[0] * k), int(color[1] * k), int(color[2] * k)), (r, r), i)
    return s


def _rot(pts, ang, cx, cy):
    ca, sa = math.cos(ang), math.sin(ang)
    return [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]


class LoadingScreen:
    def __init__(self, title="ATTACK ON THE ALIENS", screen=None):
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
        sw, sh = screen.get_size()
        self.H = LOGICAL_H
        self.W = int(round(self.H * sw / float(sh)))
        self.canvas = pygame.Surface((self.W, self.H))
        self.title = title
        self.clock = pygame.time.Clock()
        self.t = 0
        self.rng = random.Random()

        self.font_big = pygame.font.Font(None, 30)
        self.font_med = pygame.font.Font(None, 22)
        self.font_small = pygame.font.Font(None, 16)

        # progreso
        self.target = 0.0
        self.shown = 0.0
        self.text = ""

        # fondo: estrellas en 3 capas
        self.stars = [[self.rng.uniform(0, self.W), self.rng.uniform(0, self.H),
                       self.rng.choice((0.3, 0.6, 1.1))] for _ in range(70)]

        # brillos cacheados
        self.glows = {}
        # marcianitos (apagado / encendido)
        self.alien_on, self.alien_off = [], []
        for i in range(6):
            rows = ALIENS[i % len(ALIENS)]
            col = ALIEN_COLORS[i % len(ALIEN_COLORS)]
            self.alien_on.append(_alien_surf(rows, col, 2))
            self.alien_off.append(_alien_surf(rows, col, 2, dim=True))
        self.alien_fr = [0.07, 0.24, 0.41, 0.58, 0.75, 0.92]      # posicion en la barra (0..1)

        # rayo (camino en zigzag, fijo)
        self.bx0 = int(self.W * 0.09)
        self.bx1 = int(self.W * 0.91)
        self.by = int(self.H * 0.86)
        r = random.Random(11)
        n = max(10, (self.bx1 - self.bx0) // 11)
        self.bolt = []
        for i in range(n + 1):
            x = self.bx0 + (self.bx1 - self.bx0) * i / float(n)
            sgn = 1 if i % 2 == 0 else -1
            if i in (0, n):
                sgn = 0
            self.bolt.append((x, sgn * r.uniform(5, 9)))

        # nave y planetas
        self.ship_y = self.H * 0.35
        self.ship_vy = 0.0
        self.ship_x = self.W * 0.27
        self.tilt = 0.0
        self.planets = []
        self.pops = []         # anillos y chispas al tocar un planeta
        self.trail = []
        self.touched = 0
        self.next_spawn = 0
        for k in range(4):
            self._spawn(self.W * (0.55 + 0.17 * k))

    # ---------------------------------------------------------------- utilidades
    def glow(self, color, r):
        key = (color, r)
        if key not in self.glows:
            self.glows[key] = _glow(color, r)
        return self.glows[key]

    def _spawn(self, x=None):
        if x is None:
            x = self.W + 20
        self.planets.append({"x": x, "y": self.rng.uniform(self.H * 0.17, self.H * 0.58),
                             "r": self.rng.choice((4, 5, 6, 7)),
                             "c": self.rng.choice(PLANET_COLORS), "ph": self.rng.uniform(0, 6.28)})

    def set(self, progress, text=None):
        self.target = max(0.0, min(1.0, progress))
        if text is not None:
            self.text = text

    # ---------------------------------------------------------------- logica
    def update(self):
        self.t += 1
        speed = 1.7 + 1.2 * self.shown                      # va mas rapido al avanzar
        ship_x = self.W * 0.27 + math.sin(self.t * 0.03) * 8

        # progreso suave
        self.shown += (self.target - self.shown) * 0.08
        if self.target >= 1.0 and self.shown > 0.995:
            self.shown = 1.0

        for s in self.stars:
            s[0] -= s[2] * speed
            if s[0] < 0:
                s[0] = self.W
                s[1] = self.rng.uniform(0, self.H)

        # planeta objetivo: el siguiente que aun no pasa de la nave
        tgt = None
        for p in self.planets:
            if p["x"] > ship_x - 4 and (tgt is None or p["x"] < tgt["x"]):
                tgt = p
        goal_y = tgt["y"] if tgt else self.H * 0.35
        acc = (goal_y - self.ship_y) * 0.012 - self.ship_vy * 0.18
        self.ship_vy += acc
        self.ship_y += self.ship_vy
        self.ship_y = max(self.H * 0.1, min(self.H * 0.64, self.ship_y))
        self.tilt = max(-0.6, min(0.6, self.ship_vy * 0.12))
        self.ship_x = ship_x

        for p in self.planets[:]:
            p["x"] -= speed
            if math.hypot(p["x"] - ship_x, p["y"] - self.ship_y) < p["r"] + 9:
                self.touched += 1
                self.pops.append({"x": p["x"], "y": p["y"], "c": p["c"], "t": 0, "kind": "ring"})
                for _ in range(10):
                    a = self.rng.uniform(0, 6.28)
                    v = self.rng.uniform(0.6, 2.4)
                    self.pops.append({"x": p["x"], "y": p["y"], "c": p["c"], "t": 0, "kind": "spark",
                                      "dx": math.cos(a) * v, "dy": math.sin(a) * v})
                self.planets.remove(p)
            elif p["x"] < -20:
                self.planets.remove(p)
        self.next_spawn -= 1
        if self.next_spawn <= 0 and len(self.planets) < 6:
            self._spawn()
            self.next_spawn = int(self.rng.uniform(34, 62) / (speed / 1.7))

        for q in self.pops[:]:
            q["t"] += 1
            if q["kind"] == "spark":
                q["x"] += q["dx"] - speed * 0.5
                q["y"] += q["dy"]
            if q["t"] > (22 if q["kind"] == "ring" else 26):
                self.pops.remove(q)

        # estela de la nave
        self.trail.append([ship_x - 8, self.ship_y, 0])
        for tr in self.trail:
            tr[0] -= speed * 1.2
            tr[2] += 1
        self.trail = [tr for tr in self.trail if tr[2] < 18]

    # ---------------------------------------------------------------- dibujo
    def bolt_points(self, upto=1.0, wobble=True):
        """Puntos del rayo hasta la fraccion 'upto' (0..1) de su largo."""
        xcut = self.bx0 + (self.bx1 - self.bx0) * upto
        pts = []
        for i, (x, dy) in enumerate(self.bolt):
            jit = math.sin(self.t * 0.5 + i * 1.7) * 1.4 if wobble else 0
            y = self.by + dy + jit
            if x >= xcut:
                if pts:
                    x0, y0 = pts[-1]
                    k = (xcut - x0) / max(0.001, x - x0)
                    pts.append((xcut, y0 + (y - y0) * k))
                break
            pts.append((x, y))
        if len(pts) < 2:
            pts = [(self.bx0, self.by), (self.bx0 + 1, self.by)]
        return pts

    def bolt_y_at(self, fr):
        pts = self.bolt_points(1.0, False)
        x = self.bx0 + (self.bx1 - self.bx0) * fr
        for a, b in zip(pts, pts[1:]):
            if a[0] <= x <= b[0]:
                k = (x - a[0]) / max(0.001, b[0] - a[0])
                return a[1] + (b[1] - a[1]) * k
        return self.by

    def draw(self):
        c = self.canvas
        c.fill((7, 6, 22))
        # estrellas
        for x, y, z in self.stars:
            col = int(70 + 130 * z / 1.1)
            c.set_at((int(x), int(y)), (col, col, min(255, col + 30)))
            if z > 1.0:
                c.set_at((int(x) + 1, int(y)), (col // 2, col // 2, col // 2))

        # linea punteada hacia el siguiente planeta
        tgt = None
        for p in self.planets:
            if p["x"] > self.ship_x and (tgt is None or p["x"] < tgt["x"]):
                tgt = p
        if tgt:
            for k in range(1, 9):
                f = k / 9.0
                px = self.ship_x + (tgt["x"] - self.ship_x) * f
                py = self.ship_y + (tgt["y"] - self.ship_y) * f
                if (k + self.t // 4) % 2 == 0:
                    c.set_at((int(px), int(py)), (90, 100, 150))

        # planetas
        for p in self.planets:
            pulse = 1.0 + 0.12 * math.sin(self.t * 0.12 + p["ph"])
            g = self.glow(p["c"], int(p["r"] * 3.2))
            c.blit(g, (int(p["x"] - g.get_width() / 2), int(p["y"] - g.get_height() / 2)), special_flags=pygame.BLEND_ADD)
            pygame.draw.circle(c, p["c"], (int(p["x"]), int(p["y"])), int(p["r"] * pulse))
            pygame.draw.circle(c, (255, 255, 255), (int(p["x"] - p["r"] * 0.3), int(p["y"] - p["r"] * 0.3)), max(1, p["r"] // 3))

        # efectos al tocar
        for q in self.pops:
            if q["kind"] == "ring":
                rr = 6 + q["t"] * 1.1
                a = max(0.0, 1.0 - q["t"] / 22.0)
                col = tuple(int(v * a) for v in q["c"])
                pygame.draw.circle(c, col, (int(q["x"]), int(q["y"])), int(rr), 2)
            else:
                a = max(0.0, 1.0 - q["t"] / 26.0)
                col = tuple(int(v * a) for v in q["c"])
                pygame.draw.rect(c, col, (int(q["x"]), int(q["y"]), 2, 2))

        # estela
        for x, y, age in self.trail:
            a = 1.0 - age / 18.0
            pygame.draw.circle(c, (int(255 * a), int(150 * a), int(40 * a)), (int(x), int(y)), max(1, int(3 * a)))

        # nave
        sx, sy, ang = self.ship_x, self.ship_y, self.tilt
        flame = 5 + (self.t // 2) % 3 * 2
        c_flame = _rot([(-6, -2), (-6 - flame, 0), (-6, 2)], ang, sx, sy)
        pygame.draw.polygon(c, (255, 190, 60), c_flame)
        wing = _rot([(2, -3), (-7, -8), (-5, -2), (-5, 2), (-7, 8), (2, 3)], ang, sx, sy)
        pygame.draw.polygon(c, (40, 110, 200), wing)
        body = _rot([(11, 0), (1, -4), (-6, -3), (-6, 3), (1, 4)], ang, sx, sy)
        pygame.draw.polygon(c, (0, 230, 255), body)
        pygame.draw.polygon(c, (10, 10, 40), body, 1)
        cx, cy = _rot([(3, 0)], ang, sx, sy)[0]
        pygame.draw.circle(c, (255, 255, 255), (int(cx), int(cy)), 2)

        # titulo
        ts = self.font_big.render(self.title, False, (255, 255, 255))
        sh = self.font_big.render(self.title, False, (40, 10, 90))
        c.blit(sh, sh.get_rect(center=(self.W // 2 + 1, int(self.H * 0.07) + 1)))
        c.blit(ts, ts.get_rect(center=(self.W // 2, int(self.H * 0.07))))

        # texto CARGANDO + porcentaje
        dots = "." * (1 + (self.t // 15) % 3)
        lt = self.font_med.render("CARGANDO" + dots, False, (230, 235, 255))
        c.blit(lt, (self.bx0, int(self.H * 0.69)))
        pt = self.font_med.render("%d%%" % int(self.shown * 100 + 0.5), False, (255, 230, 90))
        c.blit(pt, pt.get_rect(topright=(self.bx1, int(self.H * 0.69))))
        if self.text:
            tt = self.font_small.render(self.text, False, (140, 150, 190))
            c.blit(tt, (self.bx0, int(self.H * 0.69) + 19))

        # ---- BARRA: rayo ----
        full = self.bolt_points(1.0, False)
        pygame.draw.lines(c, (30, 32, 56), False, full, 5)               # riel apagado
        pygame.draw.lines(c, (60, 64, 96), False, full, 1)
        if self.shown > 0.002:
            pts = self.bolt_points(self.shown, True)
            glow_col = (255, 200, 40)
            pygame.draw.lines(c, (120, 80, 10), False, pts, 9)
            pygame.draw.lines(c, glow_col, False, pts, 5)
            pygame.draw.lines(c, (255, 250, 200), False, pts, 2)
            # chispas en la punta
            tx, ty = pts[-1]
            g = self.glow((255, 220, 90), 16)
            c.blit(g, (int(tx - 16), int(ty - 16)), special_flags=pygame.BLEND_ADD)
            for _ in range(3):
                a = self.rng.uniform(0, 6.28)
                L = self.rng.uniform(4, 11)
                pygame.draw.line(c, (255, 255, 210), (tx, ty), (tx + math.cos(a) * L, ty + math.sin(a) * L), 1)

        # marcianitos sobre el rayo
        for i, fr in enumerate(self.alien_fr):
            ax = self.bx0 + (self.bx1 - self.bx0) * fr
            ay = self.bolt_y_at(fr)
            on = self.shown >= fr
            surf = self.alien_on[i] if on else self.alien_off[i]
            bob = int(math.sin(self.t * 0.15 + i) * 2) if on else 0
            r = surf.get_rect(center=(int(ax), int(ay) + bob))
            pygame.draw.circle(c, (14, 12, 34), r.center, 11)
            pygame.draw.circle(c, ALIEN_COLORS[i % len(ALIEN_COLORS)] if on else (50, 54, 80), r.center, 11, 1)
            c.blit(surf, r)
            if on:
                g = self.glow(ALIEN_COLORS[i % len(ALIEN_COLORS)], 14)
                c.blit(g, (r.centerx - 14, r.centery - 14), special_flags=pygame.BLEND_ADD)

    def present(self):
        sw, sh = self.screen.get_size()
        k = min(sw / float(self.W), sh / float(self.H))
        vw, vh = int(self.W * k), int(self.H * k)
        self.screen.fill((0, 0, 0))
        self.screen.blit(pygame.transform.scale(self.canvas, (vw, vh)), ((sw - vw) // 2, (sh - vh) // 2))
        pygame.display.flip()

    def frame(self):
        """Un cuadro completo (logica + dibujo + pantalla). Devuelve False si se pidio salir."""
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
        self.update()
        self.draw()
        self.present()
        self.clock.tick(60)
        return True

    def fade_out(self, frames=25):
        for i in range(frames):
            self.frame()
            ov = pygame.Surface((self.W, self.H))
            ov.set_alpha(int(255 * (i + 1) / frames))
            self.canvas.blit(ov, (0, 0))
            self.present()


# ---------------------------------------------------------------- API para el juego
def run(task, title="ATTACK ON THE ALIENS", screen=None, fade=True):
    """Muestra la pantalla de carga animada mientras 'task(report)' trabaja en otro hilo.
    report(progreso 0..1, texto) actualiza la barra. Al terminar, la pantalla se oscurece y regresa."""
    ls = LoadingScreen(title, screen)
    box = {"err": None, "done": False}

    def report(p, text=""):
        ls.set(p, text)

    def worker():
        try:
            task(report)
        except BaseException as ex:             # se re-lanza en el hilo principal
            box["err"] = ex
        box["done"] = True

    th = threading.Thread(target=worker, daemon=True)
    th.start()
    while True:
        if not ls.frame():
            break
        if box["done"]:
            ls.set(1.0)
            if ls.shown >= 1.0:
                break
    if fade:
        ls.fade_out()
    if box["err"] is not None:
        raise box["err"]
    return ls.screen


# ---------------------------------------------------------------- prueba (Pydroid)
def _fake_task(report):
    steps = ["Generando sonidos", "Dibujando naves", "Creando planetas", "Preparando jefes",
             "Cargando musica", "Casi listo"]
    n = len(steps)
    for i, name in enumerate(steps):
        report(i / float(n), name)
        for k in range(10):
            time.sleep(0.12)
            report((i + (k + 1) / 10.0) / n, name)
    report(1.0, "Listo")


if __name__ == "__main__":
    pygame.init()
    run(_fake_task)
    pygame.quit()
    sys.exit()
