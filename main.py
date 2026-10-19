import pygame
import math
import random
import sys
import traceback
import os
import json
import time
from array import array

# =====================================================================
#  ATTACK ON THE ALIENS  -  v1.15: cada nivel tiene 3 PARTES (con animación entre partes) y al terminar se oscurece y vuelve al mapa; sectores 5-8 con 6/7/9/10 niveles.
#  (antes v1.14: LORE en el modo historia (prólogo, texto de cada sector, diálogo de cada boss, victorias y epílogo).
#  (antes v1.13: pantalla que se adapta/centra en cualquier dispositivo, AJUSTES (engrane): volumen de música y
#  efectos, transparencia y posición de los controles; música distinta para menú, selección, combate y cada BOSS.
#  (antes v1.12.1: opción ELIMINAR perfil (con su progreso, monedas y mejoras) en la pantalla de perfil.
#  (antes v1.12: HISTORIA con 8 sectores y 8 BOSSES distintos (dificultad creciente), INFINITO con boss al azar cada 50 puntos.
#  (antes v1.11.4: gráficos mejorados (luces/brillos, rotación suave,
#  explosiones, planetas con volumen, viñeta, temblor de pantalla) y rendimiento
#  (calidad automática según los FPS, fondo en caché, menos partículas si va lento)
#
#  El juego se dibuja a baja resolución (LOGICAL_H) y se escala a la
#  pantalla completa: da el look pixel-art real y rinde MUCHO mejor.
#    - Si aún va lento -> LOGICAL_H = 270
#    - Si lo quieres más nítido -> LOGICAL_H = 450
# =====================================================================
LOGICAL_H = 360


def _log_exc(exc_type, exc, tb):
    try:
        with open("error_log.txt", "w") as f:
            traceback.print_exception(exc_type, exc, tb, file=f)
    except Exception:
        pass
    traceback.print_exception(exc_type, exc, tb)
    print("El juego falló. Revisa el archivo 'error_log.txt'")


sys.excepthook = _log_exc

try:
    pygame.mixer.pre_init(22050, -16, 1, 512)
except Exception:
    pass
pygame.init()
pygame.display.init()
pygame.font.init()

screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)


def _cur_size():
    try:
        s = pygame.display.get_surface()
        if s is not None:
            w, h = s.get_size()
            if w > 0 and h > 0:
                return w, h
    except Exception:
        pass
    return 0, 0


def _wait_stable_size(max_ms=1600):
    """En algunos móviles/tablets el tamaño de la ventana cambia justo al arrancar (barras del sistema,
    rotación...). Se espera a que se estabilice para no quedar descentrado ni con una franja negra."""
    t0 = pygame.time.get_ticks()
    last, same = None, 0
    while pygame.time.get_ticks() - t0 < max_ms:
        pygame.event.pump()
        cur = _cur_size()
        if cur == last and cur[0] > 0:
            same += 1
        else:
            same, last = 0, cur
        landscape = cur[0] >= cur[1]
        if same >= 8 and (landscape or pygame.time.get_ticks() - t0 > max_ms * 0.7):
            break
        pygame.time.wait(40)


_wait_stable_size()
SW, SH = _cur_size()
if SW == 0 or SH == 0:
    SW, SH = 1280, 720
    screen = pygame.display.set_mode((SW, SH))
else:
    screen = pygame.display.get_surface() or screen

# ---- PANTALLA DE CARGA animada (archivo loading.py junto a main.py; si no está, el juego arranca igual) ----
try:
    import loading as _loading
    _LS = _loading.LoadingScreen("ATTACK ON THE ALIENS", screen)
except Exception:
    _LS = None


def _ld(p, text="", frames=8):
    """Avanza la barra de carga a 'p' (0..1) y anima unos cuadros."""
    global _LS
    if _LS is None:
        return
    try:
        _LS.set(p, text)
        for _ in range(frames):
            _LS.frame()
    except Exception:
        _LS = None


def _ld_done():
    """Llena la barra, oscurece y quita la pantalla de carga."""
    global _LS
    if _LS is None:
        return
    try:
        _LS.set(1.0, "Listo")
        for _ in range(120):
            _LS.frame()
            if _LS.shown >= 1.0:
                break
        _LS.fade_out()
    except Exception:
        pass
    _LS = None


_ld(0.03, "Iniciando", 10)

HEIGHT = LOGICAL_H
WIDTH = int(round(LOGICAL_H * SW / float(SH)))
canvas = pygame.Surface((WIDTH, HEIGHT)).convert()
VIEW = [0, 0, SW, SH]          # zona de la ventana donde se dibuja el juego (x, y, ancho, alto)


def update_view():
    """Calcula dónde va el juego dentro de la ventana REAL (centrado y sin deformar) y se mantiene al día
    si el tamaño de la ventana cambia mientras se juega."""
    global screen, SW, SH
    s = pygame.display.get_surface()
    if s is None:
        return
    cw, ch = s.get_size()
    if cw <= 0 or ch <= 0:
        return
    screen, SW, SH = s, cw, ch
    ca = WIDTH / float(HEIGHT)
    sa = cw / float(ch)
    if abs(sa / ca - 1.0) < 0.06:          # casi igual: se llena toda la pantalla
        vw, vh = cw, ch
    elif sa > ca:                           # ventana más ancha: barras a los lados
        vh = ch
        vw = max(1, int(round(ch * ca)))
    else:                                   # ventana más alta: barras arriba/abajo (centrado)
        vw = cw
        vh = max(1, int(round(cw / ca)))
    VIEW[0], VIEW[1], VIEW[2], VIEW[3] = (cw - vw) // 2, (ch - vh) // 2, vw, vh


def view_to_canvas(px, py):
    """Pixeles de la ventana -> coordenadas del juego."""
    return (px - VIEW[0]) * WIDTH / float(VIEW[2]), (py - VIEW[1]) * HEIGHT / float(VIEW[3])


update_view()
clock = pygame.time.Clock()
PIXEL_SCALE = 2

# --- PALETA ---
SPACE_BG = (10, 8, 25)
WHITE = (255, 255, 255)
LIGHT_GRAY = (200, 205, 220)
DARK_GRAY = (40, 44, 62)
CYAN = (0, 240, 255)
GREEN = (60, 230, 80)
RED = (240, 50, 60)
ORANGE = (255, 140, 20)
YELLOW = (255, 230, 60)

# --- FUENTES (sin antialias = look pixel) y caché de texto ---
font_large = pygame.font.Font(None, max(18, int(HEIGHT * 0.1)))
font_medium = pygame.font.Font(None, max(12, int(HEIGHT * 0.06)))
font_title = pygame.font.Font(None, max(24, int(HEIGHT * 0.13)))
font_small = pygame.font.Font(None, max(10, int(HEIGHT * 0.047)))

_text_cache = {}


def text_surf(font, s, color, shadow=(8, 6, 20)):
    key = (id(font), s, color)
    surf = _text_cache.get(key)
    if surf is None:
        if len(_text_cache) > 300:
            _text_cache.clear()
        a = font.render(s, False, color)
        b = font.render(s, False, shadow)
        surf = pygame.Surface((a.get_width() + 3, a.get_height() + 3), pygame.SRCALPHA)
        surf.blit(b, (2, 2))
        for ox, oy in ((0, 1), (2, 1), (1, 0), (1, 2)):       # contorno oscuro: texto más nítido
            surf.blit(b, (ox, oy))
        surf.blit(a, (1, 1))
        surf = surf.convert_alpha()
        _text_cache[key] = surf
    return surf


def draw_text(font, s, color, cx, y):
    t = text_surf(font, s, color)
    canvas.blit(t, (int(cx - t.get_width() / 2), int(y)))


# ---- títulos con degradado + contorno (cacheados) ----
_title_cache = {}


