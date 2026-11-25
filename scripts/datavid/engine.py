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
DX, DZ = 4.45, 0.00
BW, BD = 3.60, 3.60
H_MIN, H_RANGE = float(cfg('height_min', 2.8)), float(cfg('height_range', 31.0))
RANK_MIX = max(0.0, min(1.0, float(cfg('height_rank_mix', 0.42))))
HEIGHTS = [H_MIN + H_RANGE * (
    (1.0 - RANK_MIX) * ((p['worth'] / MAXW) ** GAMMA) +
    RANK_MIX * (i / max(1, N - 1))) for i, p in enumerate(PEOPLE)]
H_MAX = max(HEIGHTS)
DL = math.hypot(DX, DZ)
DIRV = np.array([0.0, 0.0, -1.0])
LATV = np.array([1.0, 0.0, 0.0])
STEP = np.array([DX, 0.0, 0.0])

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


_IMAGE_CACHE = {}
_IMAGE_MANIFEST_PATH = os.path.join(ROOT, 'image_sources.json')
try:
    IMAGE_MANIFEST = json.load(open(_IMAGE_MANIFEST_PATH))
except (OSError, ValueError):
    IMAGE_MANIFEST = []


def item_image(index):
    """Return the locally cached Wikimedia image for a ranked entity, if available."""
    if index not in _IMAGE_CACHE:
        image = None
        if 0 <= index < len(IMAGE_MANIFEST):
            rel = IMAGE_MANIFEST[index].get('local_path')
            if rel:
                path = os.path.join(ROOT, rel)
                try:
                    image = Image.open(path).convert('RGB')
                    image.thumbnail((320, 400), Image.Resampling.LANCZOS)
                except (OSError, ValueError):
                    image = None
        _IMAGE_CACHE[index] = image
    return _IMAGE_CACHE[index]


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
    return np.array([i * DX, 0.0, 0.0])


def height_at(u):
    i0 = clamp(int(math.floor(u)), 0, len(PEOPLE) - 1)
    i1 = int(clamp(i0 + 1, 0, len(PEOPLE) - 1))
    return lerp(HEIGHTS[i0], HEIGHTS[i1], clamp(u - math.floor(u), 0, 1))


def cam_state(u, rise=0.0, back=0.0, side=0.0, tilt=0.0, fov=37.0, look=1.0):
    lead = float(cfg('camera_lead_steps', 3.5))
    base = np.array([(u - lead) * DX, 0.0, 0.0])
    # Fixed vertical framing keeps true tower-height differences visible instead
    # of auto-zooming every item to the same apparent height. The camera looks
    # straight down the parade lane, so the active front face stays head-on.
    tgt_y = float(cfg('camera_target_y', 14.2)) + tilt
    dist = float(cfg('camera_distance', 46.0)) + back
    cam_y = tgt_y + 0.11 * dist + rise
    lateral = 0.0 if cfg('camera_front', True) else 0.36 * dist
    pos = base - DIRV * dist + LATV * (lateral + side) + np.array([0, cam_y, 0])
    tgt = base + DIRV * (0.78 * dist * look) + np.array([0, tgt_y, 0])
    return Cam(pos, tgt, float(cfg('camera_fov', fov)))


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
    """Subtle softened-square footprint glow beneath each visible column."""
    for vz, i in order:
        if vz > 100:
            continue
        col = tier_color(PEOPLE[i]['worth'])
        bevel = min(float(cfg('bevel_radius',0.42)), BW*0.22, BD*0.22)
        xz=[(-BW/2+bevel,-BD/2),(BW/2-bevel,-BD/2),(BW/2,-BD/2+bevel),
            (BW/2,BD/2-bevel),(BW/2-bevel,BD/2),(-BW/2+bevel,BD/2),
            (-BW/2,BD/2-bevel),(-BW/2,-BD/2+bevel)]
        pts=np.asarray([bar_base(i)+np.array([x,0.025,z]) for x,z in xz])
        pr=cam.project(pts)
        if np.min(pr[:,2])<0.8: continue
        fade=clamp(1.0-vz/100.0,0,1)
        d=ImageDraw.Draw(im,'RGBA')
        d.polygon([tuple(q[:2]) for q in pr],fill=col+(int(15*fade),),outline=col+(int(70*fade),))
        c=cam.project(np.array([bar_base(i)]))[0]
        add_glow(emissive,c[0],c[1],cam.f*(BW*1.5)/max(7.0,c[2]),col,int(30*fade),0.28)
