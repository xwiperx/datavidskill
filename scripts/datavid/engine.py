"""3D ranked-tower renderer. Every pixel is drawn from code.

Reads a project directory (env DATAVID_PROJECT, else CWD) containing:
  config.json  - titles, units, colours, timing
  data.json    - {"items":[{"name","value","category","meta"}...], "total": optional}
"""
import json, math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1920, 1080
FPS = 30
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get('DATAVID_PROJECT', os.getcwd())
FONT_DIR = os.path.join(SKILL_DIR, 'fonts')
BEBAS = os.path.join(FONT_DIR, 'BebasNeue-Regular.ttf')
I_BLACK = os.path.join(FONT_DIR, 'InterDisplay-Black.ttf')
I_BOLD = os.path.join(FONT_DIR, 'InterDisplay-Bold.ttf')
I_SEMI = os.path.join(FONT_DIR, 'Inter-SemiBold.ttf')
I_MED = os.path.join(FONT_DIR, 'Inter-Medium.ttf')
I_REG = os.path.join(FONT_DIR, 'Inter-Regular.ttf')
I_LIGHT = os.path.join(FONT_DIR, 'Inter-Light.ttf')

CFG = json.load(open(os.path.join(ROOT, 'config.json')))
DATA = json.load(open(os.path.join(ROOT, 'data.json')))


def cfg(key, default=None):
    v = CFG.get(key, default)
    return default if v is None else v


ITEMS = sorted(DATA['items'], key=lambda x: float(x['value']))
N = len(ITEMS)
PEOPLE = [{
    'pos': i + 1,
    'name': it['name'],
    'worth': float(it['value']),
    'industry': it.get('category', ''),
    'source': it.get('meta', ''),
    'country': '',
    'family': bool(it.get('family', False)),
} for i, it in enumerate(ITEMS)]

MINW = min(p['worth'] for p in PEOPLE)
MAXW = max(p['worth'] for p in PEOPLE)
TOTAL = float(DATA.get('total') or sum(p['worth'] for p in PEOPLE))
SECOND = PEOPLE[-2]['worth'] if N > 1 else MAXW

# ---- timeline: 12s intro + N*SPI + 10s finale + 3.4s + 8.6s end card
SPI = float(cfg('seconds_per_item', 1.46))
if CFG.get('duration'):
    DUR = float(CFG['duration'])
    SPI = (DUR - 34.0) / N
else:
    DUR = 34.0 + N * SPI
NF = int(round(FPS * DUR))
T_INTRO = 12.0
T_FINALE_END = DUR - 12.0
T_COUNT_END = T_FINALE_END - 10.0
T_ENDCARD = T_FINALE_END + 3.4
PER_BAR = (T_COUNT_END - T_INTRO) / N

GAMMA = float(cfg('gamma', 0.72))

# ---------------------------------------------------------------- layout
DX, DZ = 6.00, 7.00
BW, BD = 3.60, 3.60
H_MIN, H_RANGE = 3.1, 27.0
HEIGHTS = [H_MIN + H_RANGE * ((p['worth'] / MAXW) ** GAMMA) for p in PEOPLE]
H_MAX = max(HEIGHTS)
DL = math.hypot(DX, DZ)
DIRV = np.array([DX / DL, 0.0, -DZ / DL])
LATV = np.array([DZ / DL, 0.0, DX / DL])
STEP = np.array([DX, 0.0, -DZ])

# ---------------------------------------------------------------- palette
BG_TOP = (3, 5, 11)
BG_HOR = (11, 24, 43)
BG_BOT = (2, 3, 7)
TIER = [tuple(c) for c in cfg('colors', [[40, 84, 240], [32, 196, 232], [150, 78, 240],
                                          [238, 62, 96], [255, 186, 64]])]
TIER_POS = cfg('color_positions', [0.0, 0.22, 0.40, 0.58, 0.84])
GOLD = (255, 194, 88)
WHITE = (238, 244, 255)
MUTED = (126, 142, 164)


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(round(lerp(c1[i], c2[i], t))) for i in range(3))


def clamp(v, a, b):
    return a if v < a else (b if v > b else v)