def title_surf(font, s, top, bot):
    key = (id(font), s, top, bot)
    t = _title_cache.get(key)
    if t is None:
        a = font.render(s, False, (255, 255, 255)).convert_alpha()
        w, h = a.get_size()
        grad = pygame.Surface((w, h))
        for y in range(h):
            k = y / float(max(1, h - 1))
            pygame.draw.line(grad, (int(top[0] + (bot[0] - top[0]) * k), int(top[1] + (bot[1] - top[1]) * k),
                                    int(top[2] + (bot[2] - top[2]) * k)), (0, y), (w, y))
        a.blit(grad, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        o = font.render(s, False, (10, 8, 30)).convert_alpha()
        t = pygame.Surface((w + 8, h + 8), pygame.SRCALPHA)
        for dx in (-2, -1, 0, 1, 2):
            for dy in (-2, -1, 0, 1, 2, 3):
                if abs(dx) + abs(dy) <= 3:
                    t.blit(o, (4 + dx, 4 + dy))
        t.blit(a, (4, 4))
        t = t.convert_alpha()
        _title_cache[key] = t
    return t


_ft_font = None
_ft_cache = {}
_ft_frames = {}
TITLE_SHINE_N = 20


def get_title_font():
    """Fuente grande y en negrita; se achica sola si el título no cabe en la pantalla."""
    global _ft_font
    if _ft_font is None:
        sz = int(HEIGHT * 0.19)
        while True:
            f = pygame.font.Font(None, sz)
            f.set_bold(True)
            if f.size("ATTACK ON THE ALIENS")[0] <= WIDTH * 0.86 or sz <= 24:
                break
            sz -= 2
        _ft_font = f
    return _ft_font


def fancy_title(s, top, bot):
    """Letras con degradado, brillo superior, contorno grueso y extrusión 3D (se hornea UNA vez)."""
    key = (s, top, bot)
    c = _ft_cache.get(key)
    if c is not None:
        return c
    font = get_title_font()
    a = font.render(s, False, (255, 255, 255)).convert_alpha()
    w, h = a.get_size()
    P = 7
    fill = pygame.Surface((w + 2, h + 1), pygame.SRCALPHA)
    fill.blit(a, (0, 0))
    fill.blit(a, (1, 0))
    grad = pygame.Surface((w + 2, h + 1))
    for y in range(h + 1):
        pygame.draw.line(grad, lerp_col(top, bot, y / float(max(1, h))), (0, y), (w + 2, y))
    fill.blit(grad, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    hl = pygame.Surface((w + 2, max(2, h // 4)))
    hl.fill((50, 50, 50))
    fill.blit(hl, (0, 2), special_flags=pygame.BLEND_RGB_ADD)      # reflejo en la parte alta
    oc = font.render(s, False, (10, 8, 30)).convert_alpha()
    ec = font.render(s, False, shade(bot, 0.3)).convert_alpha()
    lay = pygame.Surface((w + 2 * P + 2, h + 2 * P + 1), pygame.SRCALPHA)
    ring = [(dx, dy) for dx in (-2, -1, 0, 1, 2) for dy in (-2, -1, 0, 1, 2) if abs(dx) + abs(dy) <= 3]
    for ox in (0, 2, 4):
        for dx, dy in ring:
            for ex in (0, 1):
                lay.blit(oc, (P + dx + ox + ex, P + dy + ox))
    for k in range(4, 0, -1):
        for ex in (0, 1):
            lay.blit(ec, (P + k + ex, P + k))
    c = (lay.convert_alpha(), fill.convert_alpha(), w, h, P)
    _ft_cache[key] = c
    return c


def title_frame(s, top, bot, idx):
    key = (s, top, bot, idx)
    f = _ft_frames.get(key)
    if f is None:
        lay, fill, w, h, P = fancy_title(s, top, bot)
        fc = fill.copy()
        if idx >= 0:                               # destello diagonal que cruza las letras
            band = pygame.Surface((w + 2, h + 1))
            band.fill((0, 0, 0))
            x = -h + (w + 2 * h) * idx / float(TITLE_SHINE_N - 1)
            pygame.draw.polygon(band, (150, 150, 150), [(x + h * 0.5, 0), (x + h * 0.5 + 16, 0), (x + 16, h + 1), (x, h + 1)])
            fc.blit(band, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        f = lay.copy()
        f.blit(fc, (P, P))
        f = f.convert_alpha()
        _ft_frames[key] = f
    return f


def draw_title(font, s, top, bot, cx, y):
    """Dibuja el título (la fuente recibida ya no se usa: tiene la suya) y devuelve su borde inferior."""
    lay, fill, w, h, P = fancy_title(s, top, bot)
    k = frame % 240
    surf = title_frame(s, top, bot, (k // 2) if k < 2 * TITLE_SHINE_N else -1)
    x0 = int(cx - surf.get_width() / 2)
    canvas.blit(surf, (x0, int(y)))
    for j in range(4):                              # destellos en cruz
        ph = (frame // 2 + j * 37) % 120
        if ph < 14:
            sz = ph if ph < 7 else 14 - ph
            px = x0 + P + int(w * (0.1 + 0.27 * j))
            py = int(y) + P + int(h * (0.15 + 0.55 * ((j * 0.37) % 1.0)))
            pygame.draw.line(canvas, WHITE, (px - sz, py), (px + sz, py))
            pygame.draw.line(canvas, WHITE, (px, py - sz), (px, py + sz))
            pygame.draw.rect(canvas, WHITE, (px - 1, py - 1, 2, 2))
    return int(y) + surf.get_height()


# =====================================================================
#  LUCES (brillos aditivos pre-calculados), EFECTOS Y CALIDAD AUTOMÁTICA
# =====================================================================
QUALITY = 2             # 2 = todo, 1 = medio, 0 = ligero. Baja SOLO si los FPS caen.
_glow_cache = {}


def glow_surf(color, r):
    key = (color, r)
    g = _glow_cache.get(key)
    if g is None:
        g = pygame.Surface((r * 2, r * 2))
        g.fill((0, 0, 0))
        for i in range(r, 0, -1):
            t = 1.0 - i / float(r)
            k = t * t
            pygame.draw.circle(g, (int(color[0] * k), int(color[1] * k), int(color[2] * k)), (r, r), i)
        g = g.convert()
        _glow_cache[key] = g
    return g


def add_glow(surface, x, y, color, r, k=1.0, q=2):
    """Resplandor aditivo (luz). q = calidad mínima para dibujarlo."""
    if QUALITY < q:
        return
    lv = int(k * 4 + 0.5)
    if lv <= 0:
        return
    if lv < 4:
        color = (color[0] * lv // 4, color[1] * lv // 4, color[2] * lv // 4)
    surface.blit(glow_surf(color, r), (int(x) - r, int(y) - r), special_flags=pygame.BLEND_RGB_ADD)


fx_list = []
shake_t = 0


def add_shake(n):
    global shake_t
    shake_t = max(shake_t, n)


def fx_boom(x, y, size=1.0, color=None):
    """Destello + onda de choque al explotar."""
    if len(fx_list) < 14:
        fx_list.append([x, y, 0, int(18 * size) + 6, color, size])


def update_fx():
    for f in fx_list:
        f[2] += 1
    fx_list[:] = [f for f in fx_list if f[2] < f[3]]


def draw_fx(surface):
    for f in fx_list:
        t = f[2] / float(f[3])
        size = f[5]
        col = f[4] or ((250, 225, 120) if vg_on else (255, 210, 120))
        add_glow(surface, f[0], f[1], col, max(8, (int(26 * size * (1.0 - t * 0.5)) // 4) * 4), 1.0 - t, 1)
        r = int(size * (6 + 30 * t))
        if r > 2:
            pygame.draw.circle(surface, shade(col, 1.2 - t), (int(f[0]), int(f[1])), r, 2 if t < 0.6 else 1)


# =====================================================================
#  SONIDO  (todo se sintetiza por código: no hacen falta archivos)
#  Si el dispositivo no tiene audio, el juego corre igual en silencio.
# =====================================================================
AUDIO = False
SR, CH = 22050, 1
music_vol = 1.0          # volumen de la música (0..1) - se cambia en AJUSTES
sfx_vol = 1.0            # volumen de los efectos (0..1)
try:
    _mi = pygame.mixer.get_init()
    if _mi and _mi[1] == -16:
        SR, CH = _mi[0], _mi[2]
        AUDIO = True
except Exception:
    AUDIO = False


def _sq(p):
    return 1.0 if (p % 1.0) < 0.5 else -1.0


def _saw(p):
    return 2.0 * (p % 1.0) - 1.0


def _tri(p):
    p %= 1.0
    return 4.0 * p - 1.0 if p < 0.5 else 3.0 - 4.0 * p


def _sin(p):
    return math.sin(6.283185307 * p)


def tone(dur, f0, f1=None, wave=_sq, vol=0.5, decay=1.5):
    f1 = f0 if f1 is None else f1
    n = max(1, int(dur * SR))
    out, ph = [], 0.0
    for i in range(n):
        t = i / float(n)
        ph += (f0 + (f1 - f0) * t) / SR
        out.append(wave(ph) * vol * (1.0 - t) ** decay * min(1.0, i / 40.0))
    return out


def noise(dur, c0=0.5, c1=0.05, vol=0.6, decay=1.5):
    n = max(1, int(dur * SR))
    out, y = [], 0.0
    for i in range(n):
        t = i / float(n)
        y += (random.uniform(-1, 1) - y) * (c0 + (c1 - c0) * t)
        out.append(y * 2.2 * vol * (1.0 - t) ** decay)
    return out


def mix(*bufs):
    out = [0.0] * max(len(b) for b in bufs)
    for b in bufs:
        for i, v in enumerate(b):
            out[i] += v
    return out


def seq(*bufs):
    out = []
    for b in bufs:
        out.extend(b)
    return out


def to_sound(buf, vol=1.0):
    pk = max(abs(v) for v in buf) if buf else 1.0
    k = 0.95 / pk if pk > 0.95 else 1.0      # normaliza: nada de distorsión
    ints = array('h', [int(max(-1.0, min(1.0, v * k)) * 30000) for v in buf])
    if CH == 2:
        st = array('h', [0]) * (len(ints) * 2)
        st[0::2] = ints
        st[1::2] = ints
        ints = st
    s = pygame.mixer.Sound(buffer=ints.tobytes())
    s.set_volume(vol)
    return s


def _note(buf, start, dur, freq, vol, wave, decay=1.2):
    s0, n, ph, inc = int(start * SR), int(dur * SR), 0.0, freq / SR
    for i in range(n):
        j = s0 + i
        if j >= len(buf):
            break
        ph += inc
        buf[j] += wave(ph) * vol * (1.0 - i / float(n)) ** decay * min(1.0, i / 40.0)


def _kick(buf, start, vol):
    s0, n, ph = int(start * SR), int(0.12 * SR), 0.0
    for i in range(n):
        if s0 + i >= len(buf):
            break
        t = i / float(n)
        ph += (140 - 100 * t) / SR
        buf[s0 + i] += _sin(ph) * vol * (1.0 - t) ** 2


def _hat(buf, start, vol):
    s0, n = int(start * SR), int(0.03 * SR)
    for i in range(n):
        if s0 + i >= len(buf):
            break
        buf[s0 + i] += random.uniform(-1, 1) * vol * (1.0 - i / float(n))


_NN = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def nf(name):
    """'A#3' -> frecuencia en Hz."""
    st = _NN[name[0]]
    i = 1
    if name[i] in "#b":
        st += 1 if name[i] == "#" else -1
        i += 1
    midi = 12 * (int(name[i:]) + 1) + st
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


_WAVES = {"sq": _sq, "saw": _saw, "tri": _tri, "sin": _sin}


def _snare(buf, start, vol):
    s0, n = int(start * SR), int(0.11 * SR)
    for i in range(n):
        if s0 + i >= len(buf):
            break
        t = i / float(n)
        buf[s0 + i] += (random.uniform(-1, 1) * 0.8 + _sin(i * 190.0 / SR) * 0.4) * vol * (1.0 - t) ** 1.6


def _clang(buf, start, vol):
    s0, n = int(start * SR), int(0.22 * SR)
    for i in range(n):
        if s0 + i >= len(buf):
            break
        t = i / float(n)
        buf[s0 + i] += (_sin(i * 523.0 / SR) + _sin(i * 811.0 / SR) * 0.7 + random.uniform(-1, 1) * 0.25) * vol * (1.0 - t) ** 2.2


def _note_gen(buf, start, dur, freq, vol, wave, decay=1.2):
    """Igual que _note pero en trocitos (generador) para no trabar el juego con notas largas."""
    s0, n, ph, inc = int(start * SR), int(dur * SR), 0.0, freq / SR
    for i in range(n):
        j = s0 + i
        if j >= len(buf):
            break
        ph += inc
        buf[j] += wave(ph) * vol * (1.0 - i / float(n)) ** decay * min(1.0, i / 40.0)
        if i % 2500 == 2499:
            yield
    yield


def _pad_gen(buf, start, dur, freq, vol):
    """Nota larga y suave (sinusoide con subida/bajada lenta). Es un generador: se construye por trocitos."""
    s0, n, inc, ph = int(start * SR), int(dur * SR), freq / SR, 0.0
    for i in range(n):
        j = s0 + i
        if j >= len(buf):
            break
        ph += inc
        buf[j] += math.sin(6.283185307 * ph) * vol * math.sin(3.14159265 * i / n)
        if i % 3000 == 0:
            yield


# ---- Cada pista: tempo (step), acordes (bajo, [notas]) y qué se toca. Patrones de 8 pasos por acorde:
#      kick / snare / hat / metal / bell son cadenas de 8 letras ('x' = suena). Todo se sintetiza por código.
TRACKS = {
    # MENU: alegre y luminoso (Do mayor)
    "menu": dict(vol=0.26, step=0.22, bw="sq", arp="tri", avol=0.13, bvol=0.15, bass="eighth", pad=0.03,
                 pat=[0, 1, 2, 1, 0, 1, 2, 2], kick="x...x...", hat="..x...x.", bell="x.....x.", bellvol=0.05,
                 prog=[("C3", ["C4", "E4", "G4"]), ("G2", ["B3", "D4", "G4"]), ("A2", ["A3", "C4", "E4"]), ("F2", ["A3", "C4", "F4"])]),
    # SELECCION (mapa, tienda, color): relajada, cósmica, con eco, sin batería
    "select": dict(vol=0.30, step=0.45, bw="sin", arp="sin", avol=0.05, bvol=0.14, bass="long", pad=0.05,
                   pat=[0, 1, 2, 1, 0, 2, 1, 2], aoct=[2] * 8, amask="x.x.x.x.", bell="x...x.x.", bellvol=0.07,
                   echo=(0.45, 0.45),
                   prog=[("A2", ["A3", "E4", "B4"]), ("F2", ["F3", "C4", "G4"]), ("C3", ["G3", "D4", "E4"]), ("G2", ["D4", "A4", "B3"])]),
    # COMBATE normal: rápida y con empuje (Re menor)
    "game": dict(vol=0.32, step=0.15, bw="sq", arp="saw", avol=0.065, bvol=0.17, bass="pump",
                 pat=[0, 2, 1, 2, 0, 2, 1, 2], aoct=[1, 1, 1, 1, 2, 1, 1, 2], kick="x..x..x.", snare="....x...", hat="x.x.x.x.",
                 prog=[("D2", ["D4", "F4", "A4"]), ("A#1", ["A#3", "D4", "F4"]), ("F2", ["A3", "C4", "F4"]), ("C2", ["G3", "C4", "E4"])]),
    # BOSS 1 CENTINELA ALFA: marcha militar tensa (Mi menor)
    "boss1": dict(vol=0.38, step=0.15, bw="sq", arp="saw", avol=0.06, bvol=0.2, bass="pump",
                  pat=[0, 1, 2, 1, 0, 1, 2, 1], aoct=[1, 2, 1, 2, 1, 2, 1, 2], kick="x.x.x.x.", snare="....x...", hat=".x.x.x.x",
                  prog=[("E2", ["E4", "G4", "B4"]), ("C2", ["C4", "E4", "G4"]), ("D2", ["D4", "F#4", "A4"]), ("B1", ["B3", "D#4", "F#4"])]),
    # BOSS 2 TITAN ESCARLATA: pesada, lenta, con golpes graves
    "boss2": dict(vol=0.42, step=0.21, bw="saw", arp="saw", avol=0.08, bvol=0.22, bass="stomp",
                  pat=[0, 0, 1, 0, 0, 1, 2, 1], kick="x...x.x.", snare="....x...", metal="x.......",
                  prog=[("D2", ["D3", "A3", "D4"]), ("D#2", ["D#3", "A#3", "D#4"]), ("C2", ["C3", "G3", "C4"]), ("A1", ["A2", "E3", "A3"])]),
    # BOSS 3 OJO DEL NUCLEO: misteriosa, arpegios agudos y eco
    "boss3": dict(vol=0.36, step=0.14, bw="saw", arp="tri", avol=0.12, bvol=0.16, bass="off",
                  pat=[0, 1, 2, 1, 2, 1, 0, 2], aoct=[2] * 8, kick="x.....x.", hat="x.x.x.x.", echo=(0.21, 0.35),
                  prog=[("F#2", ["F#4", "A4", "C5"]), ("G2", ["G4", "A#4", "C#5"]), ("F#2", ["F#4", "A4", "C5"]), ("E2", ["E4", "G4", "A#4"])]),
    # BOSS 4 CENTINELA GLACIAL: helada, campanitas y silencios
    "boss4": dict(vol=0.36, step=0.17, bw="tri", arp="sin", avol=0.09, bvol=0.2, bass="long", pad=0.04,
                  pat=[0, 1, 2, 2, 1, 0, 1, 2], aoct=[2] * 8, amask="x.x.xx.x", bell="x...x.x.", bellvol=0.08,
                  kick="x.......", snare="....x...", hat=".x.x.x.x", echo=(0.3, 0.3),
                  prog=[("G2", ["G4", "A#4", "D5"]), ("D#2", ["G4", "A#4", "D#5"]), ("C3", ["G4", "C5", "D#5"]), ("D3", ["F#4", "A4", "D5"])]),
    # BOSS 5 REINA ENJAMBRE: zumbido rápido y desafinado
    "boss5": dict(vol=0.38, step=0.11, bw="sq", arp="saw", avol=0.055, bvol=0.15, bass="pump", det=4.0,
                  pat=[0, 1, 2, 1, 2, 1, 0, 1], aoct=[1, 2, 1, 2, 1, 2, 1, 2], kick="x.x.x.x.", snare="..x...x.", hat="xxxxxxxx", hatvol=0.025,
                  prog=[("A2", ["A4", "A#4", "E5"]), ("A#2", ["A#4", "D5", "F5"]), ("A2", ["A4", "A#4", "E5"]), ("G2", ["G4", "A#4", "D5"])]),
    # BOSS 6 CAZADOR DEL VACIO: oscura, grave, espaciosa
    "boss6": dict(vol=0.38, step=0.2, bw="sin", arp="tri", avol=0.1, bvol=0.26, bass="long", pad=0.05, padoct=0.5,
                  pat=[0, 1, 2, 0, 1, 2, 1, 0], aoct=[2] * 8, amask="x..x.x..", kick="x.....x.", metal="......x.",
                  echo=(0.5, 0.45),
                  prog=[("C#2", ["C#4", "E4", "G#4"]), ("A1", ["A3", "C#4", "E4"]), ("B1", ["B3", "D#4", "F#4"]), ("G#1", ["G#3", "B3", "D#4"])]),
    # BOSS 7 ARCHI-REACTOR: industrial, mecánica
    "boss7": dict(vol=0.40, step=0.13, bw="sq", arp="sq", avol=0.06, bvol=0.2, bass="pump",
                  pat=[0, 0, 1, 0, 0, 2, 1, 2], aoct=[1, 1, 2, 1, 1, 2, 1, 2], amask="xx.xx.x.", kick="x.x.x.x.", snare="..x...x.",
                  hat="x.xxx.xx", metal="x...x...",
                  prog=[("B1", ["B3", "D4", "F#4"]), ("G2", ["G3", "B3", "D4"]), ("D2", ["D4", "F#4", "A4"]), ("A1", ["A3", "C#4", "E4"])]),
    # BOSS 8 EMPERADOR GALACTICO: épica, grandiosa (Re menor armónico), la más larga
    "boss8": dict(vol=0.42, step=0.14, bw="sq", arp="saw", avol=0.065, bvol=0.2, bass="pump", pad=0.04,
                  pat=[0, 1, 2, 1, 0, 2, 1, 2], aoct=[1, 2, 1, 2, 1, 2, 2, 1], kick="x.x.x.x.", snare="....x...", hat="xxxxxxxx", hatvol=0.03,
                  metal="x.......", bell="x...x...", bellvol=0.06, echo=(0.28, 0.3),
                  prog=[("D2", ["D4", "F4", "A4"]), ("A#1", ["A#3", "D4", "F4"]), ("G2", ["G3", "A#3", "D4"]),
                        ("A2", ["A3", "C#4", "E4"]), ("D2", ["D4", "F4", "A4"]), ("A2", ["A3", "C#4", "E4"])]),
}
BUILD_ORDER = ["menu", "select", "game"] + ["boss%d" % i for i in range(1, 9)]


def _track_gen(key):
    """Construye una pista POCO A POCO (generador): el juego la va sintetizando entre cuadros sin trabarse."""
    sp = TRACKS[key]
    step, prog = sp["step"], sp["prog"]
    pat = sp.get("pat", [0, 1, 2, 1, 0, 1, 2, 2])
    aw, bw = _WAVES[sp.get("arp", "tri")], _WAVES[sp.get("bw", "sq")]
    amask, aoct = sp.get("amask", "xxxxxxxx"), sp.get("aoct", [1] * 8)
    avol, bvol, det = sp.get("avol", 0.1), sp.get("bvol", 0.18), sp.get("det", 0.0)
    bass = sp.get("bass", "eighth")
    kick, snare = sp.get("kick", "........"), sp.get("snare", "........")
    hat, metal, bell = sp.get("hat", "........"), sp.get("metal", "........"), sp.get("bell", "........")
    spc = 8
    buf = [0.0] * int(len(prog) * spc * step * SR)
    for c, (root, chord) in enumerate(prog):
        rf, cf = nf(root), [nf(x) for x in chord]
        bt = c * spc * step
        if sp.get("pad"):
            for f in cf:
                yield from _pad_gen(buf, bt, spc * step * 1.02, f * sp.get("padoct", 1.0), sp["pad"])
        if bass == "long":
            yield from _note_gen(buf, bt, spc * step * 0.98, rf, bvol, bw, 0.6)
        for k in range(spc):
            t0 = bt + k * step
            if bass == "pump" or (bass == "eighth" and k % 2 == 0) or (bass == "stomp" and k in (0, 3, 4, 7)) \
                    or (bass == "off" and k in (0, 3, 6)):
                yield from _note_gen(buf, t0, step * 0.9, rf, bvol, bw, 1.0)
            if amask[k] == "x":
                f = cf[pat[k]] * aoct[k]
                yield from _note_gen(buf, t0, step * 0.95, f, avol, aw, 1.4)
                if det:
                    yield from _note_gen(buf, t0, step * 0.95, f + det, avol, aw, 1.4)
            if bell[k] == "x":
                yield from _note_gen(buf, t0, step * 3.0, cf[(k + c) % 3] * 2.0, sp.get("bellvol", 0.06), _sin, 2.2)
            if kick[k] == "x":
                _kick(buf, t0, 0.45)
                yield
            if snare[k] == "x":
                _snare(buf, t0, 0.12)
                yield
            if hat[k] == "x":
                _hat(buf, t0, sp.get("hatvol", 0.04))
            if metal[k] == "x":
                _clang(buf, t0, 0.09)
            yield
    ec = sp.get("echo")
    if ec:
        d, fb = int(ec[0] * SR), ec[1]
        for i in range(d, len(buf)):
            buf[i] += buf[i - d] * fb
            if i % 6000 == 0:
                yield
    pk = 0.0
    for i in range(0, len(buf), 20000):
        pk = max(pk, max(map(abs, buf[i:i + 20000])))
        yield
    k = 0.95 / pk if pk > 0.95 else 1.0
    ints = array('h')
    for i in range(0, len(buf), 12000):
        ints.extend([int(max(-1.0, min(1.0, v * k)) * 30000) for v in buf[i:i + 12000]])
        yield
    if CH == 2:
        st = array('h', [0]) * (len(ints) * 2)
        st[0::2] = ints
        st[1::2] = ints
        ints = st
    return pygame.mixer.Sound(buffer=ints.tobytes())


SFX = {}
SFX_BASE = {}
MUSIC = {}
music_ch = None
music_now = None         # pista que suena ahora
music_want = None        # pista que se pidió (puede estar construyéndose todavía)
_gens = {}


def apply_sfx_volume():
    for k, s in SFX.items():
        try:
            s.set_volume(SFX_BASE.get(k, 1.0) * sfx_vol)
        except Exception:
            pass


def apply_music_volume():
    if music_ch is not None and music_now in TRACKS:
        try:
            music_ch.set_volume(TRACKS[music_now]["vol"] * music_vol)
        except Exception:
            pass


def init_audio():
    global music_ch
    if not AUDIO:
        return
    try:
        pygame.mixer.set_num_channels(16)
        pygame.mixer.set_reserved(1)
        music_ch = pygame.mixer.Channel(0)
        S = SFX
        S["shoot"] = to_sound(tone(0.11, 1100, 350, _sq, 0.22, 1.5), 0.45)
        S["explosion"] = to_sound(mix(noise(0.35, 0.45, 0.03, 0.9, 1.6), tone(0.3, 160, 50, _sin, 0.6, 1.5)), 0.7)
        S["hurt"] = to_sound(mix(tone(0.4, 330, 70, _saw, 0.45, 1.2), noise(0.3, 0.5, 0.1, 0.5, 1.5)), 0.8)
        S["orb"] = to_sound(tone(0.07, 900, 1500, _sin, 0.5, 1.0), 0.5)
        S["heart"] = to_sound(seq(tone(0.07, 523, None, _sq, 0.3, 0.8), tone(0.07, 659, None, _sq, 0.3, 0.8),
                                  tone(0.12, 784, None, _sq, 0.3, 1.0)), 0.6)
        S["ready"] = to_sound(seq(tone(0.09, 880, None, _sin, 0.5, 0.8), tone(0.16, 1320, None, _sin, 0.5, 1.0)), 0.6)
        S["nuke"] = to_sound(mix(noise(0.8, 0.02, 0.5, 0.9, 0.8), tone(0.8, 90, 700, _saw, 0.35, 0.6)), 0.8)
        S["click"] = to_sound(tone(0.05, 1200, 900, _sq, 0.3, 1.0), 0.5)
        S["dash"] = to_sound(mix(tone(0.2, 280, 1000, _saw, 0.3, 1.0), noise(0.2, 0.6, 0.1, 0.35, 1.0)), 0.7)
        S["dash_ready"] = to_sound(seq(tone(0.05, 1000, None, _sin, 0.4, 1.0), tone(0.08, 1500, None, _sin, 0.4, 1.0)), 0.4)
        S["lock_on"] = to_sound(seq(tone(0.05, 700, None, _sq, 0.25, 1.0), tone(0.08, 1100, None, _sq, 0.25, 1.0)), 0.5)
        S["lock_off"] = to_sound(seq(tone(0.05, 1100, None, _sq, 0.25, 1.0), tone(0.08, 600, None, _sq, 0.25, 1.0)), 0.5)
        S["level_done"] = to_sound(seq(tone(0.12, 523, None, _sq, 0.3, 0.8), tone(0.12, 659, None, _sq, 0.3, 0.8),
                                       tone(0.12, 784, None, _sq, 0.3, 0.8), tone(0.35, 1047, None, _sq, 0.3, 1.0)), 0.7)
        S["power"] = to_sound(seq(tone(0.06, 660, None, _tri, 0.4, 0.8), tone(0.06, 880, None, _tri, 0.4, 0.8),
                                  tone(0.06, 1100, None, _tri, 0.4, 0.8), tone(0.14, 1480, None, _tri, 0.4, 1.0)), 0.6)
        S["shield_break"] = to_sound(mix(noise(0.3, 0.6, 0.1, 0.7, 1.2), tone(0.28, 900, 160, _sq, 0.3, 1.2)), 0.7)
        siren = seq(tone(0.32, 420, 640, _sq, 0.3, 0.3), tone(0.32, 640, 420, _sq, 0.3, 0.3))
        S["warning"] = to_sound(siren * 3, 0.7)
        S["boss_shot"] = to_sound(tone(0.16, 600, 180, _saw, 0.3, 1.5), 0.45)
        S["boss_ring"] = to_sound(mix(tone(0.3, 200, 520, _sq, 0.25, 1.0), noise(0.25, 0.4, 0.05, 0.4, 1.0)), 0.55)
        S["boss_hit"] = to_sound(mix(tone(0.05, 220, 120, _sq, 0.25, 1.0), noise(0.04, 0.6, 0.3, 0.4, 1.0)), 0.5)
        S["boss_roar"] = to_sound(mix(tone(0.9, 90, 55, _saw, 0.5, 0.7), noise(0.9, 0.2, 0.03, 0.6, 0.7)), 0.9)
        S["boss_die"] = to_sound(mix(noise(1.6, 0.5, 0.01, 1.0, 1.0), tone(1.6, 140, 30, _sin, 0.7, 1.0)), 0.9)
        S["gameover"] = to_sound(seq(tone(0.25, 392, None, _tri, 0.5, 0.8), tone(0.25, 349, None, _tri, 0.5, 0.8),
                                     tone(0.25, 311, None, _tri, 0.5, 0.8), tone(0.7, 262, 200, _tri, 0.5, 1.0)), 0.8)
        S["victory"] = to_sound(seq(tone(0.14, 523, None, _sq, 0.3, 0.8), tone(0.14, 659, None, _sq, 0.3, 0.8),
                                    tone(0.14, 784, None, _sq, 0.3, 0.8), tone(0.14, 1047, None, _sq, 0.3, 0.8),
                                    tone(0.14, 784, None, _sq, 0.3, 0.8), tone(0.6, 1047, None, _sq, 0.3, 1.0)), 0.8)
        for _k, _s in S.items():
            SFX_BASE[_k] = _s.get_volume()
        apply_sfx_volume()
    except Exception:
        SFX.clear()
        MUSIC.clear()


def play(name):
    s = SFX.get(name)
    if s is not None:
        try:
            s.play()
        except Exception:
            pass


def _apply_music():
    global music_now
    if music_ch is None:
        return
    want = music_want
    try:
        if want is None:
            if music_now is not None:
                music_ch.stop()
                music_now = None
            return
        if want in MUSIC:
            tgt = want
        elif music_now is None:                  # aún no está lista: mientras tanto suena otra que sí lo esté
            tgt = next((k for k in ("game", "menu", "select") if k in MUSIC), None)
        else:
            return
        if tgt is None or tgt == music_now:
            return
        music_now = tgt
        music_ch.set_volume(TRACKS[tgt]["vol"] * music_vol)
        music_ch.play(MUSIC[tgt], loops=-1)
    except Exception:
        pass


def set_music(name):
    """name: 'menu' | 'select' | 'game' | 'boss1'..'boss8' | None"""
    global music_want
    music_want = name
    _apply_music()


def music_tick():
    """Cada cuadro avanza un poquito la síntesis de la música que falta (primero la pedida, luego el resto)."""
    if music_ch is None or not AUDIO:
        return
    key = music_want if (music_want in TRACKS and music_want not in MUSIC) else None
    if key is None:
        key = next((k for k in BUILD_ORDER if k not in MUSIC), None)
    if key is None:
        return
    g = _gens.get(key)
    if g is None:
        g = _gens[key] = _track_gen(key)
    quiet = game_state != "PLAYING"
    fps = clock.get_fps()
    budget = 0.010 if quiet else (0.004 if (fps == 0 or fps >= 50) else 0.0015)
    t0 = time.perf_counter()
    try:
        while time.perf_counter() - t0 < budget:
            next(g)
    except StopIteration as e:
        try:
            MUSIC[key] = e.value
        except Exception:
            MUSIC[key] = None
        _gens.pop(key, None)
        if MUSIC.get(key) is None:
            MUSIC.pop(key, None)
            TRACKS.pop(key, None)
            if key in BUILD_ORDER:
                BUILD_ORDER.remove(key)
        else:
            _apply_music()
    except Exception:
        _gens.pop(key, None)
        TRACKS.pop(key, None)
        if key in BUILD_ORDER:
            BUILD_ORDER.remove(key)


def music_pause(flag):
    if music_ch is not None:
        try:
            music_ch.pause() if flag else music_ch.unpause()
        except Exception:
            pass


_ld(0.06, "Generando sonidos")
init_audio()
_ld(0.35, "Sonidos listos")


# =====================================================================
#  MOTOR DE PIXEL ART: matriz -> sprite con contorno y sombreado
#  (se define media nave y se espeja; luz desde arriba)
# =====================================================================
def shade(c, f):
    return (max(0, min(255, int(c[0] * f))), max(0, min(255, int(c[1] * f))), max(0, min(255, int(c[2] * f))))


def sprite_pixels(rows, palette, mirror=True, outline=(12, 10, 30), noshade=""):
    if mirror:
        rows = [r + r[::-1] for r in rows]
    h, w = len(rows), len(rows[0])
    H, W = h + 2, w + 2
    g = [[None] * W for _ in range(H)]
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in palette:
                g[y + 1][x + 1] = (ch, palette[ch])
    out = {}
    for y in range(H):
        for x in range(W):
            cell = g[y][x]
            if cell is None:
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < W and 0 <= ny < H and g[ny][nx] is not None:
                        out[(x, y)] = outline
                        break
            else:
                ch, c = cell
                if ch not in noshade:
                    up = g[y - 1][x] if y > 0 else None
                    dn = g[y + 1][x] if y < H - 1 else None
                    lf = g[y][x - 1] if x > 0 else None
                    rt = g[y][x + 1] if x < W - 1 else None
                    if up is None:
                        c = shade(c, 1.3)
                    elif dn is None:
                        c = shade(c, 0.7)
                    if lf is None:                  # luz desde la izquierda
                        c = shade(c, 1.14)
                    elif rt is None:
                        c = shade(c, 0.86)
                out[(x, y)] = c
    return W, H, out


def make_surface(rows, pal, outline, noshade="", scale=PIXEL_SCALE):
    w, h, px = sprite_pixels(rows, pal, True, outline, noshade)
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for (x, y), c in px.items():
        s.set_at((x, y), (c[0], c[1], c[2], 255))
    if scale != 1:
        s = pygame.transform.scale(s, (w * scale, h * scale))
    return s.convert_alpha()


class Sprite:
    """Sprite con caché de rotaciones (pasos de 10°) -> nada de rotate() por frame."""
    def __init__(self, surf):
        self.base = surf
        self.cache = {}
        self.glow = None

    def rot(self, angle):
        k = int(round(angle / 10.0)) % 36
        s = self.cache.get(k)
        if s is None:
            s = pygame.transform.rotozoom(self.base, k * 10, 1.0).convert_alpha()   # rotación suave (sin dientes)
            self.cache[k] = s
        return s


# --- Diseños (media mitad, se espejan) ---
PLAYER_PAL = {'W': (235, 240, 250), 'L': (160, 178, 208), 'D': (84, 96, 130), 'C': (60, 230, 255),
              'B': (40, 110, 220), 'R': (230, 60, 60), 'O': (255, 140, 30), 'Y': (255, 230, 90)}
PLAYER_BODY = [
    ".......W",
    ".......W",
    "......WW",
    "......WC",
    ".....WLC",
    ".....WLC",
    "....WWLL",
    "...BWWLL",
    "..BBWLLD",
    ".BBBWLDD",
    "BBRBWLDD",
    "BRRBLLDD",
    "BR.BDLOD",
    "B..B.DOO",
]
PLAYER_A = PLAYER_BODY + [".......Y"]
PLAYER_B = PLAYER_BODY + [".......Y", ".......O"]

ALIEN_1 = [
    "D.......",
    ".D......",
    "..GGGGGG",
    ".GGGGGGG",
    "GGEEGGGG",
    "GGEKGGGG",
    "GGGGGGGG",
    "G.GDDGDD",
    "G.D.GGG.",
    "D.....G.",
]
ALIEN_2 = [
    "....PPPP",
    "..PPPPPP",
    ".PPLLPPP",
    ".PLLPPPP",
    "PPEEPPPP",
    "PPEKPPPP",
    "PPPPPPYY",
    ".PPDPDPD",
    "..PD.PD.",
    "..D...D.",
]
ALIEN_3 = [
    "......RR",
    "..W..RRR",
    ".WW.RRRR",
    "WWWRRERR",
    "WWWWRKRR",
    ".WWWRRRD",
    "..WW.RDD",
    "....OO..",
]
HEART_MAT = [
    "..RR.",
    ".RWRR",
    "RRRRR",
    "RRRRR",
    ".RRRR",
    "..RRR",
    "...RR",
    "....R",
]
PROJ_MAT = [".W", ".W", "CW", "CW", "CC", ".C"]

A1 = {'G': (60, 220, 70), 'D': (20, 100, 40), 'E': (250, 250, 250), 'K': (20, 20, 40)}
A2 = {'P': (180, 60, 210), 'D': (80, 24, 110), 'L': (225, 150, 245), 'E': (250, 250, 250), 'K': (20, 20, 40), 'Y': (255, 230, 60)}
A3 = {'R': (235, 50, 50), 'W': (240, 235, 225), 'O': (255, 140, 20), 'D': (120, 20, 30), 'E': (255, 240, 80), 'K': (20, 20, 40)}
HP = {'R': (235, 45, 60), 'W': (255, 200, 200)}
PP = {'W': (255, 255, 255), 'C': (0, 230, 255)}

PLAYER_SPR = [Sprite(make_surface(PLAYER_A, PLAYER_PAL, (12, 10, 30))),
              Sprite(make_surface(PLAYER_B, PLAYER_PAL, (12, 10, 30)))]
ALIEN_SPRS = [Sprite(make_surface(ALIEN_1, A1, (6, 30, 16), "EK")),
              Sprite(make_surface(ALIEN_2, A2, (30, 8, 45), "EK")),
              Sprite(make_surface(ALIEN_3, A3, (50, 8, 14), "EK"))]
HEART_IMG = make_surface(HEART_MAT, HP, (60, 6, 20), "W", PIXEL_SCALE)
UI_HEART_IMG = make_surface(HEART_MAT, HP, (60, 6, 20), "W", 1)
PROJ_SPR = Sprite(make_surface(PROJ_MAT, PP, (0, 70, 120), "", 1))
for _s, _g in zip(ALIEN_SPRS, ((40, 210, 80), (190, 70, 230), (255, 70, 50))):
    _s.glow = _g

# --- Colores de nave (ala, franja, cabina) ---
SHIP_COLORS = [
    ("AZUL", (40, 110, 220), (230, 60, 60), (60, 230, 255)),
    ("ROJO", (215, 45, 55), (255, 220, 70), (255, 160, 150)),
    ("VERDE", (40, 180, 80), (240, 240, 80), (150, 255, 170)),
    ("MORADO", (140, 70, 210), (255, 120, 220), (220, 170, 255)),
    ("NARANJA", (240, 130, 30), (60, 70, 210), (255, 230, 120)),
    ("ROSA", (230, 90, 170), (120, 240, 255), (255, 190, 230)),
    ("DORADO", (220, 180, 40), (200, 50, 50), (255, 245, 170)),
    ("ESTELAR", (30, 70, 160), (240, 200, 40), (250, 230, 90)),
    ("NOCHE ESTRELLADA", (40, 80, 190), (250, 215, 90), (255, 245, 170)),   # activa el diseño especial
]
VG_IDX = len(SHIP_COLORS) - 1
ship_idx = 0
SHIP_BIG = None
SHIP_ICON = None


def apply_ship_color(idx):
    global PLAYER_SPR, PROJ_SPR, ship_idx, SHIP_BIG, SHIP_ICON, vg_on
    ship_idx = idx % len(SHIP_COLORS)
    vg_on = (ship_idx == VG_IDX)          # el diseño de Van Gogh es solo un color más
    nm, cb, cr, cc = SHIP_COLORS[ship_idx]
    pal = dict(PLAYER_PAL)
    pal['B'], pal['R'], pal['C'] = cb, cr, cc
    PLAYER_SPR = [Sprite(make_surface(PLAYER_A, pal, (12, 10, 30))),
                  Sprite(make_surface(PLAYER_B, pal, (12, 10, 30)))]
    pp = dict(PP)
    pp['C'] = cc
    PROJ_SPR = Sprite(make_surface(PROJ_MAT, pp, shade(cc, 0.35), "", 1))
    base = PLAYER_SPR[0].base
    SHIP_BIG = pygame.transform.scale(base, (base.get_width() * 3, base.get_height() * 3))
    SHIP_ICON = pygame.transform.scale(base, (int(base.get_width() * 0.75), int(base.get_height() * 0.75)))


apply_ship_color(0)

# Nave de la NOCHE ESTRELLADA: casco crema, alas que laten entre azules y amarillos (6 fases)
VG_SHIP_PAL = {'W': (250, 240, 190), 'L': (120, 165, 230), 'D': (40, 62, 140), 'C': (255, 245, 170),
               'B': (40, 90, 200), 'R': (250, 215, 90), 'O': (255, 170, 40), 'Y': (255, 240, 120)}
_vg_ship = None


def vg_ship_sprites():
    global _vg_ship
    if _vg_ship is None:
        _vg_ship = []
        for k in range(6):
            t = 0.5 + 0.5 * math.sin(k * 1.0472)
            pal = dict(VG_SHIP_PAL)
            pal['B'] = lerp_col((28, 64, 170), (80, 150, 235), t)
            pal['R'] = lerp_col((250, 205, 70), (255, 245, 170), 1.0 - t)
            pal['L'] = lerp_col((100, 150, 225), (170, 205, 245), t)
            _vg_ship.append([Sprite(make_surface(PLAYER_A, pal, (12, 10, 30))),
                             Sprite(make_surface(PLAYER_B, pal, (12, 10, 30)))])
    return _vg_ship

BOSS_MAT = [
    "...........DDMMM",
    ".........DDMMLLL",
    ".......DDMMMLLLL",
    ".....DDMMMMLLLLM",
    "...DDMMMMMMLLMMM",
    ".DDMMMMRRMMMMMMM",
    "DDMMMRRRRMMMEEEE",
    "DMMMMMRRMMMEEEKK",
    "DMMMMMMMMMMMEEKK",
    "DDMMMMMMMMMMMEEE",
    ".DMMMDDMMMMMMMMM",
    ".DDMMMMMMMMMMYYY",
    "..DMMMLLMMMMMYYY",
    "..DDMMMMMMMMMMYY",
    "...DDMMMDDMMMMMM",
    "....DDMMMDMMMMMM",
    ".....DMMDDMMMOOO",
    ".....DD...DDOOOO",
    "......D.....OOOO",
]
BOSS_PAL = {'M': (120, 64, 160), 'L': (180, 120, 220), 'D': (52, 24, 84), 'R': (240, 50, 60),
            'E': (250, 250, 250), 'K': (255, 40, 40), 'Y': (255, 220, 60), 'O': (255, 140, 30)}
BOSS_IMG = make_surface(BOSS_MAT, BOSS_PAL, (20, 5, 35), "EKYO", 3)
_ld(0.48, "Dibujando jefes")


def _tinted(surf, rgb):
    t = surf.copy()
    t.fill((rgb[0], rgb[1], rgb[2], 0), special_flags=pygame.BLEND_RGB_ADD)
    return t.convert_alpha()


BOSS_HIT = _tinted(BOSS_IMG, (130, 130, 130))    # destello al recibir daño
BOSS_RAGE = _tinted(BOSS_IMG, (80, 0, 0))        # fase final (enfurecido)

# --- BOSS 2: TITAN ESCARLATA (cangrejo de roca con garras y núcleo al rojo vivo) ---
BOSS2_MAT = [
    "..D.........DM",
    "..DD.......DMM",
    "..DMD.....DMML",
    "...DMD..DDMMLL",
    "DDD.DMDDMMMMLL",
    "DLLDDMMMMMMMLM",
    "DLLLDMMMRRRMMM",
    "DLLDMMMRRKKRMM",
    ".DDDMMMRKKKKRM",
    "..DDMMMMRKKKKR",
    "...DDMMMMRRRMM",
    "...DMMDDMMMMMM",
    "..DMMDDMMMLMMM",
    "..DDD.DMMMMDDM",
    "...D...DDMMMMD",
    "..........DDDO",
]
BOSS2_PAL = {'M': (175, 60, 50), 'L': (245, 140, 95), 'D': (85, 22, 28), 'R': (255, 200, 60),
             'K': (255, 250, 200), 'O': (255, 140, 30)}

# --- BOSS 3: OJO DEL NUCLEO (cristal flotante con un ojo gigante) ---
BOSS3_MAT = [
    "..........DDDD",
    "........DDLLLL",
    "......DDLLMMMM",
    "....DDLLMMMMMM",
    "..DDLLMMMMMMMM",
    ".DLLMMMMDDDDDD",
    ".DLMMMDDEEEEEE",
    "DLMMMDEEEEKKKK",
    "DLMMMDEEKKKRRR",
    "DLMMMDEEKKRRRR",
    "DLMMMDEEKKRRRR",
    "DLMMMDEEKKKRRR",
    ".DLMMMDEEEEKKK",
    ".DLMMMMDDDEEEE",
    "..DDLLMMMMMDDD",
    "....DDLLMMMMMM",
    "......DDLLMMMM",
    "........DDDDDD",
]
BOSS3_PAL = {'M': (50, 62, 150), 'L': (130, 155, 255), 'D': (18, 18, 60), 'E': (240, 245, 255),
             'K': (255, 70, 220), 'R': (25, 0, 40)}

# --- BOSS 4: CENTINELA GLACIAL (fortaleza de cristal de hielo) ---
BOSS4_MAT = [
    "D.........DLLL",
    "DD.......DLLLL",
    "DLD.....DLMMMM",
    "DLLD..DDLMMMMM",
    "DLLLDDMMMMMMMM",
    ".DLLMMMMMMLLMM",
    ".DMMMMMEEEKKKK",
    "..DMMMMEKKKKKK",
    "..DMMMMMEKKKKK",
    ".DLLMMMMMMLLMM",
    "DLLLDDMMMMMMMM",
    "DLLD..DDMMMMMM",
    "DLD.....DDMMMM",
    "DD.......DDDDD",
]
BOSS4_PAL = {'M': (70, 150, 210), 'L': (190, 235, 255), 'D': (20, 50, 100), 'E': (255, 255, 255), 'K': (110, 255, 255)}
# --- BOSS 5: REINA ENJAMBRE (insecto reina con abdomen de huevos) ---
BOSS5_MAT = [
    "D.D.........DM",
    "DMD........DMM",
    "DMMD...DDDDMML",
    ".DMMDDDMMMMMMM",
    "..DMMMMMMLLMMM",
    "..DMMMMRRRMMMM",
    "...DMMMRKRMMMM",
    "..DDMMMMRRMMMM",
    ".DMMDDMMMMMMMM",
    "DMMD.DDMMYYYMM",
    "DMD...DMMYMYMM",
    "DD....DDMMYYYM",
    "......DDMMMYYY",
    ".......DDMMMMM",
    "........DDDDDD",
]
BOSS5_PAL = {'M': (70, 160, 60), 'L': (160, 230, 90), 'D': (25, 60, 30), 'Y': (255, 220, 60), 'R': (240, 60, 80), 'K': (255, 255, 200)}
# --- BOSS 6: CAZADOR DEL VACIO (manta oscura con ojo magenta) ---
BOSS6_MAT = [
    "DD............",
    "DLDD..........",
    "DLLLDD........",
    ".DLLLMDD......",
    "..DLLMMMDD...D",
    "..DDLMMMMMDDDM",
    "...DLMMMMMMMMM",
    "....DMMMEEEEKK",
    "....DMMEKKKKRR",
    "...DLMMMEKKRRR",
    "..DDLMMMMMMMMM",
    "..DLLMMMMMDDDM",
    ".DLLLMDD....DD",
    "DLLLDD........",
    "DDDD..........",
]
BOSS6_PAL = {'M': (60, 40, 110), 'L': (140, 110, 220), 'D': (20, 10, 45), 'E': (255, 255, 255), 'K': (255, 60, 220), 'R': (30, 0, 50)}
# --- BOSS 7: ARCHI-REACTOR (maquina de acero con dos nucleos) ---
BOSS7_MAT = [
    "..DDDD......DD",
    "..DLLDD....DLL",
    "..DLMMDDDDDLMM",
    "DDDLMMMMMMMLMM",
    "DLLMMMMMMMMMMM",
    "DLMMMDDDDDMMMM",
    "DLMMDOOOOOODMM",
    "DLMMDOYYYKKKDM",
    "DLMMDOYKKKKKDM",
    "DLMMDOYYYKKKDM",
    "DLMMMDDDDDDDMM",
    "DDLMMMMMMMMMMM",
    ".DDMMMMMMDDDMM",
    "..DDMMMDDRRDDD",
    "...DDDDD.DRRRR",
]
BOSS7_PAL = {'M': (150, 155, 175), 'L': (225, 230, 245), 'D': (45, 48, 70), 'O': (255, 140, 30), 'Y': (255, 230, 60), 'K': (255, 255, 220), 'R': (230, 50, 40)}
# --- BOSS 8: EMPERADOR GALACTICO (corona dorada y gema roja) ---
BOSS8_MAT = [
    "..D.....D...DD",
    "..DD...DLD..DY",
    "..DLD.DLLLDDYY",
    "..DLLDLLYLLLYY",
    "..DLLLLLLLLLLL",
    "...DDDDDDDDDDD",
    "...DMMMMMMMMMM",
    "..DMMMLLMMMMMM",
    ".DMMMEEEEEEMMM",
    ".DMMEEKKKKEEMM",
    "DDMMEKKRRKKEMM",
    "DLMMEKRRRRKEMM",
    "DLMMMEKKKKEEMM",
    ".DLMMMEEEEMMMM",
    ".DDMMMMMMMMMMM",
    "..DDMMMMDDMMYY",
    "...DDDMMMDDMMY",
    ".....DDDDDDDDD",
]
BOSS8_PAL = {'M': (200, 150, 40), 'L': (255, 225, 110), 'D': (80, 50, 10), 'Y': (255, 245, 150), 'E': (255, 255, 255), 'K': (255, 120, 120), 'R': (230, 30, 60)}
for _m in (BOSS2_MAT, BOSS3_MAT, BOSS4_MAT, BOSS5_MAT, BOSS6_MAT, BOSS7_MAT, BOSS8_MAT):
    for _row in _m:
        assert len(_row) == 14, _row


def _boss_set(mat, pal, noshade):
    img = make_surface(mat, pal, (20, 5, 35), noshade, 3)
    return (img, _tinted(img, (130, 130, 130)), _tinted(img, (80, 0, 0)))


BOSS_SETS = {1: (BOSS_IMG, BOSS_HIT, BOSS_RAGE),
             2: _boss_set(BOSS2_MAT, BOSS2_PAL, "RKO"),
             3: _boss_set(BOSS3_MAT, BOSS3_PAL, "EKR"),
             4: _boss_set(BOSS4_MAT, BOSS4_PAL, "EK"),
             5: _boss_set(BOSS5_MAT, BOSS5_PAL, "RKY"),
             6: _boss_set(BOSS6_MAT, BOSS6_PAL, "EKR"),
             7: _boss_set(BOSS7_MAT, BOSS7_PAL, "OYKR"),
             8: _boss_set(BOSS8_MAT, BOSS8_PAL, "EKRY")}
NUM_BOSSES = 8
BOSS_ICONS = [pygame.transform.scale(BOSS_SETS[_k][0], (42, 26)) for _k in range(1, NUM_BOSSES + 1)]
BOSS_NAMES = {1: "CENTINELA ALFA", 2: "TITAN ESCARLATA", 3: "OJO DEL NUCLEO", 4: "CENTINELA GLACIAL",
              5: "REINA ENJAMBRE", 6: "CAZADOR DEL VACIO", 7: "ARCHI-REACTOR", 8: "EMPERADOR GALACTICO"}

# =====================================================================
#  FONDOS (se pre-renderizan UNA vez)
# =====================================================================
def bake_vignette(bg, strength=120):
    """Oscurece suavemente los bordes (se hornea UNA vez en el fondo: coste cero por frame)."""
    v = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    steps = 46
    for i in range(steps):
        a = int(strength * (1.0 - i / float(steps)) ** 2)
        ix = int(i * WIDTH / float(HEIGHT))
        pygame.draw.rect(v, (0, 0, 12, a), (ix, i, WIDTH - 2 * ix, HEIGHT - 2 * i), 2)
    bg.blit(v, (0, 0))


def make_nebula(color, radius, amax=46):
    s = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    for r in range(radius, 0, -3):
        t = 1.0 - r / float(radius)
        pygame.draw.circle(s, (color[0], color[1], color[2], int(amax * t * t)), (radius, radius), r)
    return s.convert_alpha()


def bake_planet(surf, cx, cy, r, bands):
    """Planeta con sombreado suave, bandas, terminador y atmósfera."""
    lx, ly = -0.55, -0.6
    n = len(bands) - 1
    for y in range(-r, r + 1):
        for x in range(-r, r + 1):
            d2 = x * x + y * y
            if d2 <= r * r:
                nz = math.sqrt(max(0.0, r * r - d2)) / r
                l = (x / float(r)) * lx + (y / float(r)) * ly + nz * 0.62
                t = (l + 0.25) / 1.1 + 0.03 * math.sin(y * 0.9 + x * 0.1)
                t = max(0.0, min(0.999, t))
                i = int(t * n)
                f = t * n - i
                c = [int(bands[i][k] + (bands[i + 1][k] - bands[i][k]) * f) for k in range(3)]
                rim = max(0.0, 0.35 - nz) / 0.35
                if rim > 0 and l > -0.1:
                    c = [min(255, int(c[0] + 70 * rim)), min(255, int(c[1] + 90 * rim)), min(255, int(c[2] + 120 * rim))]
                surf.set_at((cx + x, cy + y), (c[0], c[1], c[2]))


def make_bg():
    bg = pygame.Surface((WIDTH, HEIGHT))
    for y in range(HEIGHT):
        t = y / float(HEIGHT)
        pygame.draw.line(bg, (int(6 + 14 * t), int(5 + 7 * t), int(20 + 32 * t)), (0, y), (WIDTH, y))
    n1 = make_nebula((110, 20, 200), int(HEIGHT * 0.5))
    n2 = make_nebula((0, 130, 255), int(HEIGHT * 0.4))
    n3 = make_nebula((200, 40, 120), int(HEIGHT * 0.3), 36)
    bg.blit(n1, (int(WIDTH * 0.15) - n1.get_width() // 2, int(HEIGHT * 0.3) - n1.get_height() // 2))
    bg.blit(n2, (int(WIDTH * 0.8) - n2.get_width() // 2, int(HEIGHT * 0.75) - n2.get_height() // 2))
    bg.blit(n3, (int(WIDTH * 0.55) - n3.get_width() // 2, int(HEIGHT * 0.2) - n3.get_height() // 2))
    bake_planet(bg, int(WIDTH * 0.88), int(HEIGHT * 0.2), 20,
                [(40, 20, 70), (80, 40, 130), (130, 80, 190), (190, 140, 235)])
    bake_planet(bg, int(WIDTH * 0.1), int(HEIGHT * 0.78), 11,
                [(60, 30, 20), (120, 60, 30), (190, 110, 50), (240, 170, 90)])
    bake_vignette(bg)
    return bg.convert()


bg_game = make_bg()
_ld(0.6, "Creando planetas")


# =====================================================================
#  DISEÑO ESPECIAL: "LA NOCHE ESTRELLADA" (Van Gogh)
#  Cielo de pinceladas en remolino + estrellas con halos + luna creciente
# =====================================================================
vg_on = False       # lo decide el color de nave elegido (NOCHE ESTRELLADA)


def _make_starry_raw():
    bg = pygame.Surface((WIDTH, HEIGHT))
    for y in range(HEIGHT):
        t = y / float(HEIGHT)
        pygame.draw.line(bg, (int(8 + 12 * t), int(16 + 26 * t), int(52 + 52 * t)), (0, y), (WIDTH, y))
    vort = [(WIDTH * 0.32, HEIGHT * 0.40, HEIGHT * 0.30, 1.0),
            (WIDTH * 0.60, HEIGHT * 0.28, HEIGHT * 0.20, -1.0),
            (WIDTH * 0.82, HEIGHT * 0.66, HEIGHT * 0.22, 1.0)]
    pal = [(10, 22, 78), (24, 52, 128), (44, 92, 172), (96, 150, 206), (214, 222, 176)]
    rnd = random.Random(7)

    def flow(x, y):
        ax = 0.9 + math.cos(y * 0.05) * 0.5
        ay = math.sin(x * 0.04) * 0.5
        glow = 0.0
        for vx, vy, rr, sg in vort:
            dx, dy = x - vx, y - vy
            d = math.hypot(dx, dy) + 0.01
            w = math.exp(-(d / rr) ** 2)
            ax += -dy / d * sg * w * 3.0
            ay += dx / d * sg * w * 3.0
            glow += w
        return math.atan2(ay, ax), glow

    for _i in range(2600):
        x, y = rnd.uniform(0, WIDTH), rnd.uniform(0, HEIGHT)
        a, glow = flow(x, y)
        col = pal[int(max(0, min(4, glow * 3.2 + rnd.uniform(-0.9, 1.0))))]
        for _j in range(7):
            a, _g = flow(x, y)
            nx, ny = x + math.cos(a) * 3.2, y + math.sin(a) * 3.2
            pygame.draw.line(bg, col, (int(x), int(y)), (int(nx), int(ny)), 2)
            x, y = nx, ny
    # luna creciente con resplandor
    mx, my = int(WIDTH * 0.89), int(HEIGHT * 0.17)
    glow_s = pygame.Surface((96, 96), pygame.SRCALPHA)
    for r in range(46, 0, -2):
        pygame.draw.circle(glow_s, (255, 200, 70, int(110 * (1 - r / 46.0) ** 1.5)), (48, 48), r)
    bg.blit(glow_s, (mx - 48, my - 48))
    tmp = pygame.Surface((44, 44))
    tmp.fill((255, 0, 255))
    tmp.set_colorkey((255, 0, 255))
    pygame.draw.circle(tmp, (250, 215, 80), (22, 22), 17)
    pygame.draw.circle(tmp, (255, 0, 255), (29, 17), 15)
    bg.blit(tmp, (mx - 22, my - 22))
    bake_vignette(bg, 100)
    return bg.convert()


def make_vg_halo(R, pulse):
    S = 2 * R + 8
    s = pygame.Surface((S, S), pygame.SRCALPHA)
    c = S // 2
    top = R + pulse
    for r in range(top, 0, -1):
        t = 1.0 - r / float(top)
        k = min(1.0, t * 1.5)
        col = (int(70 + 180 * k), int(110 + 105 * k), int(200 - 110 * k))
        if t > 0.8:
            col = (255, 250, 200)
        a = int(30 + 190 * t)
        if (r // 3) % 2 == 0:
            a = int(a * 0.55)
        pygame.draw.circle(s, (col[0], col[1], col[2], a), (c, c), r)
    return s.convert_alpha()


def make_vg_hills():
    h = int(HEIGHT * 0.3)
    s = pygame.Surface((WIDTH, h), pygame.SRCALPHA)

    def ground(x):
        return int(h * 0.6 + math.sin(x * 0.018) * h * 0.10 + math.sin(x * 0.007 + 1) * h * 0.12)
    pts = [(0, h)] + [(x, ground(x)) for x in range(0, WIDTH + 8, 8)] + [(WIDTH, h)]
    pygame.draw.polygon(s, (6, 12, 36), pts)
    pygame.draw.lines(s, (30, 70, 140), False, pts[1:-1], 2)
    rr = random.Random(3)
    for _i in range(18):
        x = rr.randint(6, WIDTH - 6)
        pygame.draw.rect(s, (250, 215, 90), (x, ground(x) + rr.randint(6, 18), 2, 3))
    cx = int(WIDTH * 0.045)          # el ciprés
    pygame.draw.polygon(s, (4, 10, 24), [(cx - 7, h), (cx - 10, h - 24), (cx - 6, h - 56), (cx, h - 84),
                                         (cx + 6, h - 56), (cx + 10, h - 24), (cx + 7, h)])
    pygame.draw.line(s, (20, 50, 70), (cx - 3, h - 60), (cx - 6, h - 28), 1)
    return s.convert_alpha()


VG_STAR_POS = [(0.10, 0.20, 12), (0.28, 0.11, 9), (0.46, 0.30, 14), (0.64, 0.12, 10), (0.76, 0.46, 12),
               (0.20, 0.58, 9), (0.55, 0.66, 11), (0.92, 0.72, 9), (0.37, 0.86, 10), (0.70, 0.90, 8)]
def make_starry_bg():
    try:
        d = os.path.dirname(os.path.abspath(__file__))
    except Exception:
        d = os.getcwd()
    path = os.path.join(d, "starry_cache_%dx%d_v3.png" % (WIDTH, HEIGHT))
    try:
        img = pygame.image.load(path)
        if img.get_size() == (WIDTH, HEIGHT):
            return img.convert()
    except Exception:
        pass
    bg = _make_starry_raw()
    try:
        pygame.image.save(bg, path)
    except Exception:
        pass
    return bg


bg_vg = make_starry_bg()
VG_HALOS = [(make_vg_halo(R, 0), make_vg_halo(R, 2), int(WIDTH * fx), int(HEIGHT * fy))
            for fx, fy, R in VG_STAR_POS]
vg_hills = make_vg_hills()


def make_vg_streaks():
    """Capa de pinceladas translúcidas que se desplaza despacio sobre el cielo."""
    sf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    rr = random.Random(11)
    cols = [(150, 200, 240), (250, 225, 120), (90, 140, 220), (230, 235, 190)]
    for _i in range(150):
        x, y = rr.uniform(0, WIDTH), rr.uniform(0, HEIGHT)
        amp, ph, ln = rr.uniform(2, 6), rr.uniform(0, 6.28), rr.randint(18, 46)
        col, al = rr.choice(cols), rr.randint(45, 90)
        pts = [(int(x + i * 3), int(y + math.sin(ph + i * 0.5) * amp)) for i in range(ln // 3)]
        if len(pts) > 1:
            pygame.draw.lines(sf, (col[0], col[1], col[2], al), False, pts, 2)
    return sf.convert_alpha()


VG_STREAKS = make_vg_streaks()
_ld(0.72, "Encendiendo estrellas")


_vg_sky = pygame.Surface((WIDTH, HEIGHT)).convert()
_vg_sky_stamp = -999


def draw_vg_stars(target):
    for i, (ha, hb, x, y) in enumerate(VG_HALOS):
        h = ha if ((frame // 12) + i) % 2 == 0 else hb
        ox = int(math.sin(frame * 0.03 + i * 1.7) * 2)
        oy = int(math.cos(frame * 0.027 + i * 2.3) * 2)
        target.blit(h, h.get_rect(center=(x + ox, y + oy)))


def draw_vg_sky():
    """Cielo vivo y BARATO: bandas ondulantes + pinceladas + halos se componen en una superficie
    que solo se refresca cada 3 frames (5 si el juego va lento); el resto de frames es 1 solo blit."""
    global _vg_sky_stamp
    if QUALITY == 0:
        canvas.blit(bg_vg, (0, 0))
        draw_vg_stars(canvas)
        return
    if frame - _vg_sky_stamp >= (3 if QUALITY == 2 else 5):
        _vg_sky_stamp = frame
        t = _vg_sky
        band = 12 if QUALITY == 2 else 16
        for y in range(0, HEIGHT, band):
            area = pygame.Rect(0, y, WIDTH, min(band, HEIGHT - y))
            ox = int(round(math.sin(frame * 0.018 + y * 0.045) * 3 + math.sin(frame * 0.007 + y * 0.02) * 2))
            t.blit(bg_vg, (ox, y), area)
            if ox > 0:
                t.blit(bg_vg, (ox - WIDTH, y), area)
            elif ox < 0:
                t.blit(bg_vg, (ox + WIDTH, y), area)
        if QUALITY >= 2:
            sx = int(frame * 0.35) % WIDTH
            sy = int(math.sin(frame * 0.02) * 3)
            t.blit(VG_STREAKS, (-sx, sy))
            t.blit(VG_STREAKS, (WIDTH - sx, sy))
        draw_vg_stars(t)
    canvas.blit(_vg_sky, (0, 0))

# Planeta del menú (solo la franja visible, con brillo de atmósfera)
_p_r = int(WIDTH * 0.5)
_planet_top = int(HEIGHT - WIDTH * 0.1)
_p_cy = int(HEIGHT + WIDTH * 0.4) - _planet_top
planet_surf = pygame.Surface((WIDTH, HEIGHT - _planet_top), pygame.SRCALPHA)
_pcols = [(60, 190, 215), (0, 130, 155), (0, 90, 115), (0, 62, 84), (0, 38, 58)]
for _k in range(5):
    pygame.draw.circle(planet_surf, _pcols[_k], (WIDTH // 2, _p_cy - 3 * _k), _p_r - 6 * _k)
pygame.draw.circle(planet_surf, CYAN, (WIDTH // 2, _p_cy), _p_r, 2)
planet_surf = planet_surf.convert_alpha()

# Estrellas con 3 capas de profundidad
STAR_COLS = [(90, 90, 130), (150, 150, 200), (235, 235, 255)]
STAR_SPD = [0.25, 0.5, 0.9]
STAR_SIZE = [1, 1, 2]
STAR_COLS_VG = [(70, 100, 170), (150, 180, 230), (255, 235, 130)]
stars = []
for _ in range(70):
    layer = random.choice([0, 0, 0, 1, 1, 2])
    stars.append([random.uniform(0, WIDTH), random.uniform(0, HEIGHT), STAR_SPD[layer],
                  STAR_SIZE[layer], layer, random.randint(0, 3)])

comets = []


class Comet:
    def __init__(self):
        self.x = float(random.randint(0, WIDTH))
        self.y = -16.0
        self.dx = random.uniform(-0.4, 0.4)
        self.dy = random.uniform(2, 4)
        m = math.hypot(self.dx, self.dy)
        self.ux, self.uy = self.dx / m, self.dy / m
        self.color = random.choice([CYAN, WHITE, (200, 200, 255)])
        self.length = random.uniform(20, 45)

    def update(self, speed_mult):
        self.x += self.dx * speed_mult
        self.y += self.dy * speed_mult

    def draw(self, surface):
        n = 5
        for i in range(n):
            k = 1.0 - i / float(n)
            col = (int(self.color[0] * k), int(self.color[1] * k), int(self.color[2] * k))
            a = self.length * i / n
            b = self.length * (i + 1) / n
            pygame.draw.line(surface, col, (int(self.x - self.ux * a), int(self.y - self.uy * a)),
                             (int(self.x - self.ux * b), int(self.y - self.uy * b)), 2 if i < 2 else 1)
        add_glow(surface, self.x, self.y, self.color, 10, 0.8, 1)
        pygame.draw.rect(surface, WHITE, (int(self.x) - 1, int(self.y) - 1, 2, 2))


# =====================================================================
#  CONTROLES Y BOTONES
# =====================================================================
def vg_sparks(surface, rect, circle, n=3, speed=0.012, seed=0.0):
    """Chispas amarillas/azules que recorren el borde de un elemento (solo con NOCHE ESTRELLADA)."""
    if QUALITY < 1:
        return
    cx, cy = rect.centerx, rect.centery
    w, h = rect.width, rect.height
    rad = min(w, h) // 2 + 2
    per = 2.0 * (w + h)
    for k in range(n):
        t = (frame * speed + k / float(n) + seed) % 1.0
        for tail in range(3):                      # cola corta
            tt = (t - tail * 0.012) % 1.0
            if circle:
                a = tt * 6.2832
                x, y = cx + math.cos(a) * rad, cy + math.sin(a) * rad
            else:
                d = tt * per
                if d < w:
                    x, y = rect.left + d, rect.top
                elif d < w + h:
                    x, y = rect.right, rect.top + (d - w)
                elif d < 2 * w + h:
                    x, y = rect.right - (d - w - h), rect.bottom
                else:
                    x, y = rect.left, rect.bottom - (d - 2 * w - h)
            col = shade(VG_SPARK[(k + tail) % len(VG_SPARK)], 1.0 - tail * 0.3)
            sz = 3 - tail if tail < 2 else 1
            pygame.draw.rect(surface, col, (int(x) - sz // 2, int(y) - sz // 2, sz, sz))


class VirtualJoystick:
    def __init__(self, x, y, radius):
        self.base_pos = (int(x), int(y))
        self.radius = radius
        self.stick_pos = list(self.base_pos)
        self.touch_id = None
        self.vector = [0, 0]

    def process_event(self, e_type, tid, tx, ty):
        if e_type == 'down':
            if math.hypot(tx - self.base_pos[0], ty - self.base_pos[1]) < self.radius * 1.5:
                self.touch_id = tid
                self.update_stick(tx, ty)
        elif e_type == 'motion':
            if self.touch_id == tid:
                self.update_stick(tx, ty)
        elif e_type == 'up':
            if self.touch_id == tid:
                self.reset()

    def update_stick(self, tx, ty):
        dx = tx - self.base_pos[0]
        dy = ty - self.base_pos[1]
        dist = math.hypot(dx, dy)
        if dist > self.radius:
            dx = (dx / dist) * self.radius
            dy = (dy / dist) * self.radius
        self.stick_pos = [self.base_pos[0] + dx, self.base_pos[1] + dy]
        if dist > 0:
            self.vector = [dx / self.radius, dy / self.radius]
        else:
            self.vector = [0, 0]

    def reset(self):
        self.touch_id = None
        self.stick_pos = list(self.base_pos)
        self.vector = [0, 0]

    def draw(self, surface):
        bp = self.base_pos
        r = int(self.radius)
        base = joy_base_surface(r)
        surface.blit(base, base.get_rect(center=bp))
        sx, sy = int(self.stick_pos[0]), int(self.stick_pos[1])
        sr = int(self.radius * 0.4)
        d = dome_surface(sr, (110, 120, 160), CYAN)
        surface.blit(d, d.get_rect(center=(sx, sy)))
        if vg_on:
            vg_sparks(surface, pygame.Rect(bp[0] - r, bp[1] - r, 2 * r, 2 * r), True, 6, 0.008)


_dome_cache = {}
_btn_cache = {}
_joy_cache = {}


def lerp_col(a, b, t):
    t = max(0.0, min(1.0, t))
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def dome_surface(r, color, rim):
    """Bola con volumen (luz arriba-izquierda), borde metálico y brillo."""
    key = (r, color, rim)
    s = _dome_cache.get(key)
    if s is not None:
        return s
    S = r * 2 + 4
    s = pygame.Surface((S, S), pygame.SRCALPHA)
    c = S // 2
    pygame.draw.circle(s, (10, 8, 24), (c, c), r + 1)
    pygame.draw.circle(s, shade(rim, 0.55), (c, c), r)
    fr = max(1, r - 2)
    dark, light = shade(color, 0.55), shade(color, 1.45)
    for i in range(fr, 0, -1):
        t = 1.0 - i / float(fr)
        off = int(t * fr * 0.3)
        pygame.draw.circle(s, lerp_col(dark, light, t), (c - off, c - off), i)
    pygame.draw.circle(s, (255, 255, 255), (c - r // 3, c - r // 3), max(1, r // 5))
    pygame.draw.circle(s, rim, (c, c), r, 1)
    s = s.convert_alpha()
    _dome_cache[key] = s
    return s


def joy_base_surface(r):
    s = _joy_cache.get(r)
    if s is not None:
        return s
    S = 2 * r + 6
    c = S // 2
    s = pygame.Surface((S, S), pygame.SRCALPHA)
    pygame.draw.circle(s, (8, 8, 22), (c, c), r + 2)
    for i in range(r, 2, -3):
        col = (22, 26, 50) if (i // 3) % 2 else (30, 34, 62)
        pygame.draw.circle(s, col, (c, c), i)
    for k in range(24):
        a = 6.2832 * k / 24.0
        ca, sa = math.cos(a), math.sin(a)
        pygame.draw.line(s, (0, 120, 140), (int(c + ca * (r - 6)), int(c + sa * (r - 6))),
                         (int(c + ca * (r - 2)), int(c + sa * (r - 2))))
    pygame.draw.circle(s, DARK_GRAY, (c, c), max(2, r - 11), 1)
    pygame.draw.circle(s, CYAN, (c, c), r, 2)
    for ox, oy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        px, py = c + ox * (r - 9), c + oy * (r - 9)
        pygame.draw.polygon(s, CYAN, [(px, py - 3), (px + 3, py), (px, py + 3), (px - 3, py)])
    s = s.convert_alpha()
    _joy_cache[r] = s
    return s


def button_surface(w, h, circle, bg, border):
    """Panel metálico con degradado, rayado diagonal, biseles y remaches (se dibuja UNA vez y se cachea)."""
    key = (w, h, circle, bg, border)
    s = _btn_cache.get(key)
    if s is not None:
        return s
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    hi = shade(bg, 1.5)
    lo = shade(bg, 0.55)
    if circle:
        rad = min(w, h) // 2
        c = (w // 2, h // 2)
        pygame.draw.circle(s, (8, 8, 20), c, rad)
        pygame.draw.circle(s, shade(border, 0.5), c, rad - 1)
        nt = max(16, rad // 2)
        for k in range(nt):                      # anillo moleteado
            a = 6.2832 * k / nt
            ca, sa = math.cos(a), math.sin(a)
            pygame.draw.line(s, shade(border, 0.22), (int(c[0] + ca * (rad - 7)), int(c[1] + sa * (rad - 7))),
                             (int(c[0] + ca * (rad - 3)), int(c[1] + sa * (rad - 3))))
        pygame.draw.circle(s, (10, 10, 24), c, rad - 8)
        fr = max(1, rad - 9)
        for i in range(fr, 0, -1):               # cúpula con degradado y anillos finos
            t = 1.0 - i / float(fr)
            off = int(t * fr * 0.28)
            col = lerp_col(lo, hi, t * 0.9)
            if i % 4 == 0:
                col = shade(col, 0.9)
            pygame.draw.circle(s, col, (c[0] - off, c[1] - off), i)
        pygame.draw.circle(s, shade(hi, 1.25), (c[0] - fr // 3, c[1] - fr // 3), max(1, fr // 9))
        pygame.draw.circle(s, border, c, rad - 1, 2)
    else:
        ch = 3 if h < 40 else 4

        def poly(i):
            return [(ch + i, i), (w - 1 - ch - i, i), (w - 1 - i, ch + i), (w - 1 - i, h - 1 - ch - i),
                    (w - 1 - ch - i, h - 1 - i), (ch + i, h - 1 - i), (i, h - 1 - ch - i), (i, ch + i)]
        pygame.draw.polygon(s, (8, 8, 20), poly(0))
        pygame.draw.polygon(s, shade(border, 0.55), poly(1))
        g = pygame.Surface((w, h))
        for y in range(h):
            pygame.draw.line(g, lerp_col(hi, lo, y / float(max(1, h - 1))), (0, y), (w, y))
        dg = shade(bg, 0.8)
        for x in range(-h, w, 7):                # rayado diagonal (textura)
            pygame.draw.line(g, dg, (x, h), (x + h, 0))
        g = g.convert_alpha()
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.polygon(mask, (255, 255, 255, 255), poly(3))
        g.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        s.blit(g, (0, 0))
        pygame.draw.line(s, shade(bg, 1.9), (ch + 3, 3), (w - ch - 4, 3))
        pygame.draw.line(s, shade(bg, 0.4), (ch + 3, h - 4), (w - ch - 4, h - 4))
        pygame.draw.polygon(s, border, poly(2), 1)
        if w >= 70 and h >= 28:                   # remaches
            for rx, ry in ((6, 6), (w - 8, 6), (6, h - 8), (w - 8, h - 8)):
                pygame.draw.rect(s, (60, 64, 84), (rx + 1, ry + 1, 2, 2))
                pygame.draw.rect(s, (205, 210, 225), (rx, ry, 2, 2))
    s = s.convert_alpha()
    _btn_cache[key] = s
    return s


class ModernButton:
    def __init__(self, x, y, w, h, text="", is_circle=False, is_nuke=False, is_dash=False):
        self.rect = pygame.Rect(0, 0, int(w), int(h))
        self.rect.center = (int(x), int(y))
        self.is_pressed = False
        self.touch_id = None
        self.text = text
        self.is_circle = is_circle
        self.is_nuke = is_nuke
        self.is_dash = is_dash
        self.active = False      # botón tipo interruptor encendido

    def process_event(self, e_type, tid, tx, ty):
        if e_type == 'down':
            if self.rect.collidepoint(tx, ty):
                self.touch_id = tid
                self.is_pressed = True
                return True
        elif e_type == 'up':
            if self.touch_id == tid:
                self.touch_id = None
                self.is_pressed = False
        return False

    def draw(self, surface, nuke_ready=False, nuke_progress=0.0):
        bg_color = (60, 100, 130) if self.is_pressed else (34, 44, 70)
        border_color = CYAN
        text_color = WHITE

        if self.active:
            bg_color = (0, 120, 150)
            border_color = YELLOW

        if self.is_nuke:
            if nuke_ready:
                bg_color = (200, 100, 0) if self.is_pressed else ORANGE
                border_color = YELLOW
            else:
                bg_color = (36, 36, 44)
                border_color = (90, 90, 100)
                text_color = (150, 150, 160)
        elif self.is_dash:
            if nuke_ready:
                bg_color = (20, 110, 200) if self.is_pressed else (40, 150, 235)
                border_color = (150, 230, 255)
            else:
                bg_color = (36, 36, 44)
                border_color = (90, 90, 100)
                text_color = (150, 150, 160)

        r = self.rect
        if vg_on:                                   # NOCHE ESTRELLADA: la interfaz ondea suavemente
            ph = r.centerx * 0.035 + r.centery * 0.025
            r = r.move(int(round(math.sin(frame * 0.05 + ph) * 2)), int(round(math.cos(frame * 0.042 + ph * 1.3) * 2)))
        charge_btn = self.is_circle and (self.is_nuke or self.is_dash)
        if charge_btn and nuke_ready:
            pygame.draw.circle(surface, shade(border_color, 0.6), r.center, r.width // 2 + 2 + (frame // 8) % 2, 1)
        surface.blit(button_surface(r.width, r.height, self.is_circle, bg_color, border_color), r.topleft)

        if charge_btn and not nuke_ready:
            # el botón (gris) se va llenando de color desde abajo, como un líquido
            p = max(0.0, min(1.0, nuke_progress))
            if self.is_nuke:
                fbg, fbd = ORANGE, YELLOW
            else:
                fbg, fbd = (40, 150, 235), (150, 230, 255)
            fh = int(r.height * p)
            if fh > 0:
                col_img = button_surface(r.width, r.height, True, fbg, fbd)
                surface.blit(col_img, (r.left, r.top + r.height - fh), pygame.Rect(0, r.height - fh, r.width, fh))
                if fh < r.height - 6:                    # línea brillante en el nivel del "líquido"
                    rad = r.width // 2 - 3
                    dy = r.height // 2 - (r.height - fh)
                    if abs(dy) < rad:
                        hw = int(math.sqrt(rad * rad - dy * dy))
                        ly = r.top + r.height - fh
                        pygame.draw.line(surface, shade(fbg, 1.7), (r.centerx - hw, ly), (r.centerx + hw, ly), 1)
            if p >= 0.5:
                text_color = WHITE

        if self.text:
            ts = text_surf(font_medium, self.text, text_color)
            surface.blit(ts, ts.get_rect(center=(r.centerx, r.centery + (1 if self.is_pressed else 0))))

        if vg_on and r.width >= 24:
            vg_sparks(surface, r, self.is_circle, 3 if r.width < 120 else 4, 0.010, (r.centerx * 0.013) % 1.0)


# =====================================================================
#  ENTIDADES
# =====================================================================
frame = 0


VG_SPARK = [(250, 220, 80), (255, 245, 170), (110, 160, 235), (60, 100, 200), (255, 255, 255)]


class Particle:
    def __init__(self, x, y, dx, dy, is_explosion=False):
        self.x = float(x)
        self.y = float(y)
        self.dx = float(dx)
        self.dy = float(dy)
        self.max_life = random.randint(15, 30) if is_explosion else 15
        self.life = self.max_life
        self.curl = 0.0
        if vg_on:                       # chispas azules y amarillas que giran en espiral
            self.color = random.choice(VG_SPARK)
            if is_explosion:
                self.curl = random.choice((-0.16, 0.16))
        elif not is_explosion:
            self.color = random.choice([ORANGE, YELLOW, RED])
        else:
            self.color = random.choice([GREEN, CYAN, WHITE, YELLOW])
        self.size = random.uniform(1.5, 3.5)
        self.fancy = is_explosion and random.random() < 0.3      # estas chispas brillan

    def update(self):
        if self.curl:
            c, s = math.cos(self.curl), math.sin(self.curl)
            self.dx, self.dy = self.dx * c - self.dy * s, self.dx * s + self.dy * c
        self.x += self.dx
        self.y += self.dy
        self.life -= 1
        self.size = max(0.0, self.size - 0.07)

    def draw(self, surface):
        if self.life > 0:
            s = int(self.size + 0.5)
            if s >= 1:
                k = 0.35 + 0.65 * self.life / self.max_life
                c = (int(self.color[0] * k), int(self.color[1] * k), int(self.color[2] * k))
                pygame.draw.rect(surface, c, (int(self.x), int(self.y), s, s))
                if self.fancy:
                    add_glow(surface, self.x, self.y, self.color, 8, k, 2)


class XPOrb:
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.rect = pygame.Rect(int(x - 4), int(y - 4), 8, 8)
        self.dx = random.uniform(-0.7, 0.7)
        self.dy = random.uniform(-0.7, 0.7)
        self.speed = HEIGHT * 0.005

    def update(self, px, py):
        dist = math.hypot(px - self.x, py - self.y)
        if dist < HEIGHT * 0.25:
            angle = math.atan2(py - self.y, px - self.x)
            self.x += math.cos(angle) * self.speed * 1.5
            self.y += math.sin(angle) * self.speed * 1.5
        else:
            self.x += self.dx
            self.y += self.dy
            self.dx *= 0.96
            self.dy *= 0.96
        self.rect.centerx = int(self.x)
        self.rect.centery = int(self.y)

    def draw(self, surface):
        x, y = int(self.x), int(self.y)
        r = 4 if (frame // 6) % 2 == 0 else 3
        add_glow(surface, x, y, (0, 200, 255), 12, 0.8, 2)
        pygame.draw.polygon(surface, (0, 110, 150), [(x, y - r - 1), (x + r + 1, y), (x, y + r + 1), (x - r - 1, y)])
        pygame.draw.polygon(surface, CYAN, [(x, y - r), (x + r, y), (x, y + r), (x - r, y)])
        pygame.draw.rect(surface, WHITE, (x - 1, y - 1, 2, 2))


DASH_COOLDOWN = 600                 # 10 segundos a 60 fps (base)
DASH_FRAMES = 14                    # duración de la embestida
DASH_SPEED = HEIGHT * 0.034         # ~12 px por frame
DASH_BOSS_DAMAGE = 5

BOOST_FRAMES = 300                  # 5 segundos a 60 fps
BOOST_MULT = 1.7
SHIELD_R = 24


def make_shield(vg):
    S = SHIELD_R * 2 + 8
    s = pygame.Surface((S, S), pygame.SRCALPHA)
    c = S // 2
    if vg:
        pygame.draw.circle(s, (40, 80, 190, 60), (c, c), SHIELD_R)
        for k in range(24):
            a0, a1 = k * 0.2618, (k + 1) * 0.2618 + 0.02
            col = (250, 215, 90, 230) if k % 2 == 0 else (110, 160, 240, 230)
            pygame.draw.line(s, col, (int(c + math.cos(a0) * SHIELD_R), int(c + math.sin(a0) * SHIELD_R)),
                             (int(c + math.cos(a1) * SHIELD_R), int(c + math.sin(a1) * SHIELD_R)), 3)
        pygame.draw.circle(s, (250, 215, 90, 120), (c, c), SHIELD_R - 4, 1)
    else:
        pygame.draw.circle(s, (70, 170, 255, 55), (c, c), SHIELD_R)
        pygame.draw.circle(s, (120, 210, 255, 120), (c, c), SHIELD_R - 3, 1)
        pygame.draw.circle(s, (190, 240, 255, 240), (c, c), SHIELD_R, 2)
        pygame.draw.arc(s, (255, 255, 255, 255), (c - SHIELD_R + 3, c - SHIELD_R + 3, 2 * SHIELD_R - 6, 2 * SHIELD_R - 6),
                        0.6, 1.5, 2)
    return s.convert_alpha()


SHIELD_IMG = make_shield(False)
SHIELD_VG = make_shield(True)


# =====================================================================
#  TIENDA: potenciadores PERMANENTES que se compran con monedas
#  (las monedas se ganan en el modo INFINITO: 0.25 por alien)
#  Las monedas se guardan en "cuartos" (4 cuartos = 1 moneda) para no tener errores de decimales.
# =====================================================================
UPGRADES = [
    {"key": "life", "name": "VIDA EXTRA", "cost": (10, 25),
     "desc": ("Empiezas con 4 corazones", "Empiezas con 5 corazones")},
    {"key": "shield", "name": "ESCUDO INICIAL", "cost": (12,),
     "desc": ("Empiezas con escudo",)},
    {"key": "wave", "name": "ONDA RAPIDA", "cost": (8, 18),
     "desc": ("Onda con 8 cargas", "Onda con 6 cargas")},
    {"key": "dash", "name": "IMPULSO RAPIDO", "cost": (8, 18),
     "desc": ("Recarga de 8 segundos", "Recarga de 6 segundos")},
    {"key": "fire", "name": "DISPARO RAPIDO", "cost": (10, 22),
     "desc": ("Disparas mas rapido", "Disparas aun mas rapido")},
]
upg = {_u["key"]: 0 for _u in UPGRADES}
coins_q = 0             # saldo (en cuartos de moneda)
run_coins_q = 0         # ganado en la partida actual
coins_dirty = False
coin_pops = []


def max_lives():
    return 3 + upg["life"]


def nuke_need():
    return (10, 8, 6)[upg["wave"]]


def dash_cd_frames():
    return (DASH_COOLDOWN, 480, 360)[upg["dash"]]


def fire_cd():
    return (8, 7, 6)[upg["fire"]]


def coins_text(q):
    return ("%.2f" % (q / 4.0)).rstrip("0").rstrip(".")


def make_coin_icon(d):
    s = pygame.Surface((d, d), pygame.SRCALPHA)
    c = d // 2
    pygame.draw.circle(s, (90, 55, 0), (c, c), c)
    pygame.draw.circle(s, (255, 205, 40), (c, c), c - 1)
    pygame.draw.circle(s, (255, 240, 130), (c - 1, c - 1), max(1, c - 3))
    pygame.draw.circle(s, (230, 170, 20), (c, c), max(1, c - 3), 1)
    pygame.draw.rect(s, (200, 130, 10), (c - 1, c - max(2, c // 2), 2, max(4, c)))
    return s.convert_alpha()


def make_color_orb(d):
    """Bolita de colores (botón de COLOR NAVE)."""
    s = pygame.Surface((d, d), pygame.SRCALPHA)
    c = d // 2
    r = c - 1
    cols = [(240, 60, 70), (255, 160, 30), (255, 230, 60), (60, 220, 90), (0, 220, 250), (80, 110, 255), (200, 90, 255)]
    n = len(cols)
    for k, col in enumerate(cols):
        a0 = 6.2832 * k / n
        a1 = 6.2832 * (k + 1) / n
        pts = [(c, c)]
        for j in range(7):
            a = a0 + (a1 - a0) * j / 6.0
            pts.append((int(c + math.cos(a) * r), int(c + math.sin(a) * r)))
        pygame.draw.polygon(s, col, pts)
    pygame.draw.circle(s, (255, 255, 255), (c - r // 3, c - r // 3), max(2, r // 5))
    pygame.draw.circle(s, (12, 10, 30), (c, c), c, 2)
    return s.convert_alpha()


COIN_ICON = make_coin_icon(14)
COIN_ICON_BIG = make_coin_icon(18)
COLOR_ORB = make_color_orb(28)
_ld(0.82, "Preparando naves")


class Player:
    def __init__(self):
        self.rect = PLAYER_SPR[0].base.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        self.x = float(self.rect.centerx)
        self.y = float(self.rect.centery)
        self.speed = HEIGHT * 0.01
        self.last_dir = [0, -1]
        self.lives = max_lives()
        self.invul_timer = 0
        self.nuke_xp = 0
        self.max_nuke_xp = nuke_need()
        self.dash_max = dash_cd_frames()
        self.dash_cd = 0
        self.dash_timer = 0
        self.dash_dir = [0, -1]
        self.dash_hit_boss = False
        self.aim_dir = [0, -1]
        self.aim_active = False
        self.shield = upg["shield"] > 0
        self.boost_timer = 0
        self.trail = []

    def start_dash(self, move_vector):
        if self.dash_cd > 0 or self.dash_timer > 0:
            return False
        mag = math.hypot(move_vector[0], move_vector[1])
        if mag > 0.2:
            self.dash_dir = [move_vector[0] / mag, move_vector[1] / mag]
        else:
            self.dash_dir = list(self.last_dir)
        self.dash_timer = DASH_FRAMES
        self.dash_cd = self.dash_max
        self.dash_hit_boss = False
        self.invul_timer = max(self.invul_timer, DASH_FRAMES + 6)
        play("dash")
        return True

    def update(self, move_vector, particles_list, force_center=False):
        if self.boost_timer > 0:
            self.boost_timer -= 1
        if self.dash_cd > 0:
            self.dash_cd -= 1
            if self.dash_cd == 0:
                play("dash_ready")

        if self.dash_timer > 0:
            self.dash_timer -= 1
            self.x += self.dash_dir[0] * DASH_SPEED
            self.y += self.dash_dir[1] * DASH_SPEED
            self.last_dir = list(self.dash_dir)
            for _ in range(3):
                if len(particles_list) < 160:
                    pt = Particle(self.x - self.dash_dir[0] * self.rect.width * 0.4 + random.uniform(-6, 6),
                                  self.y - self.dash_dir[1] * self.rect.height * 0.4 + random.uniform(-6, 6),
                                  -self.dash_dir[0] * random.uniform(0.3, 1.2),
                                  -self.dash_dir[1] * random.uniform(0.3, 1.2))
                    pt.color = random.choice([CYAN, WHITE, (90, 200, 255)])
                    pt.size = random.uniform(2.5, 4.0)
                    particles_list.append(pt)
        elif force_center:
            self.x += (WIDTH // 2 - self.x) * 0.05
            self.y += (HEIGHT // 2 - self.y) * 0.05
            self.last_dir = [0, -1]
        elif move_vector[0] != 0 or move_vector[1] != 0:
            spd = self.speed * (BOOST_MULT if self.boost_timer > 0 else 1.0)
            self.x += move_vector[0] * spd
            self.y += move_vector[1] * spd
            mag = math.hypot(move_vector[0], move_vector[1])
            self.last_dir = [move_vector[0] / mag, move_vector[1] / mag]
            if len(particles_list) < 120:
                bx = self.x - self.last_dir[0] * (self.rect.width * 0.4)
                by = self.y - self.last_dir[1] * (self.rect.height * 0.4)
                particles_list.append(Particle(bx, by, -self.last_dir[0] * random.uniform(0.7, 1.7),
                                               -self.last_dir[1] * random.uniform(0.7, 1.7)))
                if self.boost_timer > 0:        # estela extra mientras dura la velocidad
                    for _ in range(2):
                        pt = Particle(bx + random.uniform(-4, 4), by + random.uniform(-4, 4),
                                      -self.last_dir[0] * random.uniform(1.2, 2.6),
                                      -self.last_dir[1] * random.uniform(1.2, 2.6))
                        pt.color = random.choice(VG_SPARK) if vg_on else random.choice([YELLOW, (255, 250, 190), ORANGE])
                        pt.size = random.uniform(2.0, 3.5)
                        particles_list.append(pt)

        hw = self.rect.width / 2
        hh = self.rect.height / 2
        self.x = max(hw, min(WIDTH - hw, self.x))
        self.y = max(hh, min(HEIGHT - hh, self.y))
        self.rect.centerx = int(self.x)
        self.rect.centery = int(self.y)
        if vg_on:
            self.trail.append((self.x, self.y))
            del self.trail[:-14]

        if self.invul_timer > 0:
            self.invul_timer -= 1

    def draw(self, surface):
        blink = self.invul_timer > 0 and self.dash_timer == 0 and (self.invul_timer // 5) % 2 == 0
        if not blink:
            face = self.aim_dir if self.aim_active else self.last_dir
            angle = math.degrees(math.atan2(-face[1], face[0])) - 90
            if vg_on:
                img = vg_ship_sprites()[(frame // 5) % 6][(frame // 4) % 2].rot(angle)
            else:
                img = PLAYER_SPR[(frame // 4) % 2].rot(angle)
            if self.boost_timer > 0:
                fcol = (255, 200, 70)
            elif self.dash_timer > 0:
                fcol = (110, 220, 255)
            else:
                fcol = (110, 150, 250) if vg_on else (60, 170, 255)
            gr = 24 if self.dash_timer > 0 else (16 if (frame // 3) % 2 == 0 else 14)
            add_glow(surface, self.x - face[0] * self.rect.height * 0.42, self.y - face[1] * self.rect.height * 0.42,
                     fcol, gr, 0.9, 1)
            if vg_on:
                n = len(self.trail)
                if QUALITY >= 1 and n > 2:             # estela trenzada de pinceladas azul y amarilla
                    px, py = -face[1], face[0]
                    pa = pb = None
                    for i, (tx, ty) in enumerate(self.trail):
                        k = (i + 1) / float(n)
                        off = math.sin(frame * 0.35 - i * 0.8) * (1.0 + (1.0 - k) * 3.0)
                        ax, ay = int(tx + px * off), int(ty + py * off)
                        bx, by = int(tx - px * off), int(ty - py * off)
                        ca = shade(VG_TRAIL_A[(i + frame // 4) % 3], 0.25 + 0.75 * k)
                        cb = shade(VG_TRAIL_B[(i + frame // 4) % 3], 0.25 + 0.75 * k)
                        if pa is not None:
                            pygame.draw.line(surface, cb, pb, (bx, by), 2 if k > 0.5 else 1)
                            pygame.draw.line(surface, ca, pa, (ax, ay), 2 if k > 0.5 else 1)
                        pa, pb = (ax, ay), (bx, by)
                add_glow(surface, self.x, self.y, (250, 215, 90), 20 + 2 * ((frame // 6) % 2), 0.35, 2)
            surface.blit(img, img.get_rect(center=self.rect.center))
            if vg_on:                                   # estrellitas que orbitan la nave
                for k in range(4):
                    a = frame * 0.11 + k * 1.5708
                    rr = 17 + 3 * math.sin(frame * 0.07 + k * 2)
                    sx_, sy_ = int(self.x + math.cos(a) * rr), int(self.y + math.sin(a) * rr * 0.8)
                    c = VG_SPARK[k % 4]
                    pygame.draw.rect(surface, c, (sx_ - 1, sy_ - 1, 3, 3))
                    pygame.draw.rect(surface, (255, 255, 230), (sx_, sy_, 1, 1))
                    add_glow(surface, sx_, sy_, c, 6, 0.6, 2)
        if self.shield:
            sh = SHIELD_VG if vg_on else SHIELD_IMG
            add_glow(surface, self.x, self.y, (250, 215, 90) if vg_on else (60, 140, 255), 30, 0.5, 2)
            surface.blit(sh, sh.get_rect(center=self.rect.center))
            a = frame * 0.09
            for k in range(3):
                ang = a + k * 2.094
                pygame.draw.rect(surface, YELLOW if vg_on else WHITE,
                                 (int(self.x + math.cos(ang) * SHIELD_R) - 1, int(self.y + math.sin(ang) * SHIELD_R) - 1, 3, 3))


TRAIL_LEN = 7
VG_TRAIL_A = [(250, 220, 80), (255, 245, 170), (250, 200, 60)]
VG_TRAIL_B = [(90, 140, 235), (140, 190, 250), (60, 100, 210)]


class Projectile:
    def __init__(self, x, y, direction):
        angle = math.degrees(math.atan2(-direction[1], direction[0])) - 90
        self.image = PROJ_SPR.rot(angle)
        self.rect = self.image.get_rect(center=(int(x), int(y)))
        self.x = float(self.rect.centerx)
        self.y = float(self.rect.centery)
        self.dx = direction[0] * (HEIGHT * 0.025)
        self.dy = direction[1] * (HEIGHT * 0.025)
        m = math.hypot(direction[0], direction[1]) or 1.0
        self.px = -direction[1] / m          # perpendicular (para el ondeo del remolino)
        self.py = direction[0] / m
        self.trail = []
        self.age = 0
        self.ph = random.uniform(0, 6.28)
        self.tc = SHIP_COLORS[ship_idx][3]   # color de la trazadora normal

    def update(self):
        self.trail.append((self.x, self.y))
        if len(self.trail) > TRAIL_LEN:
            del self.trail[0]
        self.age += 1
        self.x += self.dx
        self.y += self.dy
        self.rect.centerx = int(self.x)
        self.rect.centery = int(self.y)

    def is_off_screen(self):
        return self.rect.right < 0 or self.rect.left > WIDTH or self.rect.bottom < 0 or self.rect.top > HEIGHT

    def draw(self, surface):
        pts = self.trail + [(self.x, self.y)]
        n = len(pts)
        if n >= 2:
            if vg_on and QUALITY >= 1:
                # dos hebras (azul y amarilla) trenzadas como las pinceladas del cielo
                pa = pb = None
                for i, (tx, ty) in enumerate(pts):
                    k = (i + 1) / float(n)
                    off = math.sin(self.age * 0.45 - i * 1.1 + self.ph) * (1.0 + (1.0 - k) * 3.5)
                    ax, ay = int(tx + self.px * off), int(ty + self.py * off)
                    bx, by = int(tx - self.px * off), int(ty - self.py * off)
                    ca = shade(VG_TRAIL_A[(i + self.age // 4) % 3], 0.3 + 0.7 * k)
                    cb = shade(VG_TRAIL_B[(i + self.age // 4) % 3], 0.3 + 0.7 * k)
                    if pa is not None:
                        w = 2 if k > 0.45 else 1
                        pygame.draw.line(surface, cb, pb, (bx, by), w)
                        pygame.draw.line(surface, ca, pa, (ax, ay), w)
                    if i % 3 == 0:
                        pygame.draw.rect(surface, (255, 255, 220), (ax, ay, 1, 1))
                    pa, pb = (ax, ay), (bx, by)
            else:
                prev = None
                for i, (tx, ty) in enumerate(pts):
                    k = (i + 1) / float(n)
                    cur = (int(tx), int(ty))
                    if prev is not None:
                        pygame.draw.line(surface, shade(self.tc, 0.15 + 0.85 * k), prev, cur, 2 if k > 0.5 else 1)
                    prev = cur
        add_glow(surface, self.x, self.y, (255, 220, 90) if vg_on else self.tc, 14, 0.9, 1)
        surface.blit(self.image, self.rect)


class Enemy:
    def __init__(self, tx, ty, speed_mult=1.0, pos=None, shoot=0.0):
        self.sprite = random.choice(ALIEN_SPRS)
        side = random.randint(1, 4)
        if pos is not None:
            sx, sy = pos
        elif side == 1:
            sx, sy = random.randint(0, WIDTH), -16
        elif side == 2:
            sx, sy = random.randint(0, WIDTH), HEIGHT + 16
        elif side == 3:
            sx, sy = -16, random.randint(0, HEIGHT)
        else:
            sx, sy = WIDTH + 16, random.randint(0, HEIGHT)

        self.rect = self.sprite.base.get_rect(center=(int(sx), int(sy)))
        self.x = float(self.rect.centerx)
        self.y = float(self.rect.centery)
        self.speed = HEIGHT * random.uniform(0.002, 0.005) * speed_mult
        self.update_direction(tx, ty)
        self.z_timer = 0
        self.o_angle = 0.0
        self.shooter = random.random() < shoot       # alien armado (sectores 2 y 3)
        self.fire_t = random.randint(80, 170)

    def update_direction(self, tx, ty):
        angle = math.atan2(ty - self.y, tx - self.x)
        self.base_dx = math.cos(angle)
        self.base_dy = math.sin(angle)

    def update(self, tx, ty):
        """Devuelve True cuando el alien dispara en este frame."""
        self.z_timer += 1
        if self.z_timer > 30:
            self.update_direction(tx, ty)
            self.o_angle = random.uniform(-0.5, 0.5)
            self.z_timer = 0
        final_angle = math.atan2(self.base_dy, self.base_dx) + self.o_angle
        self.vx = math.cos(final_angle) * self.speed
        self.vy = math.sin(final_angle) * self.speed
        self.x += self.vx
        self.y += self.vy
        self.rect.centerx = int(self.x)
        self.rect.centery = int(self.y)
        fired = False
        if self.shooter:
            self.fire_t -= 1
            if self.fire_t <= 0:
                self.fire_t = random.randint(130, 210)
                fired = 0 <= self.x <= WIDTH and 0 <= self.y <= HEIGHT
        return fired

    def draw(self, surface):
        angle = math.degrees(math.atan2(-self.base_dy, self.base_dx)) - 90
        img = self.sprite.rot(angle)
        add_glow(surface, self.rect.centerx, self.rect.centery, self.sprite.glow, 22, 0.55, 2)
        surface.blit(img, img.get_rect(center=self.rect.center))
        if self.shooter:                              # lucecita roja: este alien dispara
            col = YELLOW if (self.fire_t < 25 and (frame // 3) % 2 == 0) else RED
            pygame.draw.rect(surface, (20, 4, 8), (self.rect.centerx - 3, self.rect.top - 6, 6, 6))
            pygame.draw.rect(surface, col, (self.rect.centerx - 2, self.rect.top - 5, 4, 4))


class LifePickup:
    def __init__(self):
        self.image = HEART_IMG
        self.rect = self.image.get_rect(x=random.randint(16, WIDTH - 16), y=-16)
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)
        self.speed = HEIGHT * 0.002
        self.dx = random.choice([-1, 1]) * (HEIGHT * 0.001)

    def update(self):
        self.y += self.speed
        self.x += self.dx
        if self.x < 0 or self.x > WIDTH - self.rect.width:
            self.dx *= -1
        self.rect.x = int(self.x)
        self.rect.y = int(self.y)

    def is_off_screen(self):
        return self.rect.top > HEIGHT

    def draw(self, surface):
        # latido suave
        off = 1 if (frame // 12) % 2 == 0 else 0
        add_glow(surface, self.rect.centerx, self.rect.centery, (255, 60, 80), 18, 0.8, 2)
        surface.blit(self.image, (self.rect.x, self.rect.y - off))


def make_powerup_icon(kind):
    s = pygame.Surface((24, 24), pygame.SRCALPHA)
    if kind == "shield":
        main, light = (40, 130, 255), (160, 225, 255)
    else:
        main, light = (255, 175, 20), (255, 245, 150)
    pygame.draw.circle(s, (8, 8, 24), (12, 12), 12)
    pygame.draw.circle(s, light, (12, 12), 11)
    pygame.draw.circle(s, main, (12, 12), 9)
    pygame.draw.circle(s, shade(main, 1.35), (10, 10), 5)
    if kind == "shield":
        pygame.draw.polygon(s, (255, 255, 255), [(12, 5), (18, 7), (18, 13), (12, 19), (6, 13), (6, 7)])
        pygame.draw.polygon(s, main, [(12, 8), (15, 9), (15, 12), (12, 15), (9, 12), (9, 9)])
    else:
        pygame.draw.polygon(s, (255, 255, 255), [(14, 4), (7, 13), (11, 13), (9, 20), (17, 10), (13, 10)])
    return s.convert_alpha()


PU_ICONS = {"shield": make_powerup_icon("shield"), "speed": make_powerup_icon("speed")}
PU_SMALL = {k: pygame.transform.scale(v, (16, 16)) for k, v in PU_ICONS.items()}


class PowerUp:
    """Potenciador que cae despacio: 'shield' (escudo) o 'speed' (velocidad 5 s)."""
    def __init__(self, kind, x=None, y=None):
        self.kind = kind
        self.image = PU_ICONS[kind]
        self.rect = self.image.get_rect()
        self.x = float(x if x is not None else random.randint(20, WIDTH - 20))
        self.y = float(y if y is not None else -14)
        self.base_x = self.x
        self.t = random.uniform(0, 6.28)
        self.speed = HEIGHT * 0.0022
        self.rect.center = (int(self.x), int(self.y))

    def update(self):
        self.t += 0.06
        self.y += self.speed
        self.x = min(WIDTH - 12, max(12, self.base_x + math.sin(self.t) * 14))
        self.rect.center = (int(self.x), int(self.y))

    def is_off_screen(self):
        return self.rect.top > HEIGHT

    def draw(self, surface):
        col = (150, 220, 255) if self.kind == "shield" else (255, 230, 120)
        pygame.draw.circle(surface, shade(col, 0.5), self.rect.center, 14 + (frame // 8) % 2, 1)
        add_glow(surface, self.rect.centerx, self.rect.centery, col, 20, 0.7, 2)
        surface.blit(self.image, self.rect)


class EnemyBullet:
    def __init__(self, x, y, ang, speed):
        self.x = float(x)
        self.y = float(y)
        self.dx = math.cos(ang) * speed
        self.dy = math.sin(ang) * speed
        self.rect = pygame.Rect(int(x) - 3, int(y) - 3, 6, 6)

    def update(self):
        self.x += self.dx
        self.y += self.dy
        self.rect.center = (int(self.x), int(self.y))

    def is_off_screen(self):
        return self.x < -12 or self.x > WIDTH + 12 or self.y < -12 or self.y > HEIGHT + 12

    def draw(self, surface):
        x, y = int(self.x), int(self.y)
        r = 5 if (frame // 5) % 2 == 0 else 4
        add_glow(surface, x, y, (255, 70, 40), 13, 0.9, 1)
        pygame.draw.circle(surface, (120, 10, 30), (x, y), r)
        pygame.draw.circle(surface, (255, 70, 40), (x, y), r - 1)
        pygame.draw.circle(surface, YELLOW, (x, y), 2)


BOSS_AURA = {1: (140, 70, 220), 2: (255, 90, 50), 3: (255, 60, 220), 4: (90, 210, 255), 5: (140, 255, 80),
             6: (255, 70, 210), 7: (255, 170, 40), 8: (255, 70, 90)}


class Boss:
    """Un BOSS distinto por sector, cada uno con su dibujo, movimiento y ataques:
       1 CENTINELA ALFA : se balancea, disparos apuntados, anillos de balas y llama aliens.
       2 TITAN ESCARLATA: lluvia de meteoritos y EMBESTIDAS (avisa, se lanza hacia abajo y
                          al chocar lanza una onda de balas).
       3 OJO DEL NUCLEO : se TELETRANSPORTA, dispara ESPIRALES giratorias y LASERS con aviso.
       4 CENTINELA GLACIAL: MUROS de balas con un hueco por donde pasar + disparos apuntados.
       5 REINA ENJAMBRE : invoca aliens armados, abanicos de balas y anillos.
       6 CAZADOR DEL VACIO: BARRIDOS horizontales (avisa la fila) dejando balas + anillos.
       7 ARCHI-REACTOR  : lanza BOMBAS que explotan en anillos + LASERS con aviso.
       8 EMPERADOR GALACTICO: JEFE FINAL, mezcla ataques de todos los demás.
       Todos tienen 3 fases según su vida (más difícil en cada una)."""

    def __init__(self, idx, hp_mult=1.0):
        self.idx = idx
        self.imgs = BOSS_SETS.get(idx, BOSS_SETS[3])
        base_hp = 70 + 35 * (idx - 1) if idx <= 3 else 140 + 28 * (idx - 3)
        self.max_hp = max(20, int(base_hp * hp_mult))
        self.hp = self.max_hp
        self.x = WIDTH / 2.0
        self.y = -40.0
        self.rect = self.imgs[0].get_rect(center=(int(self.x), int(self.y)))
        self.hit_rect = self.rect.inflate(-int(self.rect.width * 0.3), -int(self.rect.height * 0.25))
        self.target_y = HEIGHT * (0.26 if idx == 3 else 0.22)
        self.state = "INTRO"        # INTRO -> FIGHT -> DYING
        self.osc = 0.0
        self.fire_t = 70
        self.ring_t = 200
        self.minion_t = 300
        self.hit_flash = 0
        self.hits = 0
        self.dying = 0
        self.finished = False
        self.phase = 1
        self.vx = 0.0
        self.vy = 0.0
        # --- estado de los bosses 2 y 3
        self.sub = "HOVER" if idx == 2 else "DRIFT"
        self.sub_t = 0
        self.charge_t = 150
        self.rain_t = 40
        self.chain = False
        self.dive_x = WIDTH / 2.0
        self.tx = WIDTH / 2.0
        self.ty = self.target_y
        self.cyc = 0
        self.spin = 0.0
        self.spin_dir = 1
        self.blink_t = 200
        self.beam_t = 150
        self.beams = []
        self.ghost = False          # teletransportándose: no se le puede dañar ni él daña
        self.alpha = 255
        # --- estado de los bosses 4 a 8
        self.bombs = []             # boss 7: bombas en vuelo
        self.bomb_t = 80
        self.atk = None             # boss 8: ataque actual
        self.atk_t = 0
        self.wait_t = 90
        self.atk_dir = 1

    # ------------------------------------------------------------ utilidades
    def beam_hit(self, rect):
        r = rect.inflate(-8, -8)
        for b in self.beams:
            if b["t"] >= b["warn"]:
                if b["h"]:
                    br = pygame.Rect(0, b["p"] - 8, WIDTH, 16)
                else:
                    br = pygame.Rect(b["p"] - 8, 0, 16, HEIGHT)
                if r.colliderect(br):
                    return True
        return False

    def update(self, px, py, bullets, enemies, particles):
        ox, oy = self.x, self.y
        if self.hit_flash > 0:
            self.hit_flash -= 1

        if self.state == "INTRO":
            self.y += 1.1
            if self.y >= self.target_y:
                self.y = self.target_y
                self.state = "FIGHT"
                set_music("boss%d" % self.idx)

        elif self.state == "FIGHT":
            ratio = self.hp / float(self.max_hp)
            phase = 1 if ratio > 0.66 else 2 if ratio > 0.33 else 3
            if phase != self.phase:
                self.phase = phase
                play("boss_roar")
                add_shake(16)
                bullets[:] = []
                self.beams = []
                self.bombs = []
                self.beam_t = 110
                self.fire_t = 60
                self.atk = None
                self.wait_t = 60
                for _ in range(24):
                    particles.append(Particle(self.x, self.y, random.uniform(-2, 2), random.uniform(-2, 2), True))
            if self.idx >= 4:
                self._tick_beams()
            if self.idx == 2:
                self._fight2(px, py, bullets, particles)
            elif self.idx == 3:
                self._fight3(px, py, bullets, particles)
            elif self.idx == 4:
                self._fight4(px, py, bullets)
            elif self.idx == 5:
                self._fight5(px, py, bullets, enemies)
            elif self.idx == 6:
                self._fight6(px, py, bullets, particles)
            elif self.idx == 7:
                self._fight7(px, py, bullets, particles)
            elif self.idx == 8:
                self._fight8(px, py, bullets, enemies, particles)
            else:
                self._fight1(px, py, bullets, enemies, particles)

        elif self.state == "DYING":
            self.beams = []
            self.bombs = []
            self.ghost = False
            self.alpha = 255
            self.dying -= 1
            if self.dying % 3 == 0:
                for _ in range(6):
                    if len(particles) < 200:
                        particles.append(Particle(self.x + random.uniform(-self.rect.width / 2, self.rect.width / 2),
                                                  self.y + random.uniform(-self.rect.height / 2, self.rect.height / 2),
                                                  random.uniform(-1.6, 1.6), random.uniform(-1.6, 1.6), True))
            if self.dying % 14 == 0:
                play("explosion")
                add_shake(8)
                fx_boom(self.x + random.uniform(-40, 40), self.y + random.uniform(-25, 25), 1.6)
            if self.dying <= 0:
                self.finished = True

        self.rect.center = (int(self.x), int(self.y))
        self.hit_rect.center = self.rect.center
        self.vx = self.x - ox
        self.vy = self.y - oy

    # ------------------------------------------------------------ BOSS 1
    def _fight1(self, px, py, bullets, enemies, particles):
        phase = self.phase
        self.osc += (0.012, 0.016, 0.022)[phase - 1]
        self.x = WIDTH / 2.0 + math.sin(self.osc) * WIDTH * 0.3
        self.y = self.target_y + math.sin(self.osc * 2.3) * 8

        self.fire_t -= 1
        if self.fire_t <= 0:
            ang = math.atan2(py - self.y, px - self.x)
            n = (3, 3, 5)[phase - 1]
            for i in range(n):
                bullets.append(EnemyBullet(self.x, self.y + self.rect.height * 0.3,
                                           ang + (i - (n - 1) / 2.0) * 0.22, HEIGHT * 0.0095))
            play("boss_shot")
            self.fire_t = (75, 62, 48)[phase - 1]

        if phase >= 2:
            self.ring_t -= 1
            if self.ring_t <= 0:
                n = 12 if phase == 2 else 18
                off = random.uniform(0, 6.28)
                for i in range(n):
                    bullets.append(EnemyBullet(self.x, self.y, off + i * 6.2832 / n, HEIGHT * 0.006))
                play("boss_ring")
                self.ring_t = 220 if phase == 2 else 150

        if phase == 3:
            self.minion_t -= 1
            if self.minion_t <= 0:
                if len(enemies) < 2:
                    enemies.append(Enemy(px, py, 1.2, (self.x, self.y)))
                self.minion_t = 320

    # ------------------------------------------------------------ BOSS 2
    def _fight2(self, px, py, bullets, particles):
        ph = self.phase
        if self.sub in ("HOVER", "RETURN"):
            if self.sub == "HOVER":
                self.osc += (0.011, 0.015, 0.02)[ph - 1]
                self.x = WIDTH / 2.0 + math.sin(self.osc) * WIDTH * 0.3
                self.y = self.target_y + math.sin(self.osc * 2.3) * 6
                self.charge_t -= 1
                if self.charge_t <= 0:
                    self.sub, self.sub_t = "WIND", 55
                    self.dive_x = px
                    play("lock_on")
            else:
                self.y -= 2.4
                self.x += (WIDTH / 2.0 - self.x) * 0.03
                if self.y <= self.target_y:
                    self.y = self.target_y
                    self.sub = "HOVER"
                    self.osc = math.asin(max(-1.0, min(1.0, (self.x - WIDTH / 2.0) / (WIDTH * 0.3))))
                    self.charge_t = 35 if self.chain else (260, 210, 160)[ph - 1]
                    self.chain = False

            # lluvia de meteoritos
            self.rain_t -= 1
            if self.rain_t <= 0:
                for _ in range((2, 3, 4)[ph - 1]):
                    bullets.append(EnemyBullet(random.uniform(14, WIDTH - 14), -8, 1.5708,
                                               HEIGHT * random.uniform(0.0055, 0.0075)))
                self.rain_t = (62, 50, 40)[ph - 1]
            # disparo apuntado
            self.fire_t -= 1
            if self.fire_t <= 0:
                ang = math.atan2(py - self.y, px - self.x)
                for i in range(3):
                    bullets.append(EnemyBullet(self.x, self.y + self.rect.height * 0.3,
                                               ang + (i - 1) * 0.25, HEIGHT * 0.0085))
                play("boss_shot")
                self.fire_t = (110, 90, 75)[ph - 1]

        elif self.sub == "WIND":                       # avisa: tiembla y fija la columna
            self.sub_t -= 1
            if self.sub_t > 18:
                self.dive_x = max(50.0, min(WIDTH - 50.0, px))
            self.x += (self.dive_x - self.x) * 0.12
            self.y = self.target_y + random.uniform(-1.5, 1.5)
            if self.sub_t <= 0:
                self.sub = "DIVE"
                play("dash")

        elif self.sub == "DIVE":                       # se lanza hacia abajo
            self.y += HEIGHT * 0.03
            if len(particles) < 160:
                pt = Particle(self.x + random.uniform(-20, 20), self.y - 26, 0, -random.uniform(0.4, 1.2))
                pt.color = random.choice([ORANGE, YELLOW, (255, 90, 40)])
                particles.append(pt)
            if self.y >= HEIGHT * 0.8:
                self.y = HEIGHT * 0.8
                self.sub, self.sub_t = "RECOVER", 38
                n = (9, 11, 13)[ph - 1]
                for i in range(n):                     # onda de choque hacia arriba
                    bullets.append(EnemyBullet(self.x, self.y - 10, -3.1416 + i * 3.1416 / (n - 1), HEIGHT * 0.0062))
                play("boss_ring")
                add_shake(12)
                fx_boom(self.x, self.y + 20, 2.0)
                for _ in range(16):
                    particles.append(Particle(self.x, self.y + 20, random.uniform(-2.4, 2.4), random.uniform(-2.0, 0.4), True))

        elif self.sub == "RECOVER":
            self.sub_t -= 1
            if self.sub_t <= 0:
                self.chain = (ph == 3 and random.random() < 0.5)   # en fase 3 a veces embiste dos veces seguidas
                self.sub = "RETURN"

    # ------------------------------------------------------------ BOSS 3
    def _fight3(self, px, py, bullets, particles):
        ph = self.phase
        for b in self.beams:
            b["t"] += 1
            if b["t"] == b["warn"]:
                play("boss_ring")
        self.beams = [b for b in self.beams if b["t"] < b["warn"] + b["life"]]

        if self.sub == "DRIFT":
            self.osc += 0.02
            self.x = self.tx + math.sin(self.osc) * WIDTH * 0.10
            self.y = self.ty + math.sin(self.osc * 1.7) * 8

            # espirales en ráfagas (1, 2 y 3 brazos según la fase)
            on = (40, 50, 55)[ph - 1]
            self.cyc = (self.cyc + 1) % (120 - 10 * ph)
            if self.cyc == 1:
                self.spin_dir = -self.spin_dir
                self.spin = math.atan2(py - self.y, px - self.x) - 0.16 * (on / 4.0) * self.spin_dir
            if self.cyc < on and self.cyc % 4 == 0:
                for k in range(ph):
                    bullets.append(EnemyBullet(self.x, self.y, self.spin + k * 6.2832 / ph, HEIGHT * 0.0048))
                self.spin += 0.32 * self.spin_dir
                if self.cyc % 12 == 0:
                    play("boss_shot")

            # lasers con aviso (fase 2: vertical; fase 3: en cruz)
            if ph >= 2:
                self.beam_t -= 1
                if self.beam_t <= 0:
                    self.beams.append({"h": False, "p": int(px), "t": 0, "warn": 55, "life": 22})
                    if ph == 3:
                        self.beams.append({"h": True, "p": int(py), "t": 0, "warn": 60, "life": 22})
                    self.beam_t = (999, 240, 190)[ph - 1]
                    play("lock_on")

            # teletransporte
            self.blink_t -= 1
            if self.blink_t <= 0:
                self.sub, self.sub_t, self.ghost = "OUT", 24, True
                play("lock_off")

        elif self.sub == "OUT":
            self.sub_t -= 1
            self.alpha = max(0, int(255 * self.sub_t / 24.0))
            if self.sub_t <= 0:
                self.x = random.uniform(WIDTH * 0.2, WIDTH * 0.8)
                self.y = random.uniform(HEIGHT * 0.14, HEIGHT * 0.38)
                self.tx, self.ty = self.x, self.y
                self.sub, self.sub_t = "IN", 24

        elif self.sub == "IN":
            self.sub_t -= 1
            self.alpha = min(255, int(255 * (1 - self.sub_t / 24.0)))
            if self.sub_t <= 0:
                self.ghost = False
                self.alpha = 255
                self.sub = "DRIFT"
                self.osc = 0.0
                self.cyc = 0
                self.blink_t = (260, 210, 170)[ph - 1]
                n = (12, 16, 20)[ph - 1]
                off = random.uniform(0, 6.28)
                for i in range(n):                    # anillo al reaparecer
                    bullets.append(EnemyBullet(self.x, self.y, off + i * 6.2832 / n, HEIGHT * 0.0055))
                play("boss_ring")

    # ------------------------------------------------------------ utilidades de ataque (bosses 4-8)
    def _tick_beams(self):
        for b in self.beams:
            b["t"] += 1
            if b["t"] == b["warn"]:
                play("boss_ring")
        self.beams = [b for b in self.beams if b["t"] < b["warn"] + b["life"]]

    def _wall(self, bullets, px, gap, speed):
        """Muro horizontal de balas que cae, con un hueco cerca de la nave."""
        gx = max(gap / 2.0 + 8, min(WIDTH - gap / 2.0 - 8, px + random.uniform(-70, 70)))
        xx = 10
        while xx < WIDTH:
            if abs(xx - gx) > gap / 2.0:
                bullets.append(EnemyBullet(xx, -6, 1.5708, speed))
            xx += 22
        play("boss_ring")

    def _ring(self, bullets, n, speed, off=None):
        if off is None:
            off = random.uniform(0, 6.28)
        for i in range(n):
            bullets.append(EnemyBullet(self.x, self.y, off + i * 6.2832 / n, speed))
        play("boss_ring")

    def _fan(self, bullets, px, py, n, step, speed):
        ang = math.atan2(py - self.y, px - self.x)
        for i in range(n):
            bullets.append(EnemyBullet(self.x, self.y + self.rect.height * 0.3,
                                       ang + (i - (n - 1) / 2.0) * step, speed))
        play("boss_shot")

    # ------------------------------------------------------------ BOSS 4
    def _fight4(self, px, py, bullets):
        ph = self.phase
        self.osc += (0.012, 0.016, 0.02)[ph - 1]
        self.x = WIDTH / 2.0 + math.sin(self.osc) * WIDTH * 0.32
        self.y = self.target_y + math.sin(self.osc * 2.0) * 6
        self.ring_t -= 1
        if self.ring_t <= 0:
            self._wall(bullets, px, (100, 82, 66)[ph - 1], HEIGHT * 0.0048)
            self.ring_t = (210, 175, 140)[ph - 1]
        self.fire_t -= 1
        if self.fire_t <= 0:
            self._fan(bullets, px, py, (3, 3, 5)[ph - 1], 0.22, HEIGHT * 0.0085)
            self.fire_t = (100, 84, 68)[ph - 1]

    # ------------------------------------------------------------ BOSS 5
    def _fight5(self, px, py, bullets, enemies):
        ph = self.phase
        self.osc += (0.011, 0.015, 0.019)[ph - 1]
        self.x = WIDTH / 2.0 + math.sin(self.osc) * WIDTH * 0.28
        self.y = self.target_y + math.sin(self.osc * 2.6) * 10
        self.fire_t -= 1
        if self.fire_t <= 0:
            self._fan(bullets, px, py, (5, 7, 9)[ph - 1], 0.2, HEIGHT * 0.0065)
            self.fire_t = (82, 70, 58)[ph - 1]
        self.minion_t -= 1
        if self.minion_t <= 0:
            cap = (3, 4, 5)[ph - 1]
            for _ in range(ph):
                if len(enemies) < cap:
                    enemies.append(Enemy(px, py, 1.3, (self.x, self.y), 0.6))
            self.minion_t = (260, 220, 180)[ph - 1]
        if ph == 3:
            self.ring_t -= 1
            if self.ring_t <= 0:
                self._ring(bullets, 14, HEIGHT * 0.0052)
                self.ring_t = 170

    # ------------------------------------------------------------ BOSS 6
    def _fight6(self, px, py, bullets, particles):
        ph = self.phase
        if self.sub in ("DRIFT", "HOVER"):          # (DRIFT = estado inicial; se trata como HOVER)
            self.sub = "HOVER"
            self.osc += (0.012, 0.016, 0.02)[ph - 1]
            self.x = WIDTH / 2.0 + math.sin(self.osc) * WIDTH * 0.3
            self.y += (self.target_y + math.sin(self.osc * 2.1) * 6 - self.y) * 0.1
            self.fire_t -= 1
            if self.fire_t <= 0:
                self._fan(bullets, px, py, 3 + ph, 0.2, HEIGHT * 0.0075)
                self.fire_t = (92, 78, 64)[ph - 1]
            if ph >= 2:
                self.ring_t -= 1
                if self.ring_t <= 0:
                    self._ring(bullets, 10 if ph == 2 else 14, HEIGHT * 0.0052)
                    self.ring_t = 230 if ph == 2 else 170
            self.charge_t -= 1
            if self.charge_t <= 0:
                self.sub, self.sub_t = "WIND", 60
                self.ty = max(HEIGHT * 0.3, min(HEIGHT * 0.85, py))
                self.spin_dir = random.choice((1, -1))
                self.chain = False
                play("lock_on")
        elif self.sub == "WIND":                      # avisa la fila del barrido
            self.sub_t -= 1
            if self.sub_t > 20 and not self.chain:
                self.ty = max(HEIGHT * 0.3, min(HEIGHT * 0.85, py))
            start_x = 40.0 if self.spin_dir == 1 else WIDTH - 40.0
            self.x += (start_x - self.x) * 0.14
            self.y += (self.ty - self.y) * 0.14
            if self.sub_t <= 0:
                self.sub = "SWEEP"
                play("dash")
        elif self.sub == "SWEEP":
            self.x += self.spin_dir * WIDTH * 0.022
            self.y = self.ty
            if frame % 4 == 0:
                bullets.append(EnemyBullet(self.x, self.y + 14, 1.5708, HEIGHT * 0.004))
            if len(particles) < 160 and frame % 2 == 0:
                pt = Particle(self.x - self.spin_dir * 24, self.y + random.uniform(-10, 10), 0, 0)
                pt.color = random.choice([(255, 70, 210), (190, 110, 255), WHITE])
                particles.append(pt)
            if (self.spin_dir == 1 and self.x >= WIDTH - 30) or (self.spin_dir == -1 and self.x <= 30):
                if ph == 3 and not self.chain:        # en fase 3 barre de ida y vuelta
                    self.chain = True
                    self.spin_dir = -self.spin_dir
                    self.sub, self.sub_t = "WIND", 26
                    play("lock_on")
                else:
                    self.chain = False
                    self.sub, self.sub_t = "RECOVER", 30
                    add_shake(6)
        elif self.sub == "RECOVER":
            self.sub_t -= 1
            if self.sub_t <= 0:
                self.sub = "RETURN"
        elif self.sub == "RETURN":
            self.y += (self.target_y - self.y) * 0.08
            self.x += (WIDTH / 2.0 - self.x) * 0.06
            if abs(self.y - self.target_y) < 4 and abs(self.x - WIDTH / 2.0) < WIDTH * 0.28:
                self.sub = "HOVER"
                self.osc = math.asin(max(-1.0, min(1.0, (self.x - WIDTH / 2.0) / (WIDTH * 0.3))))
                self.charge_t = (240, 200, 160)[ph - 1]

    # ------------------------------------------------------------ BOSS 7
    def _fight7(self, px, py, bullets, particles):
        ph = self.phase
        self.osc += (0.009, 0.012, 0.016)[ph - 1]
        self.x = WIDTH / 2.0 + math.sin(self.osc) * WIDTH * 0.22
        self.y = self.target_y + math.sin(self.osc * 1.9) * 7

        # bombas: vuelan hacia la nave y explotan en anillo
        self.bomb_t -= 1
        if self.bomb_t <= 0:
            for k in range(2 if ph == 3 else 1):
                self.bombs.append({"x": self.x, "y": self.y + 20,
                                   "tx": max(20.0, min(WIDTH - 20.0, px + random.uniform(-40, 40) * k)),
                                   "ty": max(HEIGHT * 0.3, min(HEIGHT - 30.0, py + random.uniform(-30, 30) * k)),
                                   "t": 0})
            play("boss_shot")
            self.bomb_t = (95, 80, 70)[ph - 1]
        for b in self.bombs:
            b["t"] += 1
            b["x"] += (b["tx"] - b["x"]) * 0.06
            b["y"] += (b["ty"] - b["y"]) * 0.06
        for b in [b for b in self.bombs if b["t"] >= 60]:
            self.bombs.remove(b)
            n = (8, 10, 12)[ph - 1]
            off = random.uniform(0, 6.28)
            for i in range(n):
                bullets.append(EnemyBullet(b["x"], b["y"], off + i * 6.2832 / n, HEIGHT * 0.0052))
            play("boss_ring")
            add_shake(4)
            fx_boom(b["x"], b["y"], 1.1)

        # disparo apuntado
        self.fire_t -= 1
        if self.fire_t <= 0:
            self._fan(bullets, px, py, 3, 0.25, HEIGHT * 0.0085)
            self.fire_t = (115, 98, 82)[ph - 1]

        # lasers con aviso (fase 2: vertical; fase 3: vertical + horizontal)
        if ph >= 2:
            self.beam_t -= 1
            if self.beam_t <= 0:
                self.beams.append({"h": False, "p": int(px), "t": 0, "warn": 55, "life": 22})
                if ph == 3:
                    self.beams.append({"h": True, "p": int(py), "t": 0, "warn": 62, "life": 22})
                self.beam_t = (999, 250, 200)[ph - 1]
                play("lock_on")

    # ------------------------------------------------------------ BOSS 8 (jefe final)
    def _fight8(self, px, py, bullets, enemies, particles):
        ph = self.phase
        self.osc += (0.011, 0.014, 0.018)[ph - 1]
        self.x = WIDTH / 2.0 + math.sin(self.osc) * WIDTH * 0.28
        self.y = self.target_y + math.sin(self.osc * 2.2) * 8

        if self.atk is None:
            self.wait_t -= 1
            if self.wait_t <= 0:
                pool = ["spiral", "wall", "fan"]
                if ph >= 2:
                    pool += ["ring", "laser"]
                if ph >= 3:
                    pool += ["summon", "laser", "spiral"]
                self.atk = random.choice(pool)
                self.atk_dir = random.choice((1, -1))
                self.atk_t = {"spiral": 80, "wall": 14, "fan": 34, "ring": 44, "laser": 30, "summon": 14}[self.atk]
                if self.atk == "spiral":
                    self.spin = math.atan2(py - self.y, px - self.x)
            return

        a = self.atk
        self.atk_t -= 1
        t = self.atk_t
        if a == "spiral":
            if t % 4 == 0:
                arms = (2, 2, 3)[ph - 1]
                for k in range(arms):
                    bullets.append(EnemyBullet(self.x, self.y, self.spin + k * 6.2832 / arms, HEIGHT * 0.0048))
                self.spin += 0.3 * self.atk_dir
                if t % 12 == 0:
                    play("boss_shot")
        elif a == "wall":
            if t == 13:
                self._wall(bullets, px, (96, 80, 66)[ph - 1], HEIGHT * 0.0050)
        elif a == "fan":
            if t in (33, 14):
                self._fan(bullets, px, py, (7, 9, 11)[ph - 1], 0.2, HEIGHT * 0.0070)
        elif a == "ring":
            if t in (43, 22):
                self._ring(bullets, (14, 18, 22)[ph - 1], HEIGHT * 0.0055, 0.0 if t == 43 else 0.2)
        elif a == "laser":
            if t == 29:
                self.beams.append({"h": False, "p": int(px), "t": 0, "warn": 55, "life": 22})
                if ph == 3:
                    self.beams.append({"h": True, "p": int(py), "t": 0, "warn": 60, "life": 22})
                    self.beams.append({"h": False, "p": int(random.uniform(30, WIDTH - 30)), "t": 0, "warn": 60, "life": 22})
                play("lock_on")
        elif a == "summon":
            if t == 13:
                for _ in range(2):
                    if len(enemies) < 4:
                        enemies.append(Enemy(px, py, 1.3, (self.x, self.y), 0.6))
        if self.atk_t <= 0:
            self.atk = None
            self.wait_t = (100, 80, 62)[ph - 1] + (50 if a == "laser" else 0)

    # ------------------------------------------------------------ dibujo
    def draw(self, surface):
        # avisos y lasers (debajo del boss)
        if self.idx == 2 and self.sub == "WIND" and (frame // 3) % 2 == 0:
            xx = int(self.dive_x)
            for yy in range(int(self.y), HEIGHT, 14):
                pygame.draw.line(surface, (255, 80, 60), (xx, yy), (xx, yy + 7), 2)
            pygame.draw.rect(surface, (255, 80, 60), (xx - 12, HEIGHT - 8, 24, 4))
        if self.idx == 6 and self.sub == "WIND" and (frame // 3) % 2 == 0:
            yy = int(self.ty)
            for xx in range(0, WIDTH, 14):
                pygame.draw.line(surface, (255, 80, 220), (xx, yy), (xx + 7, yy), 2)
        for bm in self.bombs:
            bx, by = int(bm["x"]), int(bm["y"])
            hot = bm["t"] > 38 and (frame // 3) % 2 == 0
            add_glow(surface, bx, by, (255, 170, 40), 16, 0.8, 1)
            pygame.draw.circle(surface, (40, 20, 10), (bx, by), 7)
            pygame.draw.circle(surface, WHITE if hot else ORANGE, (bx, by), 5)
            pygame.draw.circle(surface, YELLOW, (bx - 1, by - 1), 2)
        for b in self.beams:
            if b["t"] < b["warn"]:
                if (frame // 3) % 2 == 0:
                    col = (255, 90, 200)
                    if b["h"]:
                        for xx in range(0, WIDTH, 12):
                            pygame.draw.line(surface, col, (xx, b["p"]), (xx + 6, b["p"]))
                    else:
                        for yy in range(0, HEIGHT, 12):
                            pygame.draw.line(surface, col, (b["p"], yy), (b["p"], yy + 6))
            else:
                w = 18 if (frame // 2) % 2 == 0 else 14
                if b["h"]:
                    pygame.draw.rect(surface, (110, 20, 100), (0, b["p"] - w // 2 - 5, WIDTH, w + 10))
                    pygame.draw.rect(surface, (255, 60, 220), (0, b["p"] - w // 2, WIDTH, w))
                    pygame.draw.rect(surface, WHITE, (0, b["p"] - 3, WIDTH, 6))
                else:
                    pygame.draw.rect(surface, (110, 20, 100), (b["p"] - w // 2 - 5, 0, w + 10, HEIGHT))
                    pygame.draw.rect(surface, (255, 60, 220), (b["p"] - w // 2, 0, w, HEIGHT))
                    pygame.draw.rect(surface, WHITE, (b["p"] - 3, 0, 6, HEIGHT))

        if self.alpha > 40:
            add_glow(surface, self.rect.centerx, self.rect.centery, BOSS_AURA.get(self.idx, (140, 70, 220)),
                     64 + 4 * ((frame // 8) % 2), 0.5 * self.alpha / 255.0, 2)
        b_img, b_hit, b_rage = self.imgs
        if self.state == "DYING":
            img = b_hit if (frame // 3) % 2 == 0 else b_img
        elif self.hit_flash > 0:
            img = b_hit
        elif self.phase == 3 and (frame // 10) % 2 == 0:
            img = b_rage
        else:
            img = b_img
        if self.alpha < 255:
            img.set_alpha(self.alpha)
            surface.blit(img, img.get_rect(center=self.rect.center))
            img.set_alpha(255)
        else:
            surface.blit(img, img.get_rect(center=self.rect.center))


# =====================================================================
#  DEMO DEL MENÚ: el piloto combate aliens y bosses sin morir (sin orbes, monedas ni sonidos)
# =====================================================================
DEMO_STEPS = 2          # la animación del menú avanza 2 pasos por frame (el doble de rápido)


class MenuDemo:
    def __init__(self):
        self.t = 0
        self.ship = Player()
        self.ship.shield = False
        self.ship.invul_timer = 0
        self.ship.boost_timer = 0
        self.ship.x, self.ship.y = WIDTH * 0.5, HEIGHT * 0.78
        self.shield_t = 0
        self.enemies, self.proj, self.bullets, self.parts = [], [], [], []
        self.boss = None
        self.boss_idx = 1
        self.phase = "ALIENS"
        self.ptimer = 0
        self.kills = 0
        self.spawn_t = 30
        self.cool = 0
        self.fire_t = 60
        self.ring_t = 180
        self.spin = 0.0
        self.dash_t = 0
        self.dash_cd = 90
        self.dash_dir = [0, -1]
        self.dash_hit = False
        self.wave_r = 0.0
        self.wave_cd = 260
        self.wx = self.wy = 0.0
        self.flash = 0
        self.flash_surf = pygame.Surface((WIDTH, HEIGHT))
        self.flash_surf.fill((255, 240, 200))

    # ---- utilidades
    def shoot(self, x, y, ang, sp):
        if len(self.bullets) < 80:
            self.bullets.append(EnemyBullet(x, y, ang, sp))

    def burst(self, x, y, n, sp=1.6):
        for _ in range(n):
            if len(self.parts) < 90:
                self.parts.append(Particle(x, y, random.uniform(-sp, sp), random.uniform(-sp, sp), True))

    def target(self):
        s = self.ship
        best, bd = None, 1e18
        cands = [e for e in self.enemies if 0 <= e.x <= WIDTH and 0 <= e.y <= HEIGHT]
        if self.boss is not None and self.boss.state == "FIGHT":
            cands.append(self.boss)
        for o in cands:
            d = (o.x - s.x) ** 2 + (o.y - s.y) ** 2
            if d < bd:
                best, bd = o, d
        return best

    def kill_enemy(self, e):
        if e in self.enemies:
            self.enemies.remove(e)
        self.kills += 1
        fx_boom(e.x, e.y, 0.9)
        self.burst(e.x, e.y, 8)

    def start_boss(self):
        b = Boss(self.boss_idx)
        b.x, b.y = WIDTH * 0.5, -40.0
        b.state = "INTRO"
        b.max_hp = b.hp = 60
        b.vx = 0.0
        b.vy = 0.0
        b.osc = 0.0
        self.boss = b
        add_shake(8)
        self.phase = "BOSS"
        self.ptimer = 0
        self.fire_t, self.ring_t, self.spin = 60, 180, 0.0

    # ---- lógica
    def update(self):
        s = self.ship
        self.t += 1
        self.ptimer += 1
        update_fx()

        # fases: aliens -> boss -> aliens (cada vez otro boss)
        if self.phase == "ALIENS":
            self.spawn_t -= 1
            if self.spawn_t <= 0 and len(self.enemies) < 8:
                self.enemies.append(Enemy(s.x, s.y, 1.8, None, 0.4))
                self.spawn_t = random.randint(14, 32)
            if self.kills >= 14 or self.ptimer > 700:
                self.start_boss()
        b = self.boss
        if b is not None:
            self.update_boss(b)
        if self.flash > 0:
            self.flash -= 1

        # onda expansiva cuando hay mucho que limpiar
        self.wave_cd -= 1
        if self.wave_r == 0 and self.wave_cd <= 0:
            fight = self.boss is not None and self.boss.state == "FIGHT"
            if len(self.enemies) >= 4 or (fight and len(self.bullets) > 25):
                self.wave_r = 10.0
                self.wx, self.wy = s.x, s.y
                self.wave_cd = 420
                add_shake(10)
                if fight:
                    self.boss.hp -= 6
                    self.boss.hit_flash = 8
        if self.wave_r > 0:
            self.wave_r += HEIGHT * 0.045
            for e in self.enemies[:]:
                if math.hypot(e.x - self.wx, e.y - self.wy) <= self.wave_r:
                    self.kill_enemy(e)
            self.bullets[:] = [q for q in self.bullets if math.hypot(q.x - self.wx, q.y - self.wy) > self.wave_r]
            if self.wave_r > max(WIDTH, HEIGHT) * 1.1:
                self.wave_r = 0.0

        # piloto: orbita por la zona baja y esquiva balas y aliens
        bx = WIDTH * 0.5 + math.sin(self.t * 0.017) * WIDTH * 0.36
        by = HEIGHT * 0.74 + math.sin(self.t * 0.026 + 1.0) * HEIGHT * 0.11
        fx = fy = 0.0
        for q in self.bullets:
            d = math.hypot(s.x - q.x, s.y - q.y)
            if 0 < d < 52:
                k = (52 - d) / 52.0
                fx += (s.x - q.x) / d * k
                fy += (s.y - q.y) / d * k
        for e in self.enemies:
            d = math.hypot(s.x - e.x, s.y - e.y)
            if 0 < d < 64:
                k = (64 - d) / 64.0
                fx += (s.x - e.x) / d * k
                fy += (s.y - e.y) / d * k
        # embestida (dash) hacia el objetivo cuando está lista
        self.dash_cd -= 1
        if self.dash_t <= 0 and self.dash_cd <= 0:
            tg = self.target()
            if tg is not None and math.hypot(tg.x - s.x, tg.y - s.y) < 320:
                d = math.hypot(tg.x - s.x, tg.y - s.y) or 1.0
                self.dash_dir = [(tg.x - s.x) / d, (tg.y - s.y) / d]
                self.dash_t = 13
                self.dash_hit = False
                self.dash_cd = random.randint(120, 200)
        if self.dash_t > 0:
            self.dash_t -= 1
            s.x = max(20.0, min(WIDTH - 20.0, s.x + self.dash_dir[0] * 10.0))
            s.y = max(HEIGHT * 0.3, min(HEIGHT - 22.0, s.y + self.dash_dir[1] * 10.0))
            for _ in range(3):
                if len(self.parts) < 110:
                    pt = Particle(s.x - self.dash_dir[0] * 10 + random.uniform(-5, 5),
                                  s.y - self.dash_dir[1] * 10 + random.uniform(-5, 5),
                                  -self.dash_dir[0] * random.uniform(0.3, 1.2), -self.dash_dir[1] * random.uniform(0.3, 1.2))
                    pt.color = random.choice([CYAN, WHITE, (90, 200, 255)])
                    pt.size = random.uniform(2.5, 4.0)
                    self.parts.append(pt)
        else:
            vx = (bx - s.x) * 0.05 + fx * 4.0
            vy = (by - s.y) * 0.05 + fy * 4.0
            sp = math.hypot(vx, vy)
            if sp > 4.6:
                vx, vy = vx * 4.6 / sp, vy * 4.6 / sp
            s.x = max(20.0, min(WIDTH - 20.0, s.x + vx))
            s.y = max(HEIGHT * 0.38, min(HEIGHT - 22.0, s.y + vy))
        s.dash_timer = self.dash_t
        s.rect.center = (int(s.x), int(s.y))

        # apunta (con anticipación) y dispara
        t = self.target()
        if t is not None:
            dx, dy = t.x - s.x, t.y - s.y
            tt = math.hypot(dx, dy) / (HEIGHT * 0.025)
            dx += getattr(t, "vx", 0.0) * tt
            dy += getattr(t, "vy", 0.0) * tt
            m = math.hypot(dx, dy) or 1.0
            s.aim_dir = [dx / m, dy / m]
            s.aim_active = True
        else:
            s.aim_active = False
            s.last_dir = [0, -1]
        self.cool -= 1
        if t is not None and self.cool <= 0:
            self.proj.append(Projectile(s.x, s.y, s.aim_dir))
            self.cool = 5
        face = s.aim_dir if s.aim_active else s.last_dir
        if self.t % 2 == 0 and len(self.parts) < 90:
            self.parts.append(Particle(s.x - face[0] * 9, s.y - face[1] * 9,
                                       -face[0] * random.uniform(0.7, 1.6), -face[1] * random.uniform(0.7, 1.6)))
        if vg_on:
            s.trail.append((s.x, s.y))
            del s.trail[:-14]

        for q in self.proj:
            q.update()
        self.proj[:] = [q for q in self.proj if not q.is_off_screen()]

        # aliens
        for e in self.enemies[:]:
            if e.update(s.x, s.y):
                self.shoot(e.x, e.y, math.atan2(s.y - e.y, s.x - e.x), HEIGHT * 0.0045)
            if s.rect.inflate(4, 4).colliderect(e.rect):        # el escudo lo destruye
                self.shield_t = 16
                self.kill_enemy(e)
                continue
            for q in self.proj:
                if q.rect.colliderect(e.rect):
                    self.proj.remove(q)
                    self.kill_enemy(e)
                    break

        # balas enemigas: el escudo del piloto las absorbe (nunca muere)
        for q in self.bullets[:]:
            q.update()
            if q.is_off_screen():
                self.bullets.remove(q)
            elif s.rect.inflate(-10, -10).colliderect(q.rect):
                self.bullets.remove(q)
                self.shield_t = 16
                self.burst(q.x, q.y, 4, 1.2)
        s.shield = self.shield_t > 0
        if self.shield_t > 0:
            self.shield_t -= 1

        for p_ in self.parts:
            p_.update()
        self.parts[:] = [p_ for p_ in self.parts if p_.life > 0]

    def update_boss(self, b):
        s = self.ship
        ox, oy = b.x, b.y
        if b.hit_flash > 0:
            b.hit_flash -= 1
        if b.state == "INTRO":
            b.y += 1.4
            if b.y >= HEIGHT * 0.30:
                b.y = HEIGHT * 0.30
                b.state = "FIGHT"
        elif b.state == "FIGHT":
            ratio = b.hp / float(b.max_hp)
            b.phase = 1 if ratio > 0.66 else 2 if ratio > 0.33 else 3
            b.osc += 0.013 + 0.004 * b.phase
            b.x = WIDTH / 2.0 + math.sin(b.osc) * WIDTH * 0.3
            b.y = HEIGHT * 0.30 + math.sin(b.osc * 2.3) * 8
            self.fire_t -= 1
            if b.idx == 3:                                        # espirales
                if self.t % 5 == 0:
                    for k in range(b.phase):
                        self.shoot(b.x, b.y, self.spin + k * 6.2832 / b.phase, HEIGHT * 0.0042)
                    self.spin += 0.32
            elif self.fire_t <= 0:
                ang = math.atan2(s.y - b.y, s.x - b.x)
                for i in range(3):
                    self.shoot(b.x, b.y + 20, ang + (i - 1) * 0.24, HEIGHT * 0.0045)
                self.fire_t = 80 - 10 * b.phase
            if b.idx == 2 and self.t % 45 == 0:                   # lluvia de meteoritos
                self.shoot(random.uniform(14, WIDTH - 14), -8, 1.5708, HEIGHT * random.uniform(0.004, 0.006))
            if b.idx == 1 and b.phase >= 2:
                self.ring_t -= 1
                if self.ring_t <= 0:
                    off = random.uniform(0, 6.28)
                    for i in range(12):
                        self.shoot(b.x, b.y, off + i * 6.2832 / 12, HEIGHT * 0.0036)
                    self.ring_t = 230
            for q in self.proj[:]:
                if q.rect.colliderect(b.hit_rect):
                    self.proj.remove(q)
                    b.hp -= 1
                    b.hit_flash = 3
                    self.burst(q.x, q.y, 2, 1.3)
            if self.dash_t > 0 and not self.dash_hit and s.rect.colliderect(b.hit_rect):
                self.dash_hit = True                              # la embestida golpea fuerte
                b.hp -= 5
                b.hit_flash = 8
                self.burst(s.x, s.y, 10, 2.2)
                add_shake(6)
            if b.hp <= 0 or self.ptimer > 1400:
                b.hp = 0
                b.state = "DYING"
                b.dying = 90
                self.bullets[:] = []
                fx_boom(b.x, b.y, 3.0)
                add_shake(26)
                self.flash = 14
        elif b.state == "DYING":
            b.dying -= 1
            if b.dying % 4 == 0:
                self.burst(b.x + random.uniform(-40, 40), b.y + random.uniform(-25, 25), 5, 1.8)
            if b.dying % 14 == 0:
                fx_boom(b.x + random.uniform(-40, 40), b.y + random.uniform(-25, 25), 1.5)
                add_shake(6)
            if b.dying <= 0:
                self.boss = None
                self.phase = "ALIENS"
                self.boss_idx = self.boss_idx % NUM_BOSSES + 1
                self.kills = 0
                self.ptimer = 0
                self.spawn_t = 40
                return
        b.rect.center = (int(b.x), int(b.y))
        b.hit_rect.center = b.rect.center
        b.vx, b.vy = b.x - ox, b.y - oy

    # ---- dibujo
    def draw(self, surface):
        for p_ in self.parts:
            p_.draw(surface)
        for e in self.enemies:
            e.draw(surface)
        if self.boss is not None:
            self.boss.draw(surface)
        for q in self.bullets:
            q.draw(surface)
        for q in self.proj:
            q.draw(surface)
        draw_fx(surface)
        if self.wave_r > 0:
            wr, c = int(self.wave_r), (int(self.wx), int(self.wy))
            pygame.draw.circle(surface, (0, 50, 80), c, wr + 6, 4)
            pygame.draw.circle(surface, (0, 120, 170), c, wr, 7)
            pygame.draw.circle(surface, CYAN, c, max(1, wr - 1), 4)
            pygame.draw.circle(surface, WHITE, c, max(1, wr - 2), 1)
        self.ship.draw(surface)
        if self.flash > 0:
            self.flash_surf.set_alpha(min(180, self.flash * 14))
            surface.blit(self.flash_surf, (0, 0))


# =====================================================================
#  INICIALIZACIÓN
# =====================================================================
joy_rad = max(40, int(HEIGHT * 0.15))
btn_s = max(30, int(HEIGHT * 0.10))
M = 14  # margen

joystick = VirtualJoystick(joy_rad + M, HEIGHT - joy_rad - M, joy_rad)
shoot_btn = ModernButton(WIDTH - btn_s * 1.5 - M, HEIGHT - btn_s * 1.5 - M, btn_s * 3, btn_s * 3, "FUEGO", True)
nuke_btn = ModernButton(WIDTH - btn_s * 1.2 - 7, HEIGHT - btn_s * 4.5 - M, btn_s * 2.4, btn_s * 2.4, "ONDA", True, True)
pause_btn = ModernButton(WIDTH - 24, 14, 32, 22, "||", False)
# IMPULSO (dash) a la izquierda del botón de fuego, y pequeño botón "+" para fijar el disparo
dash_btn = ModernButton(WIDTH - btn_s * 3 - M - 6 - btn_s * 1.1, HEIGHT - btn_s * 1.1 - M,
                        btn_s * 2.2, btn_s * 2.2, "IMPULSO", True, False, True)
lock_btn = ModernButton(dash_btn.rect.centerx, dash_btn.rect.top - 20, 30, 30, "", True)

BW = int(WIDTH * 0.4)
BH = int(HEIGHT * 0.1)
btn_infinite = ModernButton(WIDTH // 2, int(HEIGHT * 0.47), BW, BH, "INFINITO")
btn_levels = ModernButton(WIDTH // 2, int(HEIGHT * 0.62), BW, BH, "HISTORIA")
btn_shop = ModernButton(WIDTH // 2, int(HEIGHT * 0.77), BW, BH, "TIENDA")
btn_color = ModernButton(WIDTH - 24, 24, 34, 34, "", True)       # bolita de colores (esquina)
btn_shop_back = ModernButton(WIDTH // 2, int(HEIGHT * 0.92), int(WIDTH * 0.34), BH, "VOLVER")
btn_rename = ModernButton(int(WIDTH * 0.13), int(HEIGHT * 0.07), int(WIDTH * 0.2), int(HEIGHT * 0.08), "PERFIL")
btn_resume = ModernButton(WIDTH // 2, HEIGHT // 2 - 17, BW, BH, "CONTINUAR")
btn_menu = ModernButton(WIDTH // 2, HEIGHT // 2 + 23, BW, BH, "MENU PRINCIPAL")
btn_retry = ModernButton(WIDTH // 2, HEIGHT // 2 - 4, BW, BH, "REINTENTAR")
btn_menu_end = ModernButton(WIDTH // 2, HEIGHT // 2 + 40, BW, BH, "MENU PRINCIPAL")
btn_name_ok = ModernButton(WIDTH // 2, int(HEIGHT * 0.88), int(WIDTH * 0.34), BH, "ACEPTAR")
btn_color_ok = ModernButton(WIDTH // 2, int(HEIGHT * 0.90), int(WIDTH * 0.34), BH, "LISTO")
btn_name_del = ModernButton(int(WIDTH * 0.17), int(HEIGHT * 0.88), int(WIDTH * 0.22), BH, "ELIMINAR")
btn_del_yes = ModernButton(WIDTH // 2 - int(WIDTH * 0.13), int(HEIGHT * 0.62), int(WIDTH * 0.2), BH, "SI, BORRAR")
btn_del_no = ModernButton(WIDTH // 2 + int(WIDTH * 0.13), int(HEIGHT * 0.62), int(WIDTH * 0.2), BH, "CANCELAR")
btn_map_prev = ModernButton(int(WIDTH * 0.045), int(HEIGHT * 0.5), int(WIDTH * 0.06), int(HEIGHT * 0.12), "<")
btn_map_next = ModernButton(int(WIDTH * 0.955), int(HEIGHT * 0.5), int(WIDTH * 0.06), int(HEIGHT * 0.12), ">")
btn_map_back = ModernButton(int(WIDTH * 0.13), int(HEIGHT * 0.92), int(WIDTH * 0.2), int(HEIGHT * 0.08), "VOLVER")
# ---- AJUSTES (engrane) y editor de controles ----
btn_gear = ModernButton(WIDTH - 24, HEIGHT - 24, 36, 36, "", True)
btn_set_back = ModernButton(WIDTH // 2, int(HEIGHT * 0.90), int(WIDTH * 0.34), BH, "VOLVER")
btn_set_cont = ModernButton(WIDTH // 2, int(HEIGHT * 0.62), int(WIDTH * 0.5), BH, "CONTINUO: NO")
btn_set_move = ModernButton(int(WIDTH * 0.30), int(HEIGHT * 0.77), int(WIDTH * 0.38), BH, "MOVER CONTROLES")
btn_set_reset = ModernButton(int(WIDTH * 0.70), int(HEIGHT * 0.77), int(WIDTH * 0.38), BH, "RESTABLECER")
btn_lay_done = ModernButton(WIDTH // 2, int(HEIGHT * 0.90), int(WIDTH * 0.2), BH, "LISTO")
btn_lay_reset = ModernButton(WIDTH // 2, int(HEIGHT * 0.78), int(WIDTH * 0.26), BH, "RESTABLECER")
preview_btn = ModernButton(0, 0, 40, 40, "", True)

CTRL_NAMES = ["joy", "shoot", "nuke", "dash", "lock", "pause"]
CTRL_OBJ = {"joy": joystick, "shoot": shoot_btn, "nuke": nuke_btn, "dash": dash_btn, "lock": lock_btn, "pause": pause_btn}


def ctrl_center(name):
    o = CTRL_OBJ[name]
    return o.base_pos if name == "joy" else o.rect.center


def ctrl_rect(name):
    o = CTRL_OBJ[name]
    if name == "joy":
        r = int(o.radius)
        return pygame.Rect(o.base_pos[0] - r, o.base_pos[1] - r, 2 * r, 2 * r)
    return o.rect


def ctrl_set(name, cx, cy):
    cx = max(20, min(WIDTH - 20, int(cx)))
    cy = max(20, min(HEIGHT - 20, int(cy)))
    o = CTRL_OBJ[name]
    if name == "joy":
        o.base_pos = (cx, cy)
        o.reset()
    else:
        o.rect.center = (cx, cy)


def ctrl_hit(name, tx, ty):
    o = CTRL_OBJ[name]
    if name == "joy":
        return math.hypot(tx - o.base_pos[0], ty - o.base_pos[1]) < o.radius * 1.2
    return o.rect.inflate(18, 18).collidepoint(tx, ty)


CTRL_DEFAULT = {n: (ctrl_center(n)[0] / float(WIDTH), ctrl_center(n)[1] / float(HEIGHT)) for n in CTRL_NAMES}
ctrl_pos = {}            # posiciones personalizadas (fracción de la pantalla); vacío = las de fábrica
cont_mode = False         # AJUSTES > CONTINUO: al acabar un nivel sigue directo con el siguiente (sin pasar por el mapa)
fade_in_t = 0            # cuadros restantes de aparición desde negro (modo continuo)
ctrl_alpha = 1.0         # opacidad de los controles en partida (0.2 .. 1.0)


def apply_ctrl_layout():
    for n in CTRL_NAMES:
        fx, fy = ctrl_pos.get(n, CTRL_DEFAULT[n])
        ctrl_set(n, fx * WIDTH, fy * HEIGHT)


def reset_ctrl_layout():
    ctrl_pos.clear()
    apply_ctrl_layout()


def make_gear_icon(d):
    s = pygame.Surface((d, d), pygame.SRCALPHA)
    c = d / 2.0
    r_out, r_in, teeth = d * 0.47, d * 0.34, 8
    pts = []
    for i in range(teeth):
        a = 6.2832 * i / teeth
        for da, rr in ((-0.30, r_in), (-0.19, r_out), (0.19, r_out), (0.30, r_in)):
            pts.append((c + math.cos(a + da) * rr, c + math.sin(a + da) * rr))
    pygame.draw.polygon(s, (215, 225, 245), pts)
    pygame.draw.polygon(s, (90, 110, 150), pts, 1)
    pygame.draw.circle(s, (34, 44, 70), (int(c), int(c)), int(d * 0.16))
    pygame.draw.circle(s, (90, 110, 150), (int(c), int(c)), int(d * 0.16), 1)
    return s


GEAR_ICON = make_gear_icon(26)
_ld(0.9, "Armando menus")


def draw_gear_button():
    btn_gear.draw(canvas)
    canvas.blit(GEAR_ICON, GEAR_ICON.get_rect(center=btn_gear.rect.center))


class Slider:
    def __init__(self, label, cx, y, w, value):
        self.label = label
        self.rect = pygame.Rect(0, 0, int(w), 12)
        self.rect.midtop = (int(cx), int(y))
        self.value = value
        self.touch_id = None

    def _set_from(self, tx):
        self.value = max(0.0, min(1.0, (tx - self.rect.left) / float(self.rect.width)))

    def process_event(self, e_type, tid, tx, ty):
        """Devuelve 'change' mientras se arrastra, 'release' al soltar, o None."""
        if e_type == 'down' and self.rect.inflate(26, 40).collidepoint(tx, ty):
            self.touch_id = tid
            self._set_from(tx)
            return 'change'
        if e_type == 'motion' and self.touch_id == tid:
            self._set_from(tx)
            return 'change'
        if e_type == 'up' and self.touch_id == tid:
            self.touch_id = None
            return 'release'
        return None

    def draw(self, shown):
        r = self.rect
        canvas.blit(text_surf(font_medium, self.label, WHITE), (r.left, r.top - 22))
        t = text_surf(font_medium, shown, YELLOW)
        canvas.blit(t, (r.right - t.get_width(), r.top - 22))
        pygame.draw.rect(canvas, (22, 24, 40), r)
        fw = int(self.value * r.width)
        if fw > 0:
            pygame.draw.rect(canvas, (0, 170, 220), (r.left, r.top, fw, r.height))
            pygame.draw.rect(canvas, (140, 235, 255), (r.left, r.top, fw, 2))
        pygame.draw.rect(canvas, LIGHT_GRAY, r, 1)
        kx = r.left + fw
        pygame.draw.circle(canvas, (20, 30, 55), (kx, r.centery), 10)
        pygame.draw.circle(canvas, WHITE if self.touch_id is not None else CYAN, (kx, r.centery), 8)
        pygame.draw.circle(canvas, (20, 30, 55), (kx, r.centery), 3)


_sl_w = int(WIDTH * 0.5)
sl_music = Slider("MUSICA", WIDTH // 2, int(HEIGHT * 0.22), _sl_w, 1.0)
sl_sfx = Slider("EFECTOS", WIDTH // 2, int(HEIGHT * 0.35), _sl_w, 1.0)
sl_alpha = Slider("TRANSPARENCIA", WIDTH // 2, int(HEIGHT * 0.48), _sl_w, 1.0)


def draw_control(fn, rect):
    """Dibuja un control con la opacidad elegida en AJUSTES (copia el fondo, dibuja y mezcla)."""
    if ctrl_alpha >= 0.98:
        fn()
        return
    r = pygame.Rect(rect).inflate(52, 52).clip(canvas.get_rect())
    if r.w <= 0 or r.h <= 0:
        fn()
        return
    bg = canvas.subsurface(r).copy()
    fn()
    top = canvas.subsurface(r).copy()
    top.set_alpha(int(255 * ctrl_alpha))
    canvas.blit(bg, r.topleft)
    canvas.blit(top, r.topleft)


def draw_controls(nuke_p, dash_ready, dash_p, lock_on):
    draw_control(lambda: joystick.draw(canvas), ctrl_rect("joy"))
    draw_control(lambda: shoot_btn.draw(canvas), shoot_btn.rect)
    draw_control(lambda: nuke_btn.draw(canvas, nuke_ready=(nuke_p >= 1.0), nuke_progress=nuke_p), nuke_btn.rect)
    draw_control(lambda: pause_btn.draw(canvas), pause_btn.rect)
    draw_control(lambda: dash_btn.draw(canvas, nuke_ready=dash_ready, nuke_progress=dash_p), dash_btn.rect)

    def _lock():
        lock_btn.active = lock_on
        lock_btn.draw(canvas)
        lc = YELLOW if lock_on else WHITE
        lx, ly = lock_btn.rect.center
        pygame.draw.line(canvas, lc, (lx - 7, ly), (lx + 7, ly), 2)
        pygame.draw.line(canvas, lc, (lx, ly - 7), (lx, ly + 7), 2)
    draw_control(_lock, lock_btn.rect)


btn_story_skip = ModernButton(WIDTH - 46, 22, 80, 28, "SALTAR")
ALL_BUTTONS = (btn_story_skip, btn_gear, btn_set_back, btn_set_cont, btn_set_move, btn_set_reset, btn_lay_done, btn_lay_reset, preview_btn,
               shoot_btn, nuke_btn, dash_btn, lock_btn, pause_btn, btn_infinite, btn_levels, btn_color, btn_shop, btn_shop_back, btn_rename,
               btn_resume, btn_menu, btn_retry, btn_menu_end, btn_name_ok, btn_color_ok, btn_name_del, btn_del_yes, btn_del_no,
               btn_map_prev, btn_map_next, btn_map_back)

# Superficies de efectos cacheadas (nada de crear surfaces cada frame)
dark_surf = pygame.Surface((WIDTH, HEIGHT))
dark_surf.fill((0, 0, 0))
dark_surf.set_alpha(170)
flash_surf = pygame.Surface((WIDTH, HEIGHT))
flash_surf.fill((255, 30, 30))
flash_timer = 0

game_state = "NAME"
game_mode = "INFINITE"
current_level = 1
transition_timer = 0
transition_msg = ""

# ---- HISTORIA: 8 sectores x 5 niveles (el nivel 5 de cada sector termina con un BOSS distinto) ----
SECTORS = 8
# Niveles por sector: los 4 primeros tienen 5; desde el sector 5 va subiendo hasta 10 en el sector 8.
# (Cambia esta lista si quieres otra progresión.)
SECTOR_LEVELS = (5, 5, 5, 5, 6, 7, 9, 10)
SECTOR_START = [sum(SECTOR_LEVELS[:i]) for i in range(SECTORS)]      # nodo global donde empieza cada sector
TOTAL_NODES = sum(SECTOR_LEVELS)
PARTS_PER_LEVEL = 3                                                  # cada nivel se juega en 3 partes
PART_TOTAL_MULT = (0.85, 1.0, 1.2)                                   # enemigos de cada parte (la 3ª es la más dura)
PART_SPEED_MULT = (1.0, 1.05, 1.1)


def node_sec(g):
    """Nodo global -> (sector, nivel dentro del sector empezando en 0)."""
    g = max(0, min(TOTAL_NODES - 1, g))
    for sec in range(SECTORS - 1, -1, -1):
        if g >= SECTOR_START[sec]:
            return sec, g - SECTOR_START[sec]
    return 0, 0


def node_g(sec, n):
    return SECTOR_START[sec] + n


def sec_of_progress(p):
    return node_sec(p)[0] if p < TOTAL_NODES else SECTORS - 1
SECTOR_NAMES = ["NEBULOSA ALFA", "CINTURON ROJO", "NUCLEO ESTELAR", "ABISMO GLACIAL",
                "COLMENA VERDE", "VACIO OSCURO", "FORJA SOLAR", "TRONO GALACTICO"]
SECTOR_COLORS = [(0, 240, 255), (255, 150, 30), (210, 100, 255), (120, 200, 255),
                 (120, 230, 90), (255, 80, 200), (255, 210, 60), (255, 70, 90)]
BASE_TOTALS = {1: 6, 2: 9, 3: 13, 4: 18, 5: 24}     # enemigos por nivel en el sector 1 (los de siempre)
SEC_TOTAL_MULT = (1.0, 1.35, 1.8, 2.1, 2.4, 2.7, 3.0, 3.3)       # más enemigos por nivel
SEC_SPEED_MULT = (1.0, 1.2, 1.4, 1.5, 1.62, 1.74, 1.86, 2.0)     # enemigos más rápidos
SEC_SHOOT = (0.0, 0.25, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75)         # probabilidad de que un alien dispare


def _diff_at(n, L):
    """Dificultad equivalente (escala 1..5) del nivel n de un sector con L niveles."""
    if L <= 1:
        return 5.0
    return 1.0 + 4.0 * (n - 1) / float(L - 1)


def _base_total(d):
    lo = int(d)
    hi = min(5, lo + 1)
    f = d - lo
    return BASE_TOTALS[lo] + (BASE_TOTALS[hi] - BASE_TOTALS[lo]) * f


def make_level_stage(sec, n, part=1):
    """Una PARTE (1..3) del nivel n del sector sec."""
    L = SECTOR_LEVELS[sec]
    d = _diff_at(n, L)
    p = part - 1
    return {"type": "level", "sec": sec, "num": n, "part": part,
            "total": max(4, int(round(_base_total(d) * SEC_TOTAL_MULT[sec] * PART_TOTAL_MULT[p]))),
            "speed": (1.0 + 0.06 * (d - 1)) * SEC_SPEED_MULT[sec] * PART_SPEED_MULT[p],
            "on_screen": min(min(10 + 2 * sec, 14), 2 + int(round(d)) + 2 * sec + p),
            "interval": max(220, 500 - 100 * sec, 1100 - int(80 * d) - 150 * sec - 40 * p),
            "shoot": SEC_SHOOT[sec],
            "label": "Nivel %d-%d  P%d/%d" % (sec + 1, n, part, PARTS_PER_LEVEL)}


def build_node_stages(g):
    """Etapas del nodo g del mapa: 3 partes. El último nivel de cada sector termina además con el BOSS."""
    sec, n = node_sec(g)
    n += 1
    out = [make_level_stage(sec, n, pt) for pt in range(1, PARTS_PER_LEVEL + 1)]
    if n == SECTOR_LEVELS[sec]:
        k = sec + 1
        out.append({"type": "boss", "idx": k, "sec": sec, "label": BOSS_NAMES[k]})
    return out


stages = build_node_stages(0)
stage_idx = 0
stage = None
level_spawned = 0
level_cleared = 0
boss = None
INF_BOSS_EVERY = 50     # modo INFINITO: cada 50 puntos aparece un boss al azar
inf_next_boss = INF_BOSS_EVERY
inf_defeated = 0
inf_last_boss = 0
enemy_bullets = []
aim_lock = False        # disparo fijado: apunta y dispara solo al enemigo más cercano
lock_target = None

player = Player()
projectiles = []
enemies = []
orbs = []
lives_list = []
particles = []
powerups = []

score = 0
shoot_cooldown = 0
wave_active = False
wave_radius = 0.0
menu_time = 0.0

fade_surf = pygame.Surface((WIDTH, HEIGHT))
fade_surf.fill((0, 0, 0))
ENEMY_SPAWN = pygame.USEREVENT + 1
LIFE_SPAWN = pygame.USEREVENT + 2
pygame.time.set_timer(ENEMY_SPAWN, 1000)
pygame.time.set_timer(LIFE_SPAWN, 30000)
POWER_SPAWN = pygame.USEREVENT + 3
pygame.time.set_timer(POWER_SPAWN, 20000)


def release_all():
    """Suelta todos los botones/joystick (evita que el disparo se quede 'pegado')."""
    for b in ALL_BUTTONS:
        b.is_pressed = False
        b.touch_id = None
    joystick.reset()


def start_stage(i):
    """Arranca el nivel / boss número i de la lista 'stages'."""
    global stage_idx, stage, level_spawned, level_cleared, boss, current_level
    stage_idx = i
    stage = stages[i]
    level_spawned = 0
    level_cleared = 0
    boss = None
    enemy_bullets.clear()
    if stage["type"] == "level":
        current_level = stage["num"]
        pygame.time.set_timer(ENEMY_SPAWN, stage["interval"])
        set_music("game")
    else:
        boss = Boss(stage["idx"])
        pygame.time.set_timer(ENEMY_SPAWN, 0)
        set_music(None)
        scenes = lore_scenes("bp", stage["idx"] - 1) if game_mode == "LEVELS" else []
        if scenes:
            save_game()

            def _go():
                global game_state
                game_state = "PLAYING"
                release_all()
                set_music(None)
                play("warning")
            run_story(scenes, _go)
        else:
            play("warning")


def find_target():
    """Enemigo (o boss) visible más cercano a la nave."""
    best, bd = None, 1e18
    cands = list(enemies)
    if boss is not None and boss.state == "FIGHT" and not boss.ghost:
        cands.append(boss)
    for o in cands:
        r = o.hit_rect if o is boss else o.rect
        if r.right < 0 or r.left > WIDTH or r.bottom < 0 or r.top > HEIGHT:
            continue
        d = (o.x - player.x) ** 2 + (o.y - player.y) ** 2
        if d < bd:
            best, bd = o, d
    return best


def aim_at(o):
    """Dirección hacia el objetivo, anticipando su movimiento."""
    dx, dy = o.x - player.x, o.y - player.y
    t = math.hypot(dx, dy) / (HEIGHT * 0.025)
    dx += getattr(o, "vx", 0.0) * t
    dy += getattr(o, "vy", 0.0) * t
    m = math.hypot(dx, dy) or 1.0
    return [dx / m, dy / m]


def hurt_player():
    global game_state, flash_timer
    if player.shield:                       # el escudo se rompe al primer toque
        player.shield = False
        player.invul_timer = 50
        play("shield_break")
        for _ in range(16):
            if len(particles) < 200:
                particles.append(Particle(player.x, player.y, random.uniform(-2.2, 2.2), random.uniform(-2.2, 2.2), True))
        return
    player.lives -= 1
    player.invul_timer = 60
    flash_timer = 8
    add_shake(10)
    play("hurt")
    if player.lives <= 0:
        game_state = "GAMEOVER"
        release_all()
        set_music(None)
        play("gameover")
        save_game()


def start_infinite_boss():
    """Modo INFINITO: aparece un boss al azar (distinto al anterior) y se pausan los aliens normales."""
    global boss, inf_last_boss
    k = random.choice([i for i in range(1, NUM_BOSSES + 1) if i != inf_last_boss])
    inf_last_boss = k
    for e in enemies:
        fx_boom(e.x, e.y, 0.8)
    enemies.clear()
    enemy_bullets.clear()
    boss = Boss(k, 0.8 + 0.1 * min(inf_defeated, 8))      # cada boss derrotado hace al siguiente algo más duro
    pygame.time.set_timer(ENEMY_SPAWN, 0)
    set_music(None)
    play("warning")


def end_infinite_boss():
    """Boss del modo INFINITO derrotado: premio y se reanuda la oleada normal."""
    global boss, inf_next_boss, inf_defeated, coins_q, run_coins_q, coins_dirty
    boss = None
    inf_defeated += 1
    inf_next_boss = (score // INF_BOSS_EVERY + 1) * INF_BOSS_EVERY
    player.lives = min(max_lives(), player.lives + 1)
    coins_q += 8                       # +2 monedas por vencer a un boss
    run_coins_q += 8
    coins_dirty = True
    enemy_bullets.clear()
    pygame.time.set_timer(ENEMY_SPAWN, 1000)
    set_music("game")


def reset_game(mode, node=0):
    global inf_next_boss, inf_defeated, inf_last_boss
    inf_next_boss, inf_defeated, inf_last_boss = INF_BOSS_EVERY, 0, 0
    global player, score, game_state, game_mode, current_level, wave_active, flash_timer, stage, boss, aim_lock, lock_target, current_node, run_coins_q
    player = Player()
    projectiles.clear()
    enemies.clear()
    orbs.clear()
    lives_list.clear()
    particles.clear()
    powerups.clear()
    enemy_bullets.clear()
    coin_pops.clear()
    fx_list.clear()
    run_coins_q = 0
    score = 0
    wave_active = False
    flash_timer = 0
    game_mode = mode
    current_level = 1
    stage = None
    boss = None
    aim_lock = False
    lock_target = None
    game_state = "PLAYING"
    play("click")
    if mode == "LEVELS":
        current_node = node
        stages[:] = build_node_stages(node)
        start_stage(0)
    else:
        pygame.time.set_timer(ENEMY_SPAWN, 1000)
        set_music("game")
    release_all()


# =====================================================================
#  GUARDADO, PANTALLAS (nombre / color / mapa) Y POTENCIADORES
# =====================================================================
try:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except Exception:
    _BASE_DIR = os.getcwd()
SAVE_PATH = os.path.join(_BASE_DIR, "conturboll_save.json")

NAME_MAX = 10
player_name = ""
name_buf = ""
progress = 0            # nodos de historia completados (0..TOTAL_NODES)
current_node = 0
map_sec = 0
_last_ui = 0
_last_tag = None


profiles = {}           # nombre -> {"ship", "progress", "coins_q", "upg"}
input_block_until = 0   # ms: ignora toques nuevos justo tras cambiar de pantalla


def block_input(ms=260):
    global input_block_until
    input_block_until = pygame.time.get_ticks() + ms


lore_seen = set()        # fragmentos de historia ya mostrados a este perfil ('intro', 's0', 'bp0', 'bw0', 'end'...)


def new_profile_data():
    return {"ship": 0, "progress": 0, "coins_q": 0, "upg": {u["key"]: 0 for u in UPGRADES}, "lore": [], "pv": 2}


def settings_dict():
    return {"music": round(music_vol, 3), "sfx": round(sfx_vol, 3), "alpha": round(ctrl_alpha, 3), "cont": bool(cont_mode),
            "pos": {n: [round(v[0], 4), round(v[1], 4)] for n, v in ctrl_pos.items()}}


def settings_apply(d):
    global music_vol, sfx_vol, ctrl_alpha, cont_mode
    try:
        cont_mode = bool(d.get("cont", False))
        music_vol = max(0.0, min(1.0, float(d.get("music", 1.0))))
        sfx_vol = max(0.0, min(1.0, float(d.get("sfx", 1.0))))
        ctrl_alpha = max(0.2, min(1.0, float(d.get("alpha", 1.0))))
        ctrl_pos.clear()
        for n, v in dict(d.get("pos", {})).items():
            if n in CTRL_NAMES:
                ctrl_pos[n] = (max(0.0, min(1.0, float(v[0]))), max(0.0, min(1.0, float(v[1]))))
    except Exception:
        pass
    apply_ctrl_layout()
    apply_sfx_volume()
    apply_music_volume()


def save_game():
    """Guarda TODOS los perfiles; el activo se actualiza con el estado actual."""
    global coins_dirty
    coins_dirty = False
    try:
        if player_name:
            profiles[player_name] = {"ship": ship_idx, "progress": progress,
                                     "coins_q": coins_q, "upg": dict(upg), "lore": sorted(lore_seen), "pv": 2}
        with open(SAVE_PATH, "w") as f:
            json.dump({"last": player_name, "profiles": profiles, "settings": settings_dict()}, f)
    except Exception:
        pass


def load_profile(name):
    """Carga el progreso, monedas, mejoras y color del perfil 'name'."""
    global player_name, progress, coins_q
    d = profiles.get(name) or new_profile_data()
    player_name = name
    coins_q = max(0, int(d.get("coins_q", 0)))
    progress = max(0, min(TOTAL_NODES, int(d.get("progress", 0))))
    if int(d.get("pv", 1)) < 2:                 # guardado viejo: 5 niveles por sector -> convertir al nuevo reparto
        old = int(d.get("progress", 0))
        osec, on = divmod(old, 5)
        progress = TOTAL_NODES if osec >= SECTORS else min(TOTAL_NODES, SECTOR_START[osec] + min(on, SECTOR_LEVELS[osec]))
    saved = d.get("upg", {})
    for u in UPGRADES:
        upg[u["key"]] = max(0, min(len(u["cost"]), int(saved.get(u["key"], 0))))
    apply_ship_color(int(d.get("ship", 0)))
    global lore_seen
    if "lore" in d:
        lore_seen = set(str(x) for x in d.get("lore", []))
    else:                       # perfil de una versión anterior: no repetir lo que ya recorrió
        lore_seen = set()
        if progress > 0:
            lore_seen.add("intro")
            for s in range(SECTORS):
                if SECTOR_START[s] < progress:
                    lore_seen.add("s%d" % s)
                if SECTOR_START[s] + SECTOR_LEVELS[s] <= progress:
                    lore_seen.add("bp%d" % s)
                    lore_seen.add("bw%d" % s)
            if progress >= TOTAL_NODES:
                lore_seen.add("end")


def load_game():
    global profiles
    try:
        with open(SAVE_PATH) as f:
            d = json.load(f)
        if "profiles" in d:
            profiles = dict(d["profiles"])
            last = str(d.get("last", ""))
        else:                                   # partida guardada de versiones anteriores -> primer perfil
            last = str(d.get("name", ""))[:NAME_MAX] or "PILOTO"
            vg_old = bool(d.get("vg", False))
            profiles = {last: {"ship": 8 if vg_old else int(d.get("ship", 0)), "progress": d.get("progress", 0),
                               "coins_q": d.get("coins_q", 0), "upg": d.get("upg", {})}}
        if last:
            load_profile(last)
        settings_apply(d.get("settings", {}))
    except Exception:
        pass


def ui_ok(tag=None):
    """Anti-rebote: evita que un mismo toque (dedo + ratón sintético) se cuente dos veces."""
    global _last_ui, _last_tag
    t = pygame.time.get_ticks()
    if tag == _last_tag and t - _last_ui < 130:
        return False
    _last_ui, _last_tag = t, tag
    return True


def earn_coin(x, y):
    """+0.25 monedas por cada alien destruido (solo en el modo INFINITO)."""
    global coins_q, run_coins_q, coins_dirty
    if game_mode != "INFINITE":
        return
    coins_q += 1
    run_coins_q += 1
    coins_dirty = True
    coin_pops.append([x, y, 40])


def maybe_drop(x, y):
    """Un alien destruido a veces suelta un potenciador (poco frecuente)."""
    if len(powerups) < 2 and random.random() < 0.04:
        powerups.append(PowerUp(random.choice(("shield", "speed")), x, y))


# ---------- teclado en pantalla para el nombre ----------
KEY_ROWS = ["1234567890", "QWERTYUIOP", "ASDFGHJKLÑ", "ZXCVBNM"]


settings_return = "MENU"
lay_drag = None          # (nombre, id del dedo) del control que se está arrastrando
lay_off = (0, 0)


def open_settings():
    global game_state, settings_return
    release_all()
    settings_return = game_state
    game_state = "SETTINGS"
    sl_music.value, sl_sfx.value = music_vol, sfx_vol
    sl_alpha.value = (ctrl_alpha - 0.2) / 0.8
    if settings_return == "PAUSED":
        music_pause(False)                 # para poder oír el volumen mientras se ajusta
    play("click")


def close_settings():
    global game_state
    release_all()
    block_input()
    save_game()
    game_state = settings_return
    if settings_return == "PAUSED":
        music_pause(True)
    play("click")


def settings_touch(e_type, tid, tx, ty):
    global music_vol, sfx_vol, ctrl_alpha, game_state, lay_drag, cont_mode
    r = sl_music.process_event(e_type, tid, tx, ty)
    if r:
        music_vol = sl_music.value
        apply_music_volume()
        if r == 'release':
            save_game()
    r = sl_sfx.process_event(e_type, tid, tx, ty)
    if r:
        sfx_vol = sl_sfx.value
        apply_sfx_volume()
        if r == 'release':
            play("orb")
            save_game()
    r = sl_alpha.process_event(e_type, tid, tx, ty)
    if r:
        ctrl_alpha = 0.2 + 0.8 * sl_alpha.value
        if r == 'release':
            save_game()
    if btn_set_cont.process_event(e_type, tid, tx, ty) and e_type == 'down' and ui_ok("scont"):
        cont_mode = not cont_mode
        save_game()
        play("click")
    if btn_set_move.process_event(e_type, tid, tx, ty) and e_type == 'down' and ui_ok("smove"):
        release_all()
        lay_drag = None
        game_state = "LAYOUT"
        play("click")
    if btn_set_reset.process_event(e_type, tid, tx, ty) and e_type == 'down' and ui_ok("sreset"):
        reset_ctrl_layout()
        ctrl_alpha = 1.0
        sl_alpha.value = 1.0
        save_game()
        play("click")
    if btn_set_back.process_event(e_type, tid, tx, ty) and e_type == 'down' and ui_ok("sbk"):
        close_settings()


def draw_settings():
    draw_text(font_large, "AJUSTES", CYAN, WIDTH // 2, 4)
    sl_music.draw("%d%%" % round(music_vol * 100))
    sl_sfx.draw("%d%%" % round(sfx_vol * 100))
    sl_alpha.draw("%d%%" % round(ctrl_alpha * 100))
    preview_btn.rect.center = (sl_alpha.rect.right + 44, sl_alpha.rect.centery)
    draw_control(lambda: preview_btn.draw(canvas), preview_btn.rect)
    btn_set_cont.text = "CONTINUO: SI" if cont_mode else "CONTINUO: NO"
    btn_set_cont.draw(canvas)
    btn_set_move.draw(canvas)
    btn_set_reset.draw(canvas)
    btn_set_back.draw(canvas)


def layout_touch(e_type, tid, tx, ty):
    global lay_drag, lay_off, game_state
    done = btn_lay_done.process_event(e_type, tid, tx, ty)
    rst = btn_lay_reset.process_event(e_type, tid, tx, ty)
    if done and e_type == 'down' and ui_ok("ldone"):
        lay_drag = None
        save_game()
        game_state = "SETTINGS"
        play("click")
        return
    if rst and e_type == 'down' and ui_ok("lreset"):
        lay_drag = None
        reset_ctrl_layout()
        save_game()
        play("click")
        return
    if e_type == 'down' and lay_drag is None and not done and not rst:
        for n in reversed(CTRL_NAMES):
            if ctrl_hit(n, tx, ty):
                cx, cy = ctrl_center(n)
                lay_drag = (n, tid)
                lay_off = (cx - tx, cy - ty)
                break
    elif e_type == 'motion' and lay_drag is not None and lay_drag[1] == tid:
        ctrl_set(lay_drag[0], tx + lay_off[0], ty + lay_off[1])
    elif e_type == 'up' and lay_drag is not None and lay_drag[1] == tid:
        cx, cy = ctrl_center(lay_drag[0])
        ctrl_pos[lay_drag[0]] = (cx / float(WIDTH), cy / float(HEIGHT))
        lay_drag = None
        save_game()


def draw_layout():
    canvas.blit(dark_surf, (0, 0))
    draw_text(font_large, "MOVER CONTROLES", CYAN, WIDTH // 2, 4)
    draw_text(font_small, "Arrastra cada control hasta donde te acomode", LIGHT_GRAY, WIDTH // 2, int(HEIGHT * 0.14))
    for n in CTRL_NAMES:
        pygame.draw.rect(canvas, (70, 80, 110), ctrl_rect(n).inflate(8, 8), 1)
    draw_controls(0.6, True, 1.0, False)
    if lay_drag is not None:
        pygame.draw.rect(canvas, YELLOW, ctrl_rect(lay_drag[0]).inflate(12, 12), 2)
    btn_lay_reset.draw(canvas)
    btn_lay_done.draw(canvas)


def build_name_keys():
    keys = []
    kw = int(WIDTH * 0.072)
    gap = max(3, int(WIDTH * 0.007))
    kh = int(HEIGHT * 0.088)
    for r, row in enumerate(KEY_ROWS):
        items = [(ch, kw) for ch in row]
        if r == 3:
            items.append(("DEL", kw * 2 + gap))
        total = sum(w for _, w in items) + gap * (len(items) - 1)
        x = WIDTH // 2 - total // 2
        cy = int(HEIGHT * (0.395 + 0.1 * r))
        for ch, w in items:
            keys.append((ModernButton(x + w // 2, cy, w, kh, "BORRAR" if ch == "DEL" else ch), ch))
            x += w + gap
    return keys


name_keys = build_name_keys()


def open_name():
    global game_state, name_buf, del_confirm
    del_confirm = None
    name_buf = player_name
    release_all()
    for k, _ in name_keys:
        k.is_pressed = False
        k.touch_id = None
    game_state = "NAME"


def open_menu():
    global game_state
    release_all()
    block_input()
    game_state = "MENU"
    set_music("menu")
    pygame.time.set_timer(ENEMY_SPAWN, 0)


def open_shop():
    global game_state
    release_all()
    game_state = "SHOP"
    set_music("select")
    play("click")


def open_color():
    global game_state
    release_all()
    game_state = "COLOR"
    set_music("select")
    play("click")


def open_map():
    global game_state, map_sec
    release_all()
    map_sec = sec_of_progress(progress)
    game_state = "MAP"
    set_music("select")
    play("click")


def name_add(ch):
    global name_buf
    if ch == "DEL":
        name_buf = name_buf[:-1]
        play("click")
    elif len(name_buf) < NAME_MAX:
        name_buf += ch
        play("click")


def name_accept():
    name = name_buf.strip() or "PILOTO"
    save_game()                                  # guarda el perfil que se deja
    if name not in profiles:
        profiles[name] = new_profile_data()      # perfil nuevo: progreso desde cero
    load_profile(name)
    save_game()
    play("click")
    open_menu()


def profile_chips():
    names = list(profiles.keys())
    if player_name in names:
        names.remove(player_name)
        names.insert(0, player_name)
    names = names[:6]
    cw, ch, gap = int(WIDTH * 0.14), int(HEIGHT * 0.065), 6
    total = len(names) * cw + (len(names) - 1) * gap
    x = WIDTH // 2 - total // 2
    cy = int(HEIGHT * 0.785)
    out = []
    for n in names:
        out.append((n, pygame.Rect(x, cy - ch // 2, cw, ch)))
        x += cw + gap
    return out


del_confirm = None       # nombre del perfil pendiente de borrar (None = sin confirmación)


def ask_delete():
    """Pide confirmación para borrar el perfil seleccionado."""
    global del_confirm
    n = name_buf.strip()
    if n in profiles:
        del_confirm = n
        play("click")
    else:
        play("lock_off")


def delete_profile(name):
    """Borra el perfil 'name' con todo su progreso, monedas, mejoras y color."""
    global name_buf, del_confirm
    del_confirm = None
    profiles.pop(name, None)
    if name == player_name:
        rest = list(profiles.keys())
        load_profile(rest[0] if rest else "")      # otro perfil, o todo en blanco si no queda ninguno
    name_buf = ""
    save_game()
    play("explosion")


def name_key(event):
    global del_confirm
    if del_confirm is not None:
        if event.key == pygame.K_ESCAPE:
            del_confirm = None
        return
    if event.key == pygame.K_BACKSPACE:
        name_add("DEL")
    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        name_accept()
    else:
        ch = event.unicode.upper() if event.unicode else ""
        if len(ch) == 1 and ch.isalnum():
            name_add(ch)


def name_touch(e_type, tid, tx, ty):
    global name_buf, del_confirm
    if del_confirm is not None:                   # ventana de confirmación: solo responden SI / CANCELAR
        if btn_del_yes.process_event(e_type, tid, tx, ty) and e_type == 'down' and ui_ok("dyes"):
            delete_profile(del_confirm)
        elif btn_del_no.process_event(e_type, tid, tx, ty) and e_type == 'down' and ui_ok("dno"):
            del_confirm = None
            play("click")
        return
    if btn_name_del.process_event(e_type, tid, tx, ty) and e_type == 'down' and ui_ok("ndel"):
        ask_delete()
        return
    if e_type == 'down':
        for n, r in profile_chips():
            if r.collidepoint(tx, ty) and ui_ok(("chip", n)):
                name_buf = n
                play("click")
    for k, ch in name_keys:
        if k.process_event(e_type, tid, tx, ty) and e_type == 'down' and ui_ok(("key", ch)):
            name_add(ch)
    if btn_name_ok.process_event(e_type, tid, tx, ty) and e_type == 'down' and ui_ok("nok"):
        name_accept()


def draw_name():
    draw_text(font_large, "PERFIL DE PILOTO", CYAN, WIDTH // 2, int(HEIGHT * 0.03))
    bw, bh = int(WIDTH * 0.5), int(HEIGHT * 0.12)
    box = button_surface(bw, bh, False, (14, 18, 38), CYAN)
    rect = box.get_rect(center=(WIDTH // 2, int(HEIGHT * 0.235)))
    canvas.blit(box, rect)
    if name_buf:
        t = text_surf(font_large, name_buf, WHITE)
        x0 = rect.centerx - t.get_width() // 2
        canvas.blit(t, (x0, rect.centery - t.get_height() // 2))
        cx = x0 + t.get_width() + 2
    else:
        t = text_surf(font_medium, "ESCRIBE AQUI", (110, 116, 150))
        canvas.blit(t, t.get_rect(center=rect.center))
        cx = rect.centerx - t.get_width() // 2 - 4
    if (frame // 25) % 2 == 0 and len(name_buf) < NAME_MAX:
        pygame.draw.rect(canvas, CYAN, (cx, rect.centery - 11, 3, 22))
    for k, _ in name_keys:
        k.draw(canvas)
    for n, r in profile_chips():
        sel = (n == name_buf.strip())
        canvas.blit(button_surface(r.w, r.h, False, (0, 100, 130) if sel else (30, 38, 62),
                                   YELLOW if sel else (120, 130, 170)), r.topleft)
        t = text_surf(font_small, n, WHITE)
        canvas.blit(t, t.get_rect(center=r.center))
    btn_name_ok.draw(canvas)
    btn_name_del.draw(canvas)
    if del_confirm is not None:
        canvas.blit(dark_surf, (0, 0))
        draw_text(font_large, "¿BORRAR PERFIL?", RED, WIDTH // 2, int(HEIGHT * 0.22))
        draw_text(font_medium, del_confirm, WHITE, WIDTH // 2, int(HEIGHT * 0.36))
        draw_text(font_small, "Se perderán su progreso, monedas y mejoras.", LIGHT_GRAY, WIDTH // 2, int(HEIGHT * 0.46))
        draw_text(font_small, "Esta acción no se puede deshacer.", LIGHT_GRAY, WIDTH // 2, int(HEIGHT * 0.52))
        btn_del_yes.draw(canvas)
        btn_del_no.draw(canvas)


# ---------- tienda de potenciadores ----------
SHOP_ROW_H = int(HEIGHT * 0.115)
SHOP_GAP = int(HEIGHT * 0.018)
SHOP_ROWS = [pygame.Rect(WIDTH // 2 - int(WIDTH * 0.39), int(HEIGHT * 0.17) + i * (SHOP_ROW_H + SHOP_GAP),
                         int(WIDTH * 0.78), SHOP_ROW_H) for i in range(len(UPGRADES))]


def buy_upgrade(i):
    global coins_q
    u = UPGRADES[i]
    lv = upg[u["key"]]
    if lv >= len(u["cost"]):
        play("lock_off")
        return
    cq = int(u["cost"][lv] * 4)
    if coins_q < cq:
        play("lock_off")
        return
    coins_q -= cq
    upg[u["key"]] = lv + 1
    play("power")
    save_game()


def shop_touch(e_type, tid, tx, ty):
    if e_type == 'down':
        for i, r in enumerate(SHOP_ROWS):
            if r.collidepoint(tx, ty) and ui_ok(("shop", i)):
                buy_upgrade(i)
                break
    if btn_shop_back.process_event(e_type, tid, tx, ty) and e_type == 'down' and ui_ok("sback"):
        save_game()
        play("click")
        open_menu()


def draw_coins(right_x, y, big=False):
    """Saldo de monedas alineado a la derecha."""
    font = font_large if big else font_medium
    t = text_surf(font, coins_text(coins_q), YELLOW)
    ic = COIN_ICON_BIG if big else COIN_ICON
    x = right_x - t.get_width()
    canvas.blit(t, (x, y))
    canvas.blit(ic, (x - ic.get_width() - 4, y + (t.get_height() - ic.get_height()) // 2))


def draw_shop():
    draw_text(font_large, "TIENDA", YELLOW, WIDTH // 2, 4)
    draw_coins(WIDTH - 10, 8, True)
    draw_text(font_small, "Gana monedas en el modo INFINITO: cada alien = 0.25", LIGHT_GRAY, WIDTH // 2, int(HEIGHT * 0.118))
    for i, u in enumerate(UPGRADES):
        r = SHOP_ROWS[i]
        lv = upg[u["key"]]
        n = len(u["cost"])
        maxed = lv >= n
        cq = 0 if maxed else int(u["cost"][lv] * 4)
        can = (not maxed) and coins_q >= cq
        border = GREEN if maxed else (CYAN if can else (90, 90, 100))
        bg = (34, 44, 70) if (can or maxed) else (36, 36, 44)
        canvas.blit(button_surface(r.w, r.h, False, bg, border), r.topleft)
        ncol = WHITE if (can or maxed) else (150, 150, 160)
        canvas.blit(text_surf(font_medium, u["name"], ncol), (r.left + 14, r.top + 4))
        info = "Nv %d/%d  -  %s" % (lv, n, "COMPLETO" if maxed else u["desc"][lv])
        canvas.blit(text_surf(font_small, info, (170, 180, 205) if (can or maxed) else (120, 124, 140)),
                    (r.left + 14, r.bottom - font_small.get_height() - 5))
        if maxed:
            t = text_surf(font_medium, "MAX", GREEN)
            canvas.blit(t, (r.right - 14 - t.get_width(), r.centery - t.get_height() // 2))
        else:
            t = text_surf(font_medium, coins_text(cq), YELLOW if can else RED)
            x = r.right - 14 - t.get_width()
            canvas.blit(t, (x, r.centery - t.get_height() // 2))
            canvas.blit(COIN_ICON, (x - COIN_ICON.get_width() - 4, r.centery - COIN_ICON.get_height() // 2))
    btn_shop_back.draw(canvas)


# ---------- selector de color de nave + diseño especial ----------
def color_layout():
    sz = int(HEIGHT * 0.10)
    gap = int(HEIGHT * 0.028)
    n = len(SHIP_COLORS)
    total = n * sz + (n - 1) * gap
    x0 = WIDTH // 2 - total // 2
    cy = int(HEIGHT * 0.52)
    return [pygame.Rect(x0 + i * (sz + gap), cy - sz // 2, sz, sz) for i in range(n)]


SWATCHES = color_layout()


_vg_sw_cache = {}


def vg_swatch(w, h, k):
    """Mini cielo de Van Gogh: fondo azul, remolino de pinceladas, luna y estrella. k = cuadro de animación."""
    key = (w, h, k)
    s = _vg_sw_cache.get(key)
    if s is not None:
        return s
    s = pygame.Surface((w, h))
    for y in range(h):
        t = y / float(max(1, h - 1))
        pygame.draw.line(s, lerp_col((12, 26, 90), (48, 100, 176), t), (0, y), (w, y))
    cx, cy = int(w * 0.42), int(h * 0.55)
    cols = [(110, 165, 225), (244, 224, 120), (70, 125, 205), (250, 238, 160)]
    for i, rr in enumerate((4, 7, 10, 13)):
        a0 = k * 1.0472 * (1 if i % 2 == 0 else -1) + i * 1.3
        pygame.draw.arc(s, cols[i], (cx - rr, cy - rr, 2 * rr, 2 * rr), a0, a0 + 4.0, 2)
    pygame.draw.circle(s, (255, 250, 200), (cx, cy), 2 + (k % 2))
    mx, my = int(w * 0.80), int(h * 0.22)                 # luna creciente
    pygame.draw.circle(s, (250, 215, 80), (mx, my), 5)
    pygame.draw.circle(s, (30, 60, 140), (mx + 3, my - 1), 4)
    s = s.convert()
    _vg_sw_cache[key] = s
    return s


def color_touch(e_type, tid, tx, ty):
    if e_type == 'down':
        for i, r in enumerate(SWATCHES):
            if r.inflate(6, 6).collidepoint(tx, ty) and ui_ok(("sw", i)):
                apply_ship_color(i)
                play("click")
                save_game()
                break
    if btn_color_ok.process_event(e_type, tid, tx, ty) and e_type == 'down' and ui_ok("cok"):
        save_game()
        play("click")
        open_menu()


def draw_color():
    draw_text(font_large, "COLOR DE NAVE", CYAN, WIDTH // 2, 6)
    bob = int(math.sin(frame * 0.06) * 3)
    big = SHIP_BIG
    if vg_on:
        b0 = vg_ship_sprites()[(frame // 5) % 6][(frame // 4) % 2].base
        big = pygame.transform.scale(b0, (b0.get_width() * 3, b0.get_height() * 3))
        add_glow(canvas, WIDTH // 2, int(HEIGHT * 0.28) + bob, (250, 215, 90), 40, 0.4 + 0.1 * ((frame // 8) % 2), 1)
    canvas.blit(big, big.get_rect(center=(WIDTH // 2, int(HEIGHT * 0.28) + bob)))
    for i, r in enumerate(SWATCHES):
        nm, cb, cr, cc = SHIP_COLORS[i]
        sel = (i == ship_idx)
        if vg_on:                                         # la selección ondea cuando NOCHE ESTRELLADA está activa
            r = r.move(0, int(round(math.sin(frame * 0.06 + i * 0.8) * 2)))
        canvas.blit(button_surface(r.w, r.h, False, shade(cb, 0.9), YELLOW if sel else (150, 160, 190)), r)
        if i == VG_IDX:
            canvas.blit(vg_swatch(r.w - 8, r.h - 8, (frame // 8) % 6), (r.left + 4, r.top + 4))
            pygame.draw.rect(canvas, (12, 10, 30), (r.left + 3, r.top + 3, r.w - 6, r.h - 6), 1)
        else:
            pygame.draw.rect(canvas, cc, (r.centerx - 4, r.centery - 4, 8, 8))
            pygame.draw.rect(canvas, (12, 10, 30), (r.centerx - 4, r.centery - 4, 8, 8), 1)
        if sel:
            pygame.draw.rect(canvas, YELLOW, r.inflate(6, 6), 2)
    draw_text(font_medium, SHIP_COLORS[ship_idx][0], WHITE, WIDTH // 2, int(HEIGHT * 0.62))
    btn_color_ok.draw(canvas)


# ---------- mapa de niveles (estilo camino de PvZ 2) ----------
MAP_YS = (0.68, 0.47, 0.64, 0.44, 0.60)


def node_pos(i, L=None):
    if L is None:
        L = SECTOR_LEVELS[map_sec]
    x0, x1 = (0.15, 0.85) if L <= 5 else (0.10, 0.90)
    x = x0 + (x1 - x0) * (i / float(L - 1))
    y = MAP_YS[i % len(MAP_YS)]
    return int(WIDTH * x), int(HEIGHT * y)


def node_radius(i, L=None):
    if L is None:
        L = SECTOR_LEVELS[map_sec]
    return 20 if i == L - 1 else (13 if L > 7 else 15)


# =====================================================================================================
#  HISTORIA (LORE) del modo historia
# =====================================================================================================
LORE_INTRO = [
    "Hace mil años, la Guardia Estelar velaba por las ocho regiones de la galaxia. Fue una era de paz y de luz.",
    "Entonces despertó el Imperio Alien. En una sola noche cayeron las flotas, los puertos y los faros que guiaban a los viajeros.",
    "Su soberano, el Emperador Galáctico, se encerró en su trono y puso un guardián implacable en cada región para que nadie llegara hasta él.",
    "Solo queda una nave en pie. La tuya, {name}. Ya no hay refuerzos ni retirada: o vuelas, o la galaxia se apaga.",
]
LORE_SECTOR = [
    ["La Nebulosa Alfa fue el primer puerto de la Guardia. Hoy sus faros están apagados y un Centinela patrulla el paso: antes protegía este lugar, ahora obedece al Emperador."],
    ["El Cinturón Rojo, forja de las naves de la Guardia, arde sin descanso. Entre los asteroides acecha el Titán Escarlata, una máquina de guerra que nunca fue vencida."],
    ["En el corazón de una estrella moribunda late el Núcleo Estelar. Dicen que algo despertó allí dentro y que observa a través de cada alien que te ataca."],
    ["Más allá del Núcleo comienza el Abismo Glacial, un cementerio helado donde yacen las flotas caídas. El frío lo conserva todo... incluso a quienes aún vigilan."],
    ["La Colmena Verde devora mundos enteros. Su Reina no lucha por conquista, sino por hambre, y su zumbido ya se oye en tus sensores."],
    ["En el Vacío Oscuro no llega ninguna luz. Los exploradores que entraron jamás regresaron: algo los caza en la oscuridad, y ahora te ha olido."],
    ["Aquí está el secreto del Emperador: la Forja Solar, un reactor que alimenta a toda su flota. Si cae, su imperio perderá la fuerza. Y su guardián lo sabe."],
    ["El Trono Galáctico. Tras mil años de guerra solo queda una puerta entre tú y el Emperador. No hay camino de regreso. Que la galaxia recuerde tu nombre."],
]
LORE_BOSS_PRE = [
    ["\"Identificado: último piloto de la Guardia. Mi orden es clara. Ningún intruso cruzará la Nebulosa.\""],
    ["\"Mil naves vinieron por mí. Mil naves son hoy chatarra en mi cinturón. Tú serás la siguiente.\""],
    ["\"Te vi llegar mucho antes de que despegaras. Conozco cada disparo que harás... y ninguno te salvará.\""],
    ["\"Aquí el tiempo se detiene. Quédate. Duerme junto a los demás. El frío es otra forma de paz.\""],
    ["\"Mis hijos no conocen el miedo ni el cansancio. Ven, pequeña nave. Hay sitio de sobra en la colmena.\""],
    ["\"No puedes oírme, pero yo oigo tu corazón. En la oscuridad, la presa siempre se delata.\""],
    ["\"Potencia al máximo. Esta energía es la vida del Imperio. Intentar apagarla es un error fatal: el tuyo.\""],
    ["\"Mil años esperé a alguien que llegara hasta aquí. Eres tan terco como el último que cayó. Ven, {name}. Acabemos con esto.\""],
]
LORE_BOSS_WIN = [
    ["El Centinela se apaga y la Nebulosa vuelve a brillar. Los faros del primer puerto parpadean: la Guardia aún no ha muerto."],
    ["El Titán se desploma entre las llamas del Cinturón y las forjas dejan de rugir. Por primera vez en años hay silencio... y esperanza."],
    ["El Ojo se cierra. Del Núcleo escapa un último destello, como un suspiro. Quien lo dominaba ya no mira a través de él."],
    ["El hielo se resquebraja y las flotas dormidas parecen despertar. No estás solo en este abismo. Nunca lo estuviste."],
    ["La Reina calla y el zumbido cesa. Los mundos de la Colmena respiran de nuevo. Pero aún queda camino."],
    ["La oscuridad se disuelve. Una luz tenue baña el Vacío: alguien, muy lejos, ha encendido un faro para ti."],
    ["El reactor colapsa. La flota del Emperador pierde su fuerza y el miedo cruza su imperio. Solo queda su trono."],
    ["El Emperador cae. Su trono se apaga y, con él, la sombra que cubría la galaxia."],
]
LORE_END = [
    "El silencio vuelve a las ocho regiones. En cada puerto, uno a uno, los faros se encienden.",
    "Los guardianes ya no vigilan: descansan. Las flotas caídas no regresarán, pero su sacrificio no fue en vano.",
    "Nadie sabrá cuántos disparos hicieron falta. Solo que una nave, una sola, se negó a rendirse.",
    "Gracias, {name}. La galaxia recordará tu nombre.\n\nFIN",
]


def lore_scenes(kind, i=0):
    """Devuelve la escena (título, color, páginas) si ese fragmento aún no se mostró; si no, lista vacía."""
    key = kind if kind in ("intro", "end") else "%s%d" % (kind, i)
    if key in lore_seen:
        return []
    lore_seen.add(key)
    if kind == "intro":
        return [("PROLOGO", CYAN, LORE_INTRO)]
    if kind == "s":
        return [("SECTOR %d - %s" % (i + 1, SECTOR_NAMES[i]), SECTOR_COLORS[i], LORE_SECTOR[i])]
    if kind == "bp":
        return [(BOSS_NAMES[i + 1], (255, 90, 90), LORE_BOSS_PRE[i])]
    if kind == "bw":
        return [(BOSS_NAMES[i + 1] + " DERROTADO", GREEN, LORE_BOSS_WIN[i])]
    return [("EPILOGO", YELLOW, LORE_END)]


story_scenes = []
story_si = 0
story_pi = 0
story_t = 0.0
story_then = None
_wrap_cache = {}


def wrap_text(font, text, maxw):
    key = (id(font), text, maxw)
    r = _wrap_cache.get(key)
    if r is None:
        r = []
        for para in text.split("\n"):
            cur = ""
            for w in para.split(" "):
                t = (cur + " " + w).strip()
                if font.size(t)[0] <= maxw or not cur:
                    cur = t
                else:
                    r.append(cur)
                    cur = w
            r.append(cur)
        _wrap_cache[key] = r
    return r


def story_text():
    t = story_scenes[story_si][2][story_pi]
    return t.replace("{name}", player_name or "PILOTO")


def run_story(scenes, then):
    """Muestra una o varias escenas de historia y al terminar (o al saltarlas) llama a then()."""
    global game_state, story_scenes, story_si, story_pi, story_t, story_then
    story_scenes, story_si, story_pi, story_t, story_then = scenes, 0, 0, 0.0, then
    release_all()
    block_input()
    pygame.time.set_timer(ENEMY_SPAWN, 0)
    set_music("select")
    game_state = "STORY"


def story_finish():
    global story_then
    then, story_then = story_then, None
    release_all()
    block_input()
    if then is not None:
        then()


def story_advance():
    global story_si, story_pi, story_t
    if story_si >= len(story_scenes):
        return
    if int(story_t * 1.3) < len(story_text()):     # primero se completa el texto que está apareciendo
        story_t = 1e6
        return
    story_pi += 1
    story_t = 0.0
    play("click")
    if story_pi >= len(story_scenes[story_si][2]):
        story_si += 1
        story_pi = 0
        if story_si >= len(story_scenes):
            story_finish()


def story_touch(e_type, tid, tx, ty):
    if game_state != "STORY":
        return
    if btn_story_skip.process_event(e_type, tid, tx, ty) and e_type == 'down' and ui_ok("sskip"):
        story_finish()
        return
    if e_type == 'down' and not btn_story_skip.rect.inflate(14, 14).collidepoint(tx, ty) and ui_ok("story"):
        story_advance()


def draw_story():
    global story_t
    if game_state != "STORY" or story_si >= len(story_scenes):
        return
    title, col, pages = story_scenes[story_si]
    text = story_text()
    story_t += 1
    canvas.blit(dark_surf, (0, 0))
    tf = font_large if font_large.size(title)[0] < WIDTH * 0.9 else font_medium
    ty0 = int(HEIGHT * 0.09)
    draw_text(tf, title, col, WIDTH // 2, ty0)
    ly = ty0 + tf.get_height() + 6
    pygame.draw.line(canvas, col, (int(WIDTH * 0.2), ly), (int(WIDTH * 0.8), ly), 2)
    lines = wrap_text(font_medium, text, int(WIDTH * 0.78))
    n = int(story_t * 1.3)
    x0, y, lh = int(WIDTH * 0.11), int(HEIGHT * 0.31), font_medium.get_height() + 6
    shown = 0
    for ln in lines:
        if shown >= n:
            break
        part = ln[:max(0, n - shown)]
        shown += len(ln) + 1
        if part:
            canvas.blit(text_surf(font_medium, part, (236, 240, 255)), (x0, y))
        y += lh
    if n >= len(text) and (pygame.time.get_ticks() // 450) % 2 == 0:
        draw_text(font_small, "toca para continuar", LIGHT_GRAY, WIDTH // 2, int(HEIGHT * 0.90))
    for k in range(len(pages)):
        pygame.draw.circle(canvas, col if k == story_pi else (70, 74, 100),
                           (int(WIDTH // 2 + (k - (len(pages) - 1) / 2.0) * 12), int(HEIGHT * 0.84)), 3)
    btn_story_skip.draw(canvas)


def begin_node(g):
    """Entrar a un nivel del mapa: si es la primera vez, se muestra antes el prólogo / el texto del sector."""
    sec, n = node_sec(g)
    scenes = []
    if g == 0:
        scenes += lore_scenes("intro")
    if n == 0:
        scenes += lore_scenes("s", sec)
    if scenes:
        save_game()
        run_story(scenes, lambda: reset_game("LEVELS", g))
    else:
        reset_game("LEVELS", g)


def finish_node():
    """Se terminó el nodo actual del mapa (nivel o nivel + boss)."""
    global progress
    if current_node == progress and progress < TOTAL_NODES:
        progress += 1
    sec, n = node_sec(current_node)
    last = current_node >= TOTAL_NODES - 1
    scenes = []
    if n == SECTOR_LEVELS[sec] - 1:                  # acaba de caer el boss del sector
        scenes += lore_scenes("bw", sec)
        if last:
            scenes += lore_scenes("end")
    save_game()
    pygame.time.set_timer(ENEMY_SPAWN, 0)

    def _after():
        global game_state
        global fade_in_t
        if last:
            game_state = "VICTORY"
            set_music(None)
            play("victory")
        elif cont_mode:                             # CONTINUO: directo al siguiente nivel
            fade_in_t = 30
            begin_node(current_node + 1)
        else:
            open_map()
    if scenes:
        run_story(scenes, _after)
    else:
        _after()


def map_touch(e_type, tid, tx, ty):
    global map_sec
    if btn_map_prev.process_event(e_type, tid, tx, ty) and e_type == 'down' and ui_ok("prev"):
        if map_sec > 0:
            map_sec -= 1
            play("click")
    if btn_map_next.process_event(e_type, tid, tx, ty) and e_type == 'down' and ui_ok("next"):
        if map_sec < SECTORS - 1:
            map_sec += 1
            play("click")
    if btn_map_back.process_event(e_type, tid, tx, ty) and e_type == 'down' and ui_ok("back"):
        play("click")
        open_menu()
        return
    if e_type == 'down':
        for i in range(SECTOR_LEVELS[map_sec]):
            nx, ny = node_pos(i)
            if math.hypot(tx - nx, ty - ny) <= node_radius(i) + 8 and ui_ok(("node", map_sec, i)):
                g = node_g(map_sec, i)
                if g <= progress:
                    begin_node(g)
                else:
                    play("lock_off")
                break


def draw_map():
    acc = SECTOR_COLORS[map_sec]
    base = SECTOR_START[map_sec]
    LV = SECTOR_LEVELS[map_sec]
    draw_text(font_large, "SECTOR %d" % (map_sec + 1), acc, WIDTH // 2, 4)
    draw_text(font_medium, SECTOR_NAMES[map_sec], WHITE, WIDTH // 2, 40)
    for i in range(SECTORS):
        pygame.draw.circle(canvas, acc if i == map_sec else (60, 64, 90), (int(WIDTH // 2 + (i - (SECTORS - 1) / 2.0) * 14), 70), 4 if i == map_sec else 3)
    draw_text(font_medium, player_name or "PILOTO", LIGHT_GRAY, int(WIDTH * 0.14), 8)

    # camino
    for i in range(LV - 1):
        x0, y0 = node_pos(i)
        x1, y1 = node_pos(i + 1)
        done = base + i < progress
        pts = []
        for k in range(17):
            t = k / 16.0
            sm = t * t * (3 - 2 * t)
            pts.append((int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * sm)))
        pygame.draw.lines(canvas, (10, 10, 26), False, pts, 11)
        pygame.draw.lines(canvas, shade(acc, 0.5) if done else (50, 54, 82), False, pts, 7)
        for k in range(1, 16, 2):
            pygame.draw.rect(canvas, acc if done else (86, 92, 128), (pts[k][0] - 1, pts[k][1] - 1, 3, 3))

    # nodos
    for i in range(LV):
        x, y = node_pos(i)
        r = node_radius(i)
        g = base + i
        boss_node = (i == LV - 1)
        if g < progress:
            fill, rim = ((170, 50, 70), (255, 140, 150)) if boss_node else ((40, 170, 70), (150, 255, 170))
        elif g == progress:
            fill, rim = ((190, 40, 60), (255, 120, 130)) if boss_node else (shade(acc, 0.55), acc)
        else:
            fill, rim = (46, 50, 74), (100, 106, 140)
        d = dome_surface(r, fill, rim)
        canvas.blit(d, d.get_rect(center=(x, y)))
        if g == progress:
            pygame.draw.circle(canvas, acc, (x, y), r + 3 + (frame // 10) % 3, 1)
        if g < progress:                                   # completado: palomita
            pygame.draw.lines(canvas, WHITE, False, [(x - 6, y), (x - 2, y + 5), (x + 7, y - 6)], 3)
        elif g == progress:                                # actual: número
            t = text_surf(font_medium, str(i + 1), WHITE)
            canvas.blit(t, t.get_rect(center=(x, y)))
        else:                                              # bloqueado: candado
            pygame.draw.rect(canvas, (150, 156, 184), (x - 5, y - 1, 10, 8))
            pygame.draw.arc(canvas, (150, 156, 184), (x - 4, y - 8, 8, 10), 0, 3.1416, 2)
            pygame.draw.rect(canvas, (40, 44, 64), (x - 1, y + 2, 2, 3))
        if boss_node:
            bi = BOSS_ICONS[map_sec]
            canvas.blit(bi, bi.get_rect(center=(x, y - r - 18 + int(math.sin(frame * 0.07) * 2))))

    # nave sobre el nodo actual
    ci = progress - base
    if 0 <= ci < LV:
        x, y = node_pos(ci)
        bob = int(math.sin(frame * 0.1) * 3)
        if ci == LV - 1:
            canvas.blit(SHIP_ICON, SHIP_ICON.get_rect(center=(x - 36, y + bob)))
        else:
            canvas.blit(SHIP_ICON, SHIP_ICON.get_rect(center=(x, y - node_radius(ci) - 16 + bob)))
    if base > progress:
        draw_text(font_medium, "BLOQUEADO", (170, 170, 190), WIDTH // 2, int(HEIGHT * 0.82))
    draw_text(font_medium, "%d/%d" % (min(progress, TOTAL_NODES), TOTAL_NODES), LIGHT_GRAY, int(WIDTH * 0.86), int(HEIGHT * 0.9))
    if map_sec > 0:
        btn_map_prev.draw(canvas)
    if map_sec < SECTORS - 1:
        btn_map_next.draw(canvas)
    btn_map_back.draw(canvas)


load_game()
apply_ctrl_layout()
apply_sfx_volume()
apply_music_volume()
name_buf = player_name


def present():
    global shake_t
    update_view()
    vx, vy, vw, vh = VIEW
    if shake_t > 0:
        amp = min(5, 1 + shake_t // 3)
        k = vw / float(WIDTH)
        ox = int(random.randint(-amp, amp) * k)
        oy = int(random.randint(-amp, amp) * k)
        shake_t -= 1
        screen.fill((0, 0, 0))
        screen.blit(pygame.transform.scale(canvas, (vw, vh)), (vx + ox, vy + oy))
        pygame.display.flip()
        return
    try:
        if vw == SW and vh == SH:
            pygame.transform.scale(canvas, (vw, vh), screen)
        else:
            screen.fill((0, 0, 0))
            pygame.transform.scale(canvas, (vw, vh), screen.subsurface((vx, vy, vw, vh)))
    except Exception:
        screen.fill((0, 0, 0))
        screen.blit(pygame.transform.scale(canvas, (vw, vh)), (vx, vy))
    pygame.display.flip()


# =====================================================================
#  BUCLE PRINCIPAL
# =====================================================================
_ld(0.97, "Casi listo")
set_music("menu")
menu_demo = MenuDemo()
_ld_done()
running = True
_bad_fps = 0
while running:
    frame += 1
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == ENEMY_SPAWN and game_state == "PLAYING":
            if game_mode == "INFINITE":
                if len(enemies) < 5 and boss is None:
                    enemies.append(Enemy(player.x, player.y))
            elif stage is not None and stage["type"] == "level":
                if level_spawned < stage["total"] and len(enemies) < stage["on_screen"]:
                    enemies.append(Enemy(player.x, player.y, stage["speed"], None, stage["shoot"]))
                    level_spawned += 1

        elif event.type == LIFE_SPAWN and game_state == "PLAYING":
            lives_list.append(LifePickup())

        elif event.type == POWER_SPAWN and game_state == "PLAYING":
            if not powerups and random.random() < 0.7:          # de vez en cuando
                powerups.append(PowerUp(random.choice(("shield", "speed"))))

        elif event.type == pygame.KEYDOWN and game_state == "NAME":
            name_key(event)

        elif event.type in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP,
                            pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP):

            if hasattr(event, 'finger_id'):
                tx, ty = view_to_canvas(event.x * SW, event.y * SH)
                tid = event.finger_id
                e_type = 'down' if event.type == pygame.FINGERDOWN else 'up' if event.type == pygame.FINGERUP else 'motion'
            else:
                tx, ty = view_to_canvas(event.pos[0], event.pos[1])
                tid = 'mouse'
                e_type = 'down' if event.type == pygame.MOUSEBUTTONDOWN else 'up' if event.type == pygame.MOUSEBUTTONUP else 'motion'
                if e_type == 'motion' and not pygame.mouse.get_pressed()[0]:
                    continue

            # el mismo toque llega como dedo + ratón sintético: el 2º caía sobre el botón HISTORIA del menú
            if e_type == 'down' and pygame.time.get_ticks() < input_block_until:
                continue

            if game_state == "NAME":
                name_touch(e_type, tid, tx, ty)

            elif game_state == "MENU":
                if btn_infinite.process_event(e_type, tid, tx, ty) and e_type == 'down':
                    reset_game("INFINITE")
                elif btn_levels.process_event(e_type, tid, tx, ty) and e_type == 'down':
                    open_map()
                elif btn_shop.process_event(e_type, tid, tx, ty) and e_type == 'down':
                    open_shop()
                elif btn_color.process_event(e_type, tid, tx, ty) and e_type == 'down':
                    open_color()
                elif btn_rename.process_event(e_type, tid, tx, ty) and e_type == 'down':
                    play("click")
                    open_name()
                elif btn_gear.process_event(e_type, tid, tx, ty) and e_type == 'down' and ui_ok("gear"):
                    open_settings()

            elif game_state == "COLOR":
                color_touch(e_type, tid, tx, ty)

            elif game_state == "SHOP":
                shop_touch(e_type, tid, tx, ty)

            elif game_state == "MAP":
                map_touch(e_type, tid, tx, ty)

            elif game_state == "SETTINGS":
                settings_touch(e_type, tid, tx, ty)

            elif game_state == "STORY":
                story_touch(e_type, tid, tx, ty)

            elif game_state == "LAYOUT":
                layout_touch(e_type, tid, tx, ty)

            elif game_state == "PLAYING":
                joystick.process_event(e_type, tid, tx, ty)
                shoot_btn.process_event(e_type, tid, tx, ty)
                nuke_btn.process_event(e_type, tid, tx, ty)
                if dash_btn.process_event(e_type, tid, tx, ty) and e_type == 'down':
                    player.start_dash(joystick.vector)
                if lock_btn.process_event(e_type, tid, tx, ty) and e_type == 'down':
                    aim_lock = not aim_lock
                    play("lock_on" if aim_lock else "lock_off")
                if pause_btn.process_event(e_type, tid, tx, ty) and e_type == 'down':
                    game_state = "PAUSED"
                    release_all()
                    music_pause(True)
                    play("click")

            elif game_state == "PAUSED":
                if btn_resume.process_event(e_type, tid, tx, ty) and e_type == 'down':
                    game_state = "PLAYING"
                    release_all()
                    music_pause(False)
                    play("click")
                elif btn_menu.process_event(e_type, tid, tx, ty) and e_type == 'down':
                    game_state = "MENU"
                    release_all()
                    block_input()
                    music_pause(False)
                    set_music("menu")
                    pygame.time.set_timer(ENEMY_SPAWN, 0)
                    play("click")
                    save_game()
                elif btn_gear.process_event(e_type, tid, tx, ty) and e_type == 'down' and ui_ok("gearp"):
                    open_settings()

            elif game_state in ("GAMEOVER", "VICTORY"):
                if game_state == "GAMEOVER" and game_mode == "LEVELS" and \
                        btn_retry.process_event(e_type, tid, tx, ty) and e_type == 'down':
                    reset_game("LEVELS", current_node)
                elif btn_menu_end.process_event(e_type, tid, tx, ty) and e_type == 'down':
                    play("click")
                    open_menu()

    # --- CALIDAD AUTOMÁTICA: si los FPS caen varias veces seguidas, se quitan brillos y partículas ---
    if game_state == "PLAYING" and frame % 60 == 0 and frame > 240:
        _fps = clock.get_fps()
        if _fps and _fps < 46:
            _bad_fps += 1
            if _bad_fps >= 3 and QUALITY > 0:
                QUALITY -= 1
                _bad_fps = 0
        else:
            _bad_fps = 0
    if QUALITY < 2 and len(particles) > (70 if QUALITY == 0 else 110):
        del particles[:len(particles) - (70 if QUALITY == 0 else 110)]

    # --- LÓGICA ---
    if random.random() < 0.02 and game_state != "PAUSED" and len(comets) < (0, 3, 6)[QUALITY]:
        comets.append(Comet())

    if game_state == "MENU":
        menu_time += 0.02
        for _ in range(DEMO_STEPS):
            menu_demo.update()

    if flash_timer > 0:
        flash_timer -= 1

    if game_state == "PLAYING":
        player.update(joystick.vector, particles)

        # Modo INFINITO: boss al azar cada 50 puntos
        if game_mode == "INFINITE":
            if boss is None and score >= inf_next_boss:
                start_infinite_boss()
            elif boss is not None and boss.finished:
                end_infinite_boss()

        # ¿Terminó el nivel? -> solo cuando YA salieron todos los enemigos y TODOS están muertos
        if game_mode == "LEVELS" and stage is not None:
            if stage["type"] == "level":
                stage_done = level_spawned >= stage["total"] and not enemies
            else:
                stage_done = boss is not None and boss.finished
            if stage_done:
                if stage["type"] == "boss":
                    transition_msg = "¡BOSS DERROTADO!"
                    player.lives = min(max_lives(), player.lives + 1)   # premio por vencer al boss
                elif stage_idx + 1 < len(stages):
                    transition_msg = "¡PARTE %d COMPLETADA!" % stage.get("part", 1)
                else:
                    transition_msg = "¡NIVEL COMPLETADO!"
                game_state = "TRANSITION"
                transition_timer = 150
                enemies.clear()
                projectiles.clear()
                orbs.clear()
                lives_list.clear()
                powerups.clear()
                enemy_bullets.clear()
                boss = None
                player.invul_timer = 150
                release_all()
                play("level_done")

        # Onda expansiva
        if game_state == "PLAYING" and nuke_btn.is_pressed and player.nuke_xp >= player.max_nuke_xp and not wave_active:
            player.nuke_xp = 0
            wave_active = True
            wave_radius = 10.0
            for e in enemies:
                score += 1
                level_cleared += 1
                earn_coin(e.x, e.y)
                fx_boom(e.x, e.y, 0.8)
                for _ in range(8):
                    if len(particles) < 160:
                        particles.append(Particle(e.x, e.y, random.uniform(-1.6, 1.6), random.uniform(-1.6, 1.6), True))
            enemies.clear()
            enemy_bullets.clear()
            if boss is not None and boss.state == "FIGHT" and not boss.ghost:
                boss.hp -= max(6, int(boss.max_hp * 0.12))   # la onda también daña al boss
                boss.hit_flash = 8
            nuke_btn.is_pressed = False
            add_shake(14)
            play("nuke")

        if wave_active:
            wave_radius += HEIGHT * 0.04
            if wave_radius > max(WIDTH, HEIGHT) * 1.2:
                wave_active = False

        for p in particles:
            p.update()
        particles[:] = [p for p in particles if p.life > 0]
        for cp in coin_pops:
            cp[1] -= 0.5
            cp[2] -= 1
        coin_pops[:] = [cp for cp in coin_pops if cp[2] > 0]
        update_fx()
        if coins_dirty and frame % 300 == 0:
            save_game()

        if shoot_cooldown > 0:
            shoot_cooldown -= 1

        target = find_target() if aim_lock else None
        lock_target = target
        player.aim_active = target is not None
        if target is not None:
            player.aim_dir = aim_at(target)

        if (target is not None or shoot_btn.is_pressed) and shoot_cooldown == 0:
            fire_dir = player.aim_dir if target is not None else player.last_dir
            projectiles.append(Projectile(player.rect.centerx, player.rect.centery, fire_dir))
            shoot_cooldown = fire_cd()
            play("shoot")

        for p in projectiles:
            p.update()
        projectiles[:] = [p for p in projectiles if not p.is_off_screen()]

        for lp in lives_list[:]:
            lp.update()
            if lp.is_off_screen():
                lives_list.remove(lp)
            elif player.rect.colliderect(lp.rect):
                if player.lives < max_lives():
                    player.lives += 1
                lives_list.remove(lp)
                play("heart")

        for pu in powerups[:]:
            pu.update()
            if pu.is_off_screen():
                powerups.remove(pu)
            elif player.rect.colliderect(pu.rect):
                powerups.remove(pu)
                if pu.kind == "shield":
                    player.shield = True
                else:
                    player.boost_timer = BOOST_FRAMES
                play("power")
                for _ in range(10):
                    if len(particles) < 200:
                        particles.append(Particle(pu.x, pu.y, random.uniform(-1.8, 1.8), random.uniform(-1.8, 1.8), True))

        for orb in orbs[:]:
            orb.update(player.x, player.y)
            if player.rect.colliderect(orb.rect):
                if player.nuke_xp < player.max_nuke_xp:
                    player.nuke_xp += 1
                    play("ready" if player.nuke_xp >= player.max_nuke_xp else "orb")
                orbs.remove(orb)

        # Enemigos y colisiones
        for e in enemies[:]:
            if game_state != "PLAYING":
                break
            if e.update(player.x, player.y):          # alien armado: dispara hacia la nave
                enemy_bullets.append(EnemyBullet(e.x, e.y, math.atan2(player.y - e.y, player.x - e.x), HEIGHT * 0.0055))
                play("boss_shot")

            if player.dash_timer > 0 and player.rect.inflate(8, 8).colliderect(e.rect):
                enemies.remove(e)
                score += 1
                level_cleared += 1
                orbs.append(XPOrb(e.x, e.y))
                maybe_drop(e.x, e.y)
                earn_coin(e.x, e.y)
                fx_boom(e.x, e.y)
                play("explosion")
                for _ in range(8):
                    if len(particles) < 160:
                        particles.append(Particle(e.x, e.y, random.uniform(-1.6, 1.6), random.uniform(-1.6, 1.6), True))
                continue

            if player.rect.colliderect(e.rect) and player.invul_timer == 0:
                enemies.remove(e)
                level_cleared += 1      # un alien que se estrella también cuenta como eliminado
                fx_boom(e.x, e.y, 0.7)
                for _ in range(6):
                    if len(particles) < 160:
                        particles.append(Particle(e.x, e.y, random.uniform(-1.4, 1.4), random.uniform(-1.4, 1.4), True))
                hurt_player()
                continue  # (fix) un enemigo ya eliminado no puede dar puntos

            for p in projectiles:
                if p.rect.colliderect(e.rect):
                    enemies.remove(e)
                    projectiles.remove(p)

                    score += 1
                    level_cleared += 1
                    orbs.append(XPOrb(e.x, e.y))
                    maybe_drop(e.x, e.y)
                    earn_coin(e.x, e.y)
                    fx_boom(e.x, e.y)
                    play("explosion")

                    if game_mode == "INFINITE":
                        pygame.time.set_timer(ENEMY_SPAWN, random.randint(200, 600))

                    for _ in range(8):
                        if len(particles) < 160:
                            particles.append(Particle(e.x, e.y, random.uniform(-1.2, 1.2), random.uniform(-1.2, 1.2), True))
                    break

        # --- BOSS y sus balas ---
        if game_state == "PLAYING" and boss is not None:
            boss.update(player.x, player.y, enemy_bullets, enemies, particles)

            if boss.state == "FIGHT":
                for p in projectiles[:]:
                    if not boss.ghost and p.rect.colliderect(boss.hit_rect):
                        projectiles.remove(p)
                        boss.hp -= 1
                        boss.hit_flash = 3
                        boss.hits += 1
                        play("boss_hit")
                        for _ in range(3):
                            if len(particles) < 160:
                                particles.append(Particle(p.x, p.y, random.uniform(-1.5, 1.5), random.uniform(-1.5, 1.5), True))
                        if boss.hits % 6 == 0:      # cada tanto suelta energía para cargar la onda
                            orbs.append(XPOrb(boss.x + random.uniform(-20, 20), boss.y + 30))

                if not boss.ghost and player.dash_timer > 0 and not player.dash_hit_boss and player.rect.colliderect(boss.hit_rect):
                    player.dash_hit_boss = True          # la embestida golpea al boss una vez
                    boss.hp -= DASH_BOSS_DAMAGE
                    boss.hit_flash = 8
                    play("boss_hit")
                    for _ in range(10):
                        if len(particles) < 160:
                            particles.append(Particle(player.x, player.y, random.uniform(-2, 2), random.uniform(-2, 2), True))

                if boss.hp <= 0:
                    boss.state = "DYING"
                    boss.dying = 110
                    score += 100 * boss.idx
                    enemy_bullets.clear()
                    for e in enemies:
                        for _ in range(8):
                            particles.append(Particle(e.x, e.y, random.uniform(-1.6, 1.6), random.uniform(-1.6, 1.6), True))
                    enemies.clear()
                    player.invul_timer = max(player.invul_timer, 200)
                    set_music(None)
                    play("boss_die")
                    add_shake(32)
                    fx_boom(boss.x, boss.y, 3.0)
                elif player.invul_timer == 0 and not boss.ghost and player.rect.colliderect(boss.hit_rect):
                    hurt_player()

        # lasers del boss 3
        if game_state == "PLAYING" and boss is not None and boss.state == "FIGHT" and player.invul_timer == 0 \
                and boss.beam_hit(player.rect):
            hurt_player()

        for b in enemy_bullets[:]:
            if game_state != "PLAYING":
                break
            b.update()
            if b.is_off_screen():
                enemy_bullets.remove(b)
            elif player.invul_timer == 0 and player.rect.inflate(-14, -14).colliderect(b.rect):
                enemy_bullets.remove(b)
                for _ in range(5):
                    if len(particles) < 160:
                        particles.append(Particle(b.x, b.y, random.uniform(-1.4, 1.4), random.uniform(-1.4, 1.4), True))
                hurt_player()

    elif game_state == "TRANSITION":
        transition_timer -= 1
        player.update([0, 0], particles, force_center=True)
        for p in particles:
            p.update()
        particles[:] = [p for p in particles if p.life > 0]

        if transition_timer <= 0:
            if game_mode == "LEVELS" and stage_idx + 1 < len(stages):
                start_stage(stage_idx + 1)
                if game_state != "STORY":
                    game_state = "PLAYING"
            else:
                finish_node()

    # --- DIBUJADO (todo sobre el canvas de baja resolución) ---
    if vg_on:
        draw_vg_sky()
    else:
        canvas.blit(bg_game, (0, 0))

    speed_mult = 15 if game_state == "TRANSITION" else (0 if game_state == "PAUSED" else 1)

    for s in stars:
        s[1] += s[2] * speed_mult
        if s[1] > HEIGHT:
            s[1] = 0
            s[0] = random.uniform(0, WIDTH)
        cols = STAR_COLS_VG if vg_on else STAR_COLS
        col = cols[s[4]]
        if s[4] == 2 and (frame // 10 + s[5]) % 4 == 0:
            col = cols[1]
        if speed_mult > 1:
            pygame.draw.line(canvas, col, (int(s[0]), int(s[1])), (int(s[0]), int(s[1] - s[2] * speed_mult * 2)))
        else:
            pygame.draw.rect(canvas, col, (int(s[0]), int(s[1]), s[3], s[3]))
            if s[4] == 2 and QUALITY >= 1 and (frame // 10 + s[5]) % 4 == 0:      # destello en cruz
                sx_, sy_ = int(s[0]), int(s[1])
                pygame.draw.line(canvas, cols[1], (sx_ - 3, sy_), (sx_ + 4, sy_))
                pygame.draw.line(canvas, cols[1], (sx_, sy_ - 3), (sx_, sy_ + 4))

    for c in comets[:]:
        c.update(speed_mult)
        c.draw(canvas)
        if c.y > HEIGHT + 40 or c.x < -40 or c.x > WIDTH + 40:
            comets.remove(c)

    if game_state == "NAME":
        draw_name()

    elif game_state == "COLOR":
        draw_color()

    elif game_state == "SHOP":
        draw_shop()

    elif game_state == "MAP":
        draw_map()

    elif game_state == "SETTINGS":
        draw_settings()

    elif game_state == "STORY":
        draw_story()

    elif game_state == "LAYOUT":
        draw_layout()

    elif game_state == "MENU":
        if vg_on:
            canvas.blit(vg_hills, (0, HEIGHT - vg_hills.get_height()))
        else:
            canvas.blit(planet_surf, (0, _planet_top))

        menu_demo.draw(canvas)
        bob = int(math.sin(menu_time * 3) * 3)
        tcol = ((255, 248, 180), (255, 160, 40)) if vg_on else ((210, 255, 255), (0, 140, 255))
        t_bottom = draw_title(font_title, "ATTACK ON THE ALIENS", tcol[0], tcol[1], WIDTH // 2, int(HEIGHT * 0.12) + bob)
        draw_text(font_medium, "PILOTO: %s" % (player_name or "PILOTO"), LIGHT_GRAY, WIDTH // 2, t_bottom - 2 - bob)

        btn_infinite.draw(canvas)
        btn_levels.draw(canvas)
        btn_shop.draw(canvas)
        btn_rename.draw(canvas)
        draw_gear_button()
        oc = btn_color.rect.center
        canvas.blit(COLOR_ORB, COLOR_ORB.get_rect(center=oc))
        pygame.draw.circle(canvas, WHITE, oc, 16 + (frame // 20) % 2, 1)
        draw_coins(btn_color.rect.left - 8, 16)

    elif game_state in ("PLAYING", "TRANSITION", "PAUSED"):
        for p in particles:
            p.draw(canvas)

        if wave_active:
            wr = int(wave_radius)
            pygame.draw.circle(canvas, (0, 50, 80), (int(player.x), int(player.y)), wr + 6, 4)
            pygame.draw.circle(canvas, (0, 120, 170), (int(player.x), int(player.y)), wr, 7)
            pygame.draw.circle(canvas, CYAN, (int(player.x), int(player.y)), wr - 1, 4)
            pygame.draw.circle(canvas, WHITE, (int(player.x), int(player.y)), wr - 2, 1)

        for lp in lives_list:
            lp.draw(canvas)
        for orb in orbs:
            orb.draw(canvas)
        for pu in powerups:
            pu.draw(canvas)
        for p in projectiles:
            p.draw(canvas)
        for e in enemies:
            e.draw(canvas)
        for cp in coin_pops:
            canvas.blit(text_surf(font_small, "+0.25", YELLOW), (int(cp[0]) - 14, int(cp[1]) - 8))
        if boss is not None:
            boss.draw(canvas)
        for b in enemy_bullets:
            b.draw(canvas)
        draw_fx(canvas)

        player.draw(canvas)

        # mira sobre el objetivo fijado
        if aim_lock and lock_target is not None and game_state in ("PLAYING", "PAUSED"):
            rr = (lock_target.hit_rect if lock_target is boss else lock_target.rect).inflate(8, 8)
            mc = RED if (frame // 6) % 2 == 0 else YELLOW
            for cx_, cy_, sx, sy in ((rr.left, rr.top, 1, 1), (rr.right, rr.top, -1, 1),
                                     (rr.left, rr.bottom, 1, -1), (rr.right, rr.bottom, -1, -1)):
                pygame.draw.line(canvas, mc, (cx_, cy_), (cx_ + sx * 6, cy_), 2)
                pygame.draw.line(canvas, mc, (cx_, cy_), (cx_, cy_ + sy * 6), 2)

        for i in range(player.lives):
            canvas.blit(UI_HEART_IMG, (7 + i * (UI_HEART_IMG.get_width() + 4), 7))

        hx = 7                                   # potenciadores activos
        if player.shield:
            canvas.blit(PU_SMALL["shield"], (hx, 21))
            hx += 20
        if player.boost_timer > 0:
            canvas.blit(PU_SMALL["speed"], (hx, 21))
            pygame.draw.rect(canvas, (22, 24, 40), (hx + 19, 25, 34, 8))
            pygame.draw.rect(canvas, YELLOW, (hx + 20, 26, int(32 * player.boost_timer / float(BOOST_FRAMES)), 6))

        if game_mode == "LEVELS" and stage is not None:
            is_boss = stage["type"] == "boss"
            bar_w = int(WIDTH * (0.5 if is_boss else 0.4))
            bar_h = max(6, int(HEIGHT * 0.025))
            bar_x = int(WIDTH // 2 - bar_w // 2)
            bar_y = 7

            if is_boss:
                ratio = max(0, boss.hp) / float(boss.max_hp) if boss is not None else 0.0
                c_main, c_hi, label, lcol = (200, 30, 50), (255, 130, 140), stage["label"], RED
            else:
                ratio = min(1.0, level_cleared / float(stage["total"]))
                c_main, c_hi = (30, 170, 50), (150, 255, 160)
                label, lcol = "%s  %d/%d" % (stage["label"], level_cleared, stage["total"]), WHITE

            pygame.draw.rect(canvas, (22, 24, 40), (bar_x, bar_y, bar_w, bar_h))
            fill_w = int(ratio * (bar_w - 2))
            if fill_w > 0:
                pygame.draw.rect(canvas, c_main, (bar_x + 1, bar_y + 1, fill_w, bar_h - 2))
                pygame.draw.rect(canvas, c_hi, (bar_x + 1, bar_y + 1, fill_w, 1))
            pygame.draw.rect(canvas, LIGHT_GRAY, (bar_x, bar_y, bar_w, bar_h), 1)

            draw_text(font_medium, label, lcol, WIDTH // 2, bar_y + bar_h + 3)
        else:
            draw_text(font_large, "%d" % score, WHITE, WIDTH // 2, 6)
            if boss is not None:                                   # barra de vida del boss (modo infinito)
                bar_w = int(WIDTH * 0.42)
                bar_x = WIDTH // 2 - bar_w // 2
                bar_h = max(6, int(HEIGHT * 0.022))
                ratio = max(0, boss.hp) / float(boss.max_hp)
                pygame.draw.rect(canvas, (22, 24, 40), (bar_x, 40, bar_w, bar_h))
                if ratio > 0:
                    pygame.draw.rect(canvas, (200, 30, 50), (bar_x + 1, 41, int(ratio * (bar_w - 2)), bar_h - 2))
                    pygame.draw.rect(canvas, (255, 130, 140), (bar_x + 1, 41, int(ratio * (bar_w - 2)), 1))
                pygame.draw.rect(canvas, LIGHT_GRAY, (bar_x, 40, bar_w, bar_h), 1)
                draw_text(font_small, BOSS_NAMES.get(boss.idx, "BOSS"), RED, WIDTH // 2, 40 + bar_h + 2)
            elif game_state == "PLAYING":
                draw_text(font_small, "PROXIMO BOSS: %d" % inf_next_boss, LIGHT_GRAY, WIDTH // 2, 38)
            canvas.blit(COIN_ICON, (7, 40))
            canvas.blit(text_surf(font_medium, coins_text(coins_q), YELLOW), (25, 38))

        if game_state == "PLAYING":
            draw_controls(player.nuke_xp / float(player.max_nuke_xp), player.dash_cd == 0,
                          1.0 - player.dash_cd / float(player.dash_max), aim_lock)

        if flash_timer > 0:
            flash_surf.set_alpha(flash_timer * 12)
            canvas.blit(flash_surf, (0, 0))

        if boss is not None and boss.state == "INTRO" and game_state == "PLAYING":
            if (frame // 12) % 2 == 0:
                flash_surf.set_alpha(40)
                canvas.blit(flash_surf, (0, 0))
                draw_text(font_title, "¡ADVERTENCIA!", RED, WIDTH // 2, int(HEIGHT * 0.5))
                draw_text(font_medium, BOSS_NAMES.get(boss.idx, "BOSS"), WHITE, WIDTH // 2, int(HEIGHT * 0.5) + 34)

        if game_state == "TRANSITION":
            draw_text(font_large, transition_msg, GREEN, WIDTH // 2, HEIGHT // 3 - 26)
            draw_text(font_large, "VELOCIDAD LUZ...", CYAN, WIDTH // 2, HEIGHT // 3)
            if game_mode == "LEVELS" and stage_idx + 1 >= len(stages):
                # última parte del nivel: la pantalla se oscurece poco a poco hasta negro
                k = 1.0 - transition_timer / 150.0
                a = int(255 * max(0.0, min(1.0, (k - 0.35) / 0.65)))
                if a > 0:
                    fade_surf.set_alpha(a)
                    canvas.blit(fade_surf, (0, 0))

        if fade_in_t > 0 and game_state == "PLAYING":
            fade_surf.set_alpha(int(255 * fade_in_t / 30.0))
            canvas.blit(fade_surf, (0, 0))
            fade_in_t -= 1

        if game_state == "PAUSED":
            canvas.blit(dark_surf, (0, 0))
            draw_text(font_title, "PAUSA", WHITE, WIDTH // 2, HEIGHT // 4 - 10)
            btn_resume.draw(canvas)
            btn_menu.draw(canvas)
            draw_gear_button()

    elif game_state in ("GAMEOVER", "VICTORY"):
        if game_state == "GAMEOVER":
            msg, color = "GAME OVER", RED
        else:
            msg, color = "¡MISION CUMPLIDA!", GREEN
        draw_text(font_large, msg, color, WIDTH // 2, HEIGHT // 3 - 17)
        draw_text(font_medium, "%s  -  Puntuacion: %d" % (player_name or "PILOTO", score), WHITE, WIDTH // 2, HEIGHT // 3 + 10)
        if game_mode == "INFINITE":
            draw_text(font_medium, "MONEDAS GANADAS: +%s" % coins_text(run_coins_q), YELLOW, WIDTH // 2, HEIGHT // 3 + 30)
        if game_state == "GAMEOVER" and game_mode == "LEVELS":
            btn_retry.draw(canvas)
        btn_menu_end.draw(canvas)

    music_tick()
    present()
    clock.tick(60)

save_game()
pygame.quit()
sys.exit()