def draw_one_bar(im, emissive, cam, i, h, u, vz, show_rank=True):
    """Draw a softened chamfered cuboid, with a fixed-size image high on its front."""
    if h<=0.05: return
    p=PEOPLE[i]; col=tier_color(p['worth'])
    fog=clamp(1.0-math.exp(-max(0.0,vz-4.0)/150.0),0,0.82)
    dim=1.0-0.48*clamp((i-u-2.0)/7.0,0,1)
    bevel=min(float(cfg('bevel_radius',0.42)),BW*0.22,BD*0.22)
    if str(cfg('geometry','beveled_box')).lower()=='cylinder':
        radius=min(BW,BD)*0.5
        xz=[(radius*math.cos(math.tau*k/48),radius*math.sin(math.tau*k/48)) for k in range(48)]
    else:
        xz=[(-BW/2+bevel,BD/2),(BW/2-bevel,BD/2),(BW/2,BD/2-bevel),
            (BW/2,-BD/2+bevel),(BW/2-bevel,-BD/2),(-BW/2+bevel,-BD/2),
            (-BW/2,-BD/2+bevel),(-BW/2,BD/2-bevel)]
    ys=[0.0,min(bevel*0.52,h*0.18),max(min(bevel*0.52,h*0.18),h-min(bevel*0.52,h*0.18)),h]
    scales=[0.94,1.0,1.0,0.94]
    rings=[]
    for y,sc in zip(ys,scales):
        rings.append([bar_base(i)+np.array([x*sc,y,z*sc]) for x,z in xz])
    material=str(cfg('material','glass')).lower()
    alpha={'glass':154,'metal':232,'solid':255}.get(material,154)
    surfaces=[]
    for r in range(3):
        for k in range(len(xz)):
            j=(k+1)%len(xz)
            q3=np.asarray([rings[r][k],rings[r][j],rings[r+1][j],rings[r+1][k]])
            pv=cam.project(q3)
            if np.min(pv[:,2])<0.8: continue
            dx=xz[j][0]-xz[k][0]; dz=xz[j][1]-xz[k][1]
            normal=np.array([-dz,0.0,dx]); normal/=max(1e-8,np.linalg.norm(normal))
            surfaces.append((float(np.mean(pv[:,2])),r,k,pv,normal))
    for _,r,k,pv,normal in sorted(surfaces,key=lambda row:row[0],reverse=True):
        lambert=max(0.0,float(normal@LIGHT)); shade=0.34+0.72*lambert
        hi=mix(col,(255,255,255),0.25 if material=='glass' else 0.10)
        lo=mix(col,(2,5,14),0.58 if material=='glass' else 0.82)
        hi=mix(tuple(int(clamp(v*shade*dim,0,255)) for v in hi),BG_HOR,fog*0.7)
        lo=mix(tuple(int(clamp(v*shade*dim,0,255)) for v in lo),BG_HOR,fog*0.7)
        fa=int(alpha*(1-0.42*fog)*dim)
        fill_quad_fade(im,pv[:,:2],hi,lo,fa,fa,1.25)
        d=ImageDraw.Draw(im,'RGBA')
        d.line([tuple(q[:2]) for q in pv]+[tuple(pv[0,:2])],
               fill=mix(col,(255,255,255),0.52)+(int(86*(1-fog)*dim),),width=1)
    top=cam.project(np.asarray(rings[-1]))
    if np.min(top[:,2])>0.8:
        tc=mix(col,(240,248,255),0.42 if material=='glass' else 0.22)
        d=ImageDraw.Draw(im,'RGBA')
        top_alpha = 255 if material == 'solid' else int(alpha * 0.92)
        d.polygon([tuple(q[:2]) for q in top],fill=tc+(top_alpha,),outline=(240,248,255,int(166*(1-fog))))
        add_glow(emissive,float(top[:,0].mean()),float(top[:,1].mean()),
                 float(np.ptp(top[:,0]))*0.7+12,col,int(74*(1-fog)),0.28)
    # A single light sweep travels over the active column during its rank reveal.
    # Keep it at mid-height so it never obscures the portrait or rank plate.
    active_i = int(clamp(math.floor(u), 0, N-1))
    if i == active_i and h > 0.5:
        phase = clamp(u - math.floor(u), 0.0, 1.0)
        front_y = max(0.18, h * 0.52)
        face_half = max(0.2, BW/2-bevel*0.70)
        row3 = np.asarray([bar_base(i)+np.array([-face_half,front_y,BD/2+0.012]),
                           bar_base(i)+np.array([ face_half,front_y,BD/2+0.012])])
        row = cam.project(row3)
        if np.min(row[:,2]) > 0.8:
            x = lerp(row[0,0],row[1,0],ease_out(phase))
            y = lerp(row[0,1],row[1,1],ease_out(phase))
            env = math.sin(math.pi*phase)**0.45 if 0 < phase < 1 else 0.0
            aa = int(220*env*(1-fog))
            if aa > 2:
                d = ImageDraw.Draw(im,'RGBA')
                d.line([tuple(row[0,:2]),tuple(row[1,:2])],fill=col+(int(42*env*(1-fog)),),width=2)
                d.line([(x-20,y),(x+20,y)],fill=(222,246,255,aa),width=3)
                d.ellipse([x-4,y-4,x+4,y+4],fill=(255,255,255,aa))
        # Brighten the active cap rim for a clean, single-focus reveal beat.
        if np.min(top[:,2]) > 0.8:
            pulse = int(140*(0.25+0.75*math.sin(math.pi*phase))*(1-fog))
            d = ImageDraw.Draw(im,'RGBA')
            d.line([tuple(q[:2]) for q in top]+[tuple(top[0,:2])],
                   fill=(224,246,255,pulse),width=2)
    portrait=item_image(i)
    # Keep the square wholly inside the flat face: inset from both chamfered
    # edges, the cap seam, and the rank-number zone below it.
    safe_width=max(0.0, BW-2*(bevel+0.24))
    side=min(float(cfg('bar_image_size',1.28)),safe_width)
    if portrait is not None and side>=0.60 and h>=side+1.90:
        y1=h-0.42; y0=y1-side
        z=BD/2+0.010
        x0,x1=-side/2,side/2
        quad3=[bar_base(i)+np.array([x0,y1,z]),bar_base(i)+np.array([x1,y1,z]),
               bar_base(i)+np.array([x1,y0,z]),bar_base(i)+np.array([x0,y0,z])]
        pq=cam.project(np.asarray(quad3))
        if np.min(pq[:,2])>0.8 and abs(pq[1,0]-pq[0,0])>12:
            from PIL import ImageOps
            pane=ImageOps.fit(portrait,(360,360),method=Image.Resampling.LANCZOS,centering=(0.5,0.38)).convert('RGBA')
            mask=Image.new('L',pane.size,0)
            if str(cfg('image_shape','square')).lower()=='circle':
                ImageDraw.Draw(mask).ellipse((1,1,358,358),fill=255)
            else:
                ImageDraw.Draw(mask).rounded_rectangle((1,1,358,358),radius=22,fill=255)
            pane.putalpha(mask)
            paste_quad(im,pane,pq[:,:2],int(245*(1-fog)*dim))
            d=ImageDraw.Draw(im,'RGBA')
            d.line([tuple(q[:2]) for q in pq]+[tuple(pq[0,:2])],
                   fill=mix(col,(255,255,255),0.68)+(int(225*(1-fog)),),width=2)
    if show_rank and vz<80 and h>1.45:
        # Oversized rank occupies roughly half the front-face height. It is
        # placed below the portrait zone and inset from the bevels.
        face_w=max(0.55,BW-2*(bevel+0.20))
        box_h=min(1.38,max(0.70,h*0.48))
        y0=0.20
        y1=min(h-0.16,y0+box_h)
        if y1-y0>=0.55:
            quad=cam.project(np.asarray([bar_base(i)+np.array([-face_w/2,y1,BD/2+0.014]),bar_base(i)+np.array([face_w/2,y1,BD/2+0.014]),
                 bar_base(i)+np.array([face_w/2,y0,BD/2+0.014]),bar_base(i)+np.array([-face_w/2,y0,BD/2+0.014])]))
            if np.min(quad[:,2])>0.8:
                text_on_quad(im,str(p['pos']).zfill(2),BEBAS,quad[:,:2],(250,252,255,248),
                             int(242*(1-fog)*dim),0.88,0.84)

def draw_bars(im, cam, u, emissive, order, show_rank=True):
    """Reveal only the current item; animate its height up from the floor."""
    active = min(N-1, max(0, int(u)))
    fraction = clamp(u - active, 0.0, 1.0)
    rise_fraction = max(0.1, min(1.0, float(cfg('growth_fraction', 0.46))))
    growth = smoothstep(fraction / rise_fraction)
    for vz, i in reversed(order):
        if i > active or i < active - 9:
            continue
        h = HEIGHTS[i] * (growth if i == active else 1.0)
        if i == active:
            h = max(0.08, h)
        draw_one_bar(im, emissive, cam, i, h, u, vz, show_rank)