def smoothstep(x):
    x = clamp(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def ease_out(x, p=3.0):
    x = clamp(x, 0.0, 1.0)
    return 1 - (1 - x) ** p


def ease_in_out(x):
    return smoothstep(x)


def tier_color(worth):
    """Map a value to the colour ramp by its position on a log scale."""
    span = math.log(MAXW / MINW) if MAXW > MINW else 1.0
    t = clamp(math.log(max(worth, MINW) / MINW) / span, 0.0, 1.0)
    pos = TIER_POS
    for k in range(len(pos) - 1):
        if t <= pos[k + 1] or k == len(pos) - 2:
            f = (t - pos[k]) / max(1e-6, pos[k + 1] - pos[k])
            return mix(TIER[k], TIER[k + 1], clamp(f, 0, 1))
    return TIER[-1]


# ---------------------------------------------------------------- fonts
_fc = {}


def font(path, size):
    key = (path, max(6, int(size)))
    if key not in _fc:
        _fc[key] = ImageFont.truetype(path, key[1])
    return _fc[key]


def tw(draw, s, f, ls=0):
    if not s:
        return 0
    return sum(draw.textlength(ch, font=f) for ch in s) + ls * (len(s) - 1)


def text_alpha(im, xy, s, f, fill, alpha=255, ls=0):
    """Draw text with true alpha compositing (PIL ignores alpha in text fills)."""
    if alpha <= 2:
        return
    if alpha >= 252:
        d = ImageDraw.Draw(im, 'RGBA')
        x = xy[0]
        for ch in s:
            d.text((x, xy[1]), ch, font=f, fill=(fill[0], fill[1], fill[2], 255))
            x += d.textlength(ch, font=f) + ls
        return
    asc, desc = f.getmetrics()
    wpx = int(tw(ImageDraw.Draw(im), s, f, ls)) + 10
    hpx = asc + desc + 10
    lay = Image.new('RGBA', (max(1, wpx), max(1, hpx)), (0, 0, 0, 0))
    dl = ImageDraw.Draw(lay)
    x = 5
    for ch in s:
        dl.text((x, 5), ch, font=f, fill=(fill[0], fill[1], fill[2], 255))
        x += dl.textlength(ch, font=f) + ls
    lay.putalpha(lay.getchannel('A').point(lambda v: v * alpha // 255))
    im.paste(lay, (int(xy[0]) - 5, int(xy[1]) - 5), lay)


def draw_ls(draw, xy, s, f, fill, ls=0, anchor_left=True, alpha=255):
    x, y = xy
    if not anchor_left:
        x -= tw(draw, s, f, ls)
    im = draw._image
    if alpha >= 252:
        for ch in s:
            draw.text((x, y), ch, font=f, fill=(fill[0], fill[1], fill[2], 255))
            x += draw.textlength(ch, font=f) + ls
        return x
    if alpha > 2:
        text_alpha(im, (x, y), s, f, fill, alpha, ls)
    x += tw(draw, s, f, ls)
    return x


# ---------------------------------------------------------------- camera
class Cam:
    def __init__(self, pos, target, fov=40.0):
        self.pos = np.asarray(pos, float)
        fwd = np.asarray(target, float) - self.pos
        self.fwd = fwd / np.linalg.norm(fwd)
        up = np.array([0.0, 1.0, 0.0])
        r = np.cross(self.fwd, up)
        self.right = r / np.linalg.norm(r)
        self.up = np.cross(self.right, self.fwd)
        self.f = (H / 2) / math.tan(math.radians(fov) / 2)

    def view(self, pts):
        v = np.asarray(pts, float) - self.pos
        return np.stack([v @ self.right, v @ self.up, v @ self.fwd], axis=-1)

    def project(self, pts):
        v = self.view(pts)
        z = np.clip(v[..., 2], 1e-4, None)
        return np.stack([W / 2 + self.f * v[..., 0] / z,
                         H / 2 - self.f * v[..., 1] / z, v[..., 2]], axis=-1)

    def project1(self, p):
        return self.project(np.array([p]))[0]


# ---------------------------------------------------------------- scene math
def bar_base(i):
    return np.array([i * DX, 0.0, -i * DZ])


def height_at(u):
    i0 = clamp(int(math.floor(u)), 0, len(PEOPLE) - 1)
    i1 = int(clamp(i0 + 1, 0, len(PEOPLE) - 1))
    return lerp(HEIGHTS[i0], HEIGHTS[i1], clamp(u - math.floor(u), 0, 1))


def cam_state(u, rise=0.0, back=0.0, side=0.0, tilt=0.0, fov=37.0, look=1.0):
    h = height_at(u)
    base = np.array([u * DX, 0.0, -u * DZ])
    tgt_y = h - min(h * 0.50, 4.6) + tilt
    dist = 21.0 + h * 0.30 + back
    cam_y = tgt_y + 0.14 * dist + rise
    pos = base - DIRV * dist + LATV * (0.58 * dist + side) + np.array([0, cam_y, 0])
    tgt = base + DIRV * (0.78 * dist * look) + np.array([0, tgt_y, 0])
    return Cam(pos, tgt, fov)


# ---------------------------------------------------------------- drawing utils
_grad_cache = {}


def gradient_img(c_top, c_bot, segs=0):
    key = (c_top, c_bot, segs)
    g = _grad_cache.get(key)
    if g is None:
        base = np.zeros((512, 1, 3), np.uint8)
        for y in range(512):
            base[y, 0] = mix(c_top, c_bot, y / 511.0)
        if segs:
            for k in range(1, segs):
                yy = int(round(511 * k / segs))
                base[yy, 0] = (np.array(base[yy, 0]) * 0.62).astype(np.uint8)
        g = Image.fromarray(base, 'RGB')
        _grad_cache[key] = g
    return g


def fill_quad_grad(im, pts, c_top, c_bot, alpha=255, segs=0):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1 = int(math.floor(min(xs))), int(math.ceil(max(xs)))
    y0, y1 = int(math.floor(min(ys))), int(math.ceil(max(ys)))
    x0c, y0c, x1c, y1c = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
    w, hgt = x1c - x0c, y1c - y0c
    if w <= 0 or hgt <= 0:
        return
    g = gradient_img(c_top, c_bot, segs).resize((w, hgt), Image.NEAREST)
    mask = Image.new('L', (w, hgt), 0)
    ImageDraw.Draw(mask).polygon([(p[0] - x0c, p[1] - y0c) for p in pts], fill=alpha)
    im.paste(g, (x0c, y0c), mask)


_glow_cache = {}


def glow_sprite(color, size=192):
    key = (color, size)
    s = _glow_cache.get(key)
    if s is None:
        r = np.linspace(-1, 1, size, dtype=np.float32)
        xx, yy = np.meshgrid(r, r)
        d = np.sqrt(xx ** 2 + yy ** 2)
        a = np.clip(1 - d, 0, 1) ** 2.6
        arr = np.zeros((size, size, 4), np.uint8)
        arr[..., 0] = color[0]
        arr[..., 1] = color[1]
        arr[..., 2] = color[2]
        arr[..., 3] = (a * 255).astype(np.uint8)
        s = Image.fromarray(arr, 'RGBA')
        _glow_cache[key] = s
    return s


def add_glow(layer, cx, cy, rad, color, alpha, squash=0.6):
    if alpha <= 2 or rad < 2:
        return
    sp = glow_sprite(color)
    w = int(rad * 2)
    h = int(rad * 2 * squash)
    if w < 2 or h < 2:
        return
    sp2 = sp.resize((w, h), Image.BILINEAR)
    if alpha < 255:
        a = sp2.split()[3].point(lambda v: int(v * alpha / 255))
        sp2 = sp2.copy()
        sp2.putalpha(a)
    layer.alpha_composite(sp2, (int(cx - w / 2), int(cy - h / 2)))


def fill_quad(im, pts, fill):
    ImageDraw.Draw(im, 'RGBA').polygon([tuple(p) for p in pts], fill=fill)


# ---------------------------------------------------------------- background
_vig = None
_noise = None


def vignette():
    global _vig
    if _vig is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        nx = (xx - W / 2) / (W / 2)
        ny = (yy - H / 2) / (H / 2)
        r = np.sqrt(nx * nx * 0.8 + ny * ny)
        v = 1.0 - 0.40 * np.clip((r - 0.40) / 0.95, 0, 1) ** 1.5
        _vig = v[..., None].astype(np.float32)
    return _vig


def noise_tex():
    global _noise
    if _noise is None:
        rng = np.random.default_rng(7)
        small = rng.random((36, 64)).astype(np.float32)
        img = Image.fromarray((small * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
        n = np.array(img, np.float32) / 255.0
        n = (n - n.mean()) * 2.2
        _noise = n[..., None]
    return _noise


def background(cam, horizon_y):
    y = np.arange(H, dtype=np.float32)
    top = np.array(BG_TOP, np.float32)
    hor = np.array(BG_HOR, np.float32)
    bot = np.array(BG_BOT, np.float32)
    hy = clamp(horizon_y, -600, H + 600)
    a = np.clip((y - (hy - 520)) / 520.0, 0, 1)[:, None]
    b = np.clip((y - hy) / max(1.0, (H - hy)) * 1.4, 0, 1)[:, None]
    img = top * (1 - a) + hor * a
    img = img * (1 - b) + bot * b
    g = np.exp(-((y - hy) / 150.0) ** 2)[:, None]
    img = img + np.array([20, 46, 78], np.float32) * g * 0.75
    img = np.repeat(img[:, None, :], W, axis=1)
    return img


def draw_floor(im, cam, u):
    d = ImageDraw.Draw(im, 'RGBA')
    near = 0.8
    for k in range(-10, 11):
        off = k * 5.2
        p0 = DIRV * (u * DL - 70) + LATV * off
        p1 = DIRV * (u * DL + 300) + LATV * off
        seg = clip_seg(cam, p0, p1, near)
        if seg:
            depth = seg[0][2]
            alpha = int(clamp(20 * math.exp(-depth / 170.0), 0, 20))
            if alpha > 1:
                d.line([(seg[0][0], seg[0][1]), (seg[1][0], seg[1][1])], fill=(96, 150, 205, alpha), width=1)
    for i in range(-6, 106, 8):
        p0 = DIRV * (i * DL) + LATV * (-30)
        p1 = DIRV * (i * DL) + LATV * 30
        seg = clip_seg(cam, p0, p1, near)
        if seg:
            depth = seg[0][2]
            alpha = int(clamp(15 * math.exp(-depth / 150.0), 0, 15))
            if alpha > 1:
                d.line([(seg[0][0], seg[0][1]), (seg[1][0], seg[1][1])], fill=(80, 132, 190, alpha), width=1)


def clip_seg(cam, p0, p1, near=0.8):
    v0 = cam.view([p0])[0]
    v1 = cam.view([p1])[0]
    z0, z1 = v0[2], v1[2]
    if z0 < near and z1 < near:
        return None
    if z0 < near:
        v0 = v0 + (v1 - v0) * ((near - z0) / (z1 - z0))
    elif z1 < near:
        v1 = v1 + (v0 - v1) * ((near - z1) / (z0 - z1))
    out = []
    for v in (v0, v1):
        out.append((W / 2 + cam.f * v[0] / v[2], H / 2 - cam.f * v[1] / v[2], v[2]))
    return out


# ---------------------------------------------------------------- bars
LIGHT = np.array([-0.08, 0.80, 0.59])
LIGHT = LIGHT / np.linalg.norm(LIGHT)
_UP = np.array([0.0, 1.0, 0.0])


def bar_faces(i, h):
    base = bar_base(i)
    d = DIRV * (BD / 2)
    l = LATV * (BW / 2)
    up = np.array([0, h, 0])
    f0 = base - d - l
    f1 = base - d + l
    f2 = base - d + l + up
    f3 = base - d - l + up
    r0 = base - d + l
    r1 = base + d + l
    r2 = base + d + l + up
    r3 = base - d + l + up
    t0 = f3
    t1 = r3
    t2 = base + d + l + up
    t3 = base + d - l + up
    return (f0, f1, f2, f3), (r0, r1, r2, r3), (t0, t1, t2, t3)


_agrad_cache = {}


def agrad(c_top, c_bot, a_top, a_bot, gamma=1.0):
    key = (c_top, c_bot, a_top, a_bot, gamma)
    g = _agrad_cache.get(key)
    if g is None:
        arr = np.zeros((256, 1, 4), np.uint8)
        for y in range(256):
            t = (y / 255.0) ** gamma
            c = mix(c_top, c_bot, t)
            arr[y, 0] = (c[0], c[1], c[2], int(lerp(a_top, a_bot, t)))
        g = Image.fromarray(arr, 'RGBA')
        _agrad_cache[key] = g
    return g


def fill_quad_fade(im, pts, c_top, c_bot, a_top, a_bot, gamma=1.0):
    from PIL import ImageChops
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    x0, x1 = int(math.floor(min(xs))), int(math.ceil(max(xs)))
    y0, y1 = int(math.floor(min(ys))), int(math.ceil(max(ys)))
    x0c, y0c, x1c, y1c = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
    w, hgt = x1c - x0c, y1c - y0c
    if w <= 0 or hgt <= 0:
        return
    g = agrad(c_top, c_bot, a_top, a_bot, gamma).resize((w, hgt), Image.NEAREST)
    mask = Image.new('L', (w, hgt), 0)
    ImageDraw.Draw(mask).polygon([(p[0] - x0c, p[1] - y0c) for p in pts], fill=255)
    g.putalpha(ImageChops.multiply(g.getchannel('A'), mask))
    im.paste(g, (x0c, y0c), g)


def paste_quad(im, src, quad, alpha=255):
    """Affine-map an RGBA text image onto a projected quad (TL,TR,BR,BL)."""
    from PIL import ImageChops
    xs = [p[0] for p in quad]; ys = [p[1] for p in quad]
    x0, x1 = int(math.floor(min(xs))), int(math.ceil(max(xs)))
    y0, y1 = int(math.floor(min(ys))), int(math.ceil(max(ys)))
    x0c, y0c, x1c, y1c = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
    dw, dh = x1c - x0c, y1c - y0c
    if dw <= 0 or dh <= 0 or dw > 2400 or dh > 2400:
        return
    TL, TR, BL = quad[0], quad[1], quad[3]
    sw, sh = src.size
    a11 = (TR[0] - TL[0]) / sw; a21 = (TR[1] - TL[1]) / sw
    a12 = (BL[0] - TL[0]) / sh; a22 = (BL[1] - TL[1]) / sh
    det = a11 * a22 - a12 * a21
    if abs(det) < 1e-9:
        return
    i11, i12 = a22 / det, -a12 / det
    i21, i22 = -a21 / det, a11 / det
    c = -(i11 * TL[0] + i12 * TL[1]) + i11 * x0c + i12 * y0c
    f = -(i21 * TL[0] + i22 * TL[1]) + i21 * x0c + i22 * y0c
    try:
        out = src.transform((dw, dh), Image.AFFINE, (i11, i12, c, i21, i22, f), resample=Image.BICUBIC)
    except Exception:
        return
    mask = Image.new('L', (dw, dh), 0)
    ImageDraw.Draw(mask).polygon([(p[0] - x0c, p[1] - y0c) for p in quad], fill=255)
    if alpha < 255:
        mask = mask.point(lambda v: int(v * alpha / 255))
    out.putalpha(ImageChops.multiply(out.getchannel('A'), mask))
    im.paste(out, (x0c, y0c), out)



def text_on_quad(im, text, fnt_path, quad, color, alpha=255, fill_w=0.74, fill_h=0.62):
    """Draw text onto a projected quad without distortion (aspect-matched canvas)."""
    TL, TR, BR, BL = quad
    qw = math.hypot(TR[0] - TL[0], TR[1] - TL[1])
    qh = math.hypot(BL[0] - TL[0], BL[1] - TL[1])
    if qw < 8 or qh < 6:
        return
    cw = 640
    ch = max(8, int(round(cw * qh / qw)))
    if ch > 1200:
        ch = 1200
    probe = Image.new('RGBA', (8, 8))
    dp = ImageDraw.Draw(probe)
    size = max(8, int(ch * fill_h / 0.72))
    f = font(fnt_path, size)
    wt = tw(dp, text, f, 0)
    if wt > cw * fill_w:
        size = max(8, int(size * cw * fill_w / max(1.0, wt)))
        f = font(fnt_path, size)
        wt = tw(dp, text, f, 0)
    img = Image.new('RGBA', (cw, ch), (0, 0, 0, 0))
    d2 = ImageDraw.Draw(img)
    asc, desc = f.getmetrics()
    th = asc + desc
    d2.text(((cw - wt) / 2, (ch - th) / 2 - desc * 0.10), text, font=f, fill=color)
    paste_quad(im, img, quad, alpha)


def face_bands(im, quad, n, color=(0, 0, 0, 26), width=1):
    TL, TR, BR, BL = quad
    if n < 1:
        return
    d = ImageDraw.Draw(im, 'RGBA')
    for k in range(1, n):
        t = k / n
        x0 = TL[0] + (BL[0] - TL[0]) * t
        y0 = TL[1] + (BL[1] - TL[1]) * t
        x1 = TR[0] + (BR[0] - TR[0]) * t
        y1 = TR[1] + (BR[1] - TR[1]) * t
        d.line([(x0, y0), (x1, y1)], fill=color, width=width)

def text_img(text, fnt_path, size, color, pad=8, ls=0, align='center'):
    f = font(fnt_path, size)
    tmp = Image.new('RGBA', (10, 10))
    d = ImageDraw.Draw(tmp)
    wt = int(tw(d, text, f, ls)) + pad * 2
    asc, desc = f.getmetrics()
    ht = asc + desc + pad * 2
    img = Image.new('RGBA', (max(4, wt), max(4, ht)), (0, 0, 0, 0))
    dd = ImageDraw.Draw(img)
    if ls:
        draw_ls(dd, (pad, pad), text, f, color, ls)
    else:
        dd.text((pad, pad), text, font=f, fill=color)
    return img


def draw_ground_fx(im, emissive, cam, u, order):
    for vz, i in order:
        if vz > 95:
            continue
        h = HEIGHTS[i]
        col = tier_color(PEOPLE[i]['worth'])
        front, right, top = bar_faces(i, h)
        base_q = np.array([front[0], front[1],
                           [front[1][0], -h * 0.85, front[1][2]],
                           [front[0][0], -h * 0.85, front[0][2]]])
        pq = cam.project(base_q)
        if np.min(pq[:, 2]) < 0.8:
            continue
        fade = clamp(1.0 - vz / 95.0, 0, 1)
        fill_quad_fade(im, pq, mix(col, (255, 255, 255), 0.30), col, int(52 * fade), 0, 2.4)
        c = cam.project(np.array([bar_base(i)]))[0]
        rad = cam.f * (BW * 2.2) / max(7.0, c[2])
        add_glow(emissive, c[0], c[1], rad, col, int(40 * fade), 0.26)


def draw_one_bar(im, emissive, cam, i, h, u, vz, show_rank=True):
    p = PEOPLE[i]
    col = tier_color(p['worth'])
    fog = clamp(1.0 - math.exp(-max(0.0, vz - 4.0) / 135.0), 0, 0.88)
    dim = 1.0 - 0.62 * clamp((i - u - 1.0) / 6.0, 0, 1)
    front, right, top = bar_faces(i, h)
    pf = cam.project(np.array(front))
    pr = cam.project(np.array(right))
    pt = cam.project(np.array(top))
    if np.min(pf[:, 2]) < 0.8:
        return
    if max(pf[:, 0].max(), pr[:, 0].max(), pt[:, 0].max()) < -60:
        return
    if min(pf[:, 0].min(), pr[:, 0].min(), pt[:, 0].min()) > W + 60:
        return

    b_front = 0.26 + 0.95 * max(0.0, float(-DIRV @ LIGHT))
    b_right = 0.22 + 0.95 * max(0.0, float(LATV @ LIGHT))
    b_top = 0.42 + 0.80 * max(0.0, float(_UP @ LIGHT))

    def sh(c, b, d):
        c = tuple(int(clamp(v * b * d, 0, 255)) for v in c)
        return mix(c, BG_HOR, fog * 0.9)

    body_top = sh(mix(col, (255, 255, 255), 0.05), b_front * 0.95, dim)
    body_bot = sh(mix(col, (2, 4, 9), 0.93), b_front * 0.34, dim)
    fill_quad_fade(im, pf, body_top, body_bot, 255, 255, 4.2)
    fill_quad_fade(im, pr, sh(mix(col, (255, 255, 255), 0.02), b_right, dim),
                   sh(mix(col, (2, 4, 9), 0.95), b_right * 0.30, dim), 255, 255, 4.2)
    fill_quad_fade(im, pt, sh(mix(col, (255, 255, 255), 0.34), b_top * 0.98, dim),
                   sh(mix(col, (255, 255, 255), 0.06), b_top * 0.80, dim), 255, 255, 1.0)

    # horizontal floor bands for scale
    if vz < 75 and h > 2.4:
        nb = int(clamp(h / 1.05, 3, 34))
        pff = [tuple(pf[3][:2]), tuple(pf[2][:2]), tuple(pf[1][:2]), tuple(pf[0][:2])]
        if pff[0][0] > pff[1][0]:
            pff = [pff[1], pff[0], pff[3], pff[2]]
        face_bands(im, pff, nb, (2, 4, 8, int(46 * dim * (1 - fog))), 1)


    cb = h * 0.90
    cq = np.array([[front[0][0], cb, front[0][2]], [front[1][0], cb, front[1][2]],
                   front[2], front[3]])
    pcq = cam.project(cq)
    if np.min(pcq[:, 2]) > 0.8:
        fill_quad_fade(im, pcq, sh(mix(col, (255, 255, 255), 0.62), b_front * 1.05, dim),
                       sh(mix(col, (255, 255, 255), 0.18), b_front * 0.95, dim), 255, 255, 0.9)

    d2 = ImageDraw.Draw(im, 'RGBA')
    ea = int(105 * (1 - fog) * dim)
    d2.line([tuple(pf[3][:2]), tuple(pf[2][:2])], fill=tuple(mix(col, (255, 255, 255), 0.8)) + (int(ea * 1.9),), width=2)
    d2.line([tuple(pf[2][:2]), tuple(pf[1][:2])], fill=(255, 255, 255, int(ea * 0.7)), width=2)
    d2.line([tuple(pt[3][:2]), tuple(pt[2][:2]), tuple(pt[1][:2]), tuple(pt[0][:2])],
            fill=tuple(mix(col, (255, 255, 255), 0.72)) + (int(235 * (1 - fog)),), width=2)
    d2.line([tuple(pf[3][:2]), tuple(pf[0][:2])], fill=tuple(mix(col, (255, 255, 255), 0.35)) + (int(ea * 0.8),), width=1)

    if show_rank and vz < 52 and h > 1.2:
        ny0, ny1 = h - 3.35, h - 1.05
        q = np.array([[front[0][0], ny1, front[0][2]], [front[1][0], ny1, front[1][2]],
                      [front[1][0], ny0, front[1][2]], [front[0][0], ny0, front[0][2]]])
        pq = cam.project(q)
        if np.min(pq[:, 2]) > 0.8:
            wpx = abs(pq[1][0] - pq[0][0])
            hpx = abs(pq[3][1] - pq[0][1])
            if wpx > 44 and hpx > 26:
                qq = [tuple(pq[0][:2]), tuple(pq[1][:2]), tuple(pq[2][:2]), tuple(pq[3][:2])]
                if qq[0][0] > qq[1][0]:
                    qq = [qq[1], qq[0], qq[3], qq[2]]
                text_on_quad(im, str(p['pos']).zfill(2), BEBAS, qq,
                             tuple(int(v) for v in mix(col, (255, 255, 255), 0.82)) + (235,),
                             int(225 * (1 - fog) * dim), 0.56, 0.46)

    cx, cy = float(pt[:, 0].mean()), float(pt[:, 1].mean())
    rad = float(np.ptp(pt[:, 0])) * 1.15 + 24
    add_glow(emissive, cx, cy, rad, col, int(115 * (1 - fog)))
    add_glow(emissive, cx, cy, rad * 0.28, (255, 255, 255), int(75 * (1 - fog)), 0.5)


def draw_bars(im, cam, u, emissive, order, show_rank=True):
    for vz, i in reversed(order):
        if i < u - 0.75:
            continue
        draw_one_bar(im, emissive, cam, i, HEIGHTS[i], u, vz, show_rank)
