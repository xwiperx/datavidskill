import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import engine as E
from engine import (font, tw, draw_ls, text_alpha, mix, clamp, lerp, BEBAS, I_BLACK, I_BOLD,
                    I_SEMI, I_MED, I_REG, I_LIGHT, W, H, GOLD, WHITE, MUTED)


def shadow_text(d, xy, s, f, fill, ls=0, alpha=255, shadow=0.55, blur_off=(0, 2)):
    if alpha <= 1:
        return
    if shadow > 0:
        sh = (0, 0, 0, int(alpha * shadow))
        draw_ls(d, (xy[0] + blur_off[0], xy[1] + blur_off[1]), s, f, sh[:3], ls, alpha=sh[3])
    draw_ls(d, xy, s, f, fill, ls, alpha=alpha)


def fmt_money(v):
    pre, suf = E.cfg('value_prefix', '$'), E.cfg('value_suffix', 'B')
    if v >= 1000 and suf.upper().startswith('B'):
        return f"{pre}{v/1000:.2f}T"
    if v >= 100:
        return f"{pre}{v:,.0f}{suf}"
    dec = int(E.cfg('value_decimals', 1))
    return f"{pre}{v:,.{dec}f}{suf}"


def fmt_money_long(v):
    pre = E.cfg('value_prefix', '$')
    if v >= 1000 and E.cfg('value_suffix', 'B').upper().startswith('B'):
        return f"{pre}{v/1000:.2f} TRILLION"
    return f"{pre}{v:,.0f}{E.cfg('long_suffix', ' BILLION')}"


def fit_name(draw, text, max_width=700, start_size=50, min_size=24):
    """Shrink a name, then ellipsize it so it stays inside its reserved lane."""
    size = start_size
    f = font(I_BOLD, size)
    while size > min_size and tw(draw, text, f, 0) > max_width:
        size -= 2
        f = font(I_BOLD, size)
    if tw(draw, text, f, 0) > max_width:
        fitted = text
        while fitted and tw(draw, fitted + '…', f, 0) > max_width:
            fitted = fitted[:-1]
        text = fitted + '…'
    return text, f


def panel(im, box, fill=(7, 11, 19, 200), border=(255, 255, 255, 26), radius=0, accent=None):
    x0, y0, x1, y1 = box
    lay = Image.new('RGBA', (x1 - x0, y1 - y0), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.rectangle([0, 0, x1 - x0 - 1, y1 - y0 - 1], fill=fill, outline=border, width=1)
    if accent:
        d.rectangle([0, 0, 3, y1 - y0 - 1], fill=accent)
    im.paste(lay, (x0, y0), lay)


def draw_topbar(im, p, idx, alpha=255, total=100):
    d = ImageDraw.Draw(im, 'RGBA')
    a = alpha
    # left brand
    d.rectangle([96, 74, 102, 88], fill=(255, 194, 88, a))
    draw_ls(d, (118, 72), E.cfg('brand', "DATA  VIDEO  ENGINE"), font(I_SEMI, 20),
            (188, 203, 224), 3.4, alpha=a)
    # right rank
    f_lab = font(I_SEMI, 14)
    draw_ls(d, (W - 96 - 168, 66), "RANK", f_lab, (126, 142, 164), 3.6, alpha=a)
    num = str(idx).zfill(3)
    f_num = font(BEBAS, 96)
    text_alpha(im, (W - 96 - 168, 82), num, f_num, (238, 244, 255), a)
    text_alpha(im, (W - 96 - 50, 138), f"/ {total}", font(I_MED, 22), (126, 142, 164), a)


def draw_scale(im, worth, alpha=255):
    """Bottom-right value scale."""
    if alpha < 3:
        return
    d = ImageDraw.Draw(im, 'RGBA')
    x1, y1 = W - 96, 980
    x0 = x1 - 430
    configured = float(E.cfg('scale_max', 0) or 0)
    sm = max(configured, math.ceil(E.MAXW / 100.0) * 100.0)
    pre, suf = E.cfg('value_prefix', '$'), E.cfg('value_suffix', 'B')
    d.line([(x0, y1), (x1, y1)], fill=(255, 255, 255, int(alpha * 0.22)), width=1)
    for k in range(5):
        v = sm * k / 4.0
        x = x0 + (x1 - x0) * k / 4.0
        d.line([(x, y1), (x, y1 + 6)], fill=(255, 255, 255, int(alpha * 0.3)), width=1)
        d.text((x - 6, y1 + 12), f"{v:,.0f}", font=font(I_MED, 15),
               fill=(120, 136, 158, int(alpha * 0.85)))
    d.text((x1, y1 - 18), f"{pre}{suf}", font=font(I_MED, 15),
           fill=(120, 136, 158, int(alpha * 0.85)), anchor='ra')
    xm = x0 + (x1 - x0) * clamp(worth / sm, 0.0, 1.0)
    col = E.tier_color(worth)
    d.rectangle([x0, y1 - 2, xm, y1 + 1], fill=col + (int(alpha * 0.9),))
    d.ellipse([xm - 5, y1 - 5, xm + 5, y1 + 5], fill=(255, 255, 255, alpha))
    draw_ls(d, (x0, y1 - 34), E.cfg('scale_label', 'VALUE SCALE'), font(I_SEMI, 13),
            (110, 126, 148), 3.0, alpha=int(alpha * 0.9))


def draw_progress(im, frac, color, alpha=255):
    if alpha < 3:
        return
    d = ImageDraw.Draw(im, 'RGBA')
    # Keep the progress rail visibly below the lower-third information card.
    y = H - 14
    d.line([(96, y), (W - 96, y)], fill=(255, 255, 255, int(alpha * 0.13)), width=2)
    x1 = 96 + (W - 192) * clamp(frac, 0, 1)
    d.line([(96, y), (x1, y)], fill=color + (int(alpha * 0.95),), width=2)
    d.ellipse([x1 - 4, y - 4, x1 + 4, y + 4], fill=(255, 255, 255, alpha))


def draw_card(im, p, alpha=255, appear=1.0):
    """Bottom-left lower-third information panel."""
    if alpha < 3:
        return
    x0, y0 = 96, 800
    col = E.tier_color(p['worth'])
    a = int(alpha * appear)
    lay = Image.new('RGBA', (820, 268), (0, 0, 0, 0))
    dl = ImageDraw.Draw(lay)
    # Near-opaque fill prevents tower numerals and face details from ghosting
    # through the lower third and reading as accidental text overlap.
    dl.rectangle([0, 0, 820, 268], fill=(5, 8, 14, int(a * 0.98)))
    dl.rectangle([0, 0, 820, 2], fill=col + (a,))
    dl.rectangle([0, 0, 4, 268], fill=col + (int(a * 0.55),))
    im.paste(lay, (0, y0 - 34), lay)
    d = ImageDraw.Draw(im, 'RGBA')
    d.ellipse([x0, y0 + 22, x0 + 9, y0 + 31], fill=col + (a,))
    draw_ls(d, (x0 + 20, y0 + 18), p['industry'].upper(), font(I_SEMI, 15), (150, 166, 188), 3.2, alpha=a)
    name, f = fit_name(d, p['name'].upper(), max_width=700)
    shadow_text(d, (x0, y0 + 42), name, f, (240, 245, 255), 0, a, 0.55)
    wstr = fmt_money(p['worth'])
    fw = font(BEBAS, 92)
    shadow_text(d, (x0 - 3, y0 + 98), wstr, fw, col, 0, a, 0.45)
    src = p['source'].upper()
    ctry = p['country'].upper() if p['country'] else ""
    meta = "  ·  ".join([s for s in [src, ctry] if s])
    f2 = font(I_MED, 18)
    if tw(d, meta, f2, 2.2) > 660:
        meta = meta[:48]
    draw_ls(d, (x0, y0 + 200), meta, f2, (128, 144, 166), 2.2, alpha=int(a * 0.95))
    if p.get('family'):
        draw_ls(d, (x0 + 420, y0 + 200), E.cfg("family_tag", "INCL. FAMILY"), font(I_SEMI, 12), (110, 126, 148), 2.4,
                alpha=int(a * 0.75))


def draw_plate(im, cam, p, idx, alpha=255, scale=1.0):
    """Floating name plate above the active tower's cap."""
    if alpha < 3:
        return
    i = idx - 1
    top = E.bar_base(i) + np.array([0, E.HEIGHTS[i], 0])
    pt = cam.project(np.array([top]))[0]
    if pt[2] < 1:
        return
    sx = pt[0]
    sy = pt[1] - 54 * scale
    col = E.tier_color(p['worth'])
    d = ImageDraw.Draw(im, 'RGBA')
    a = int(alpha)

    name = p['name'].upper()
    rk = "#" + str(idx)
    frk = font(BEBAS, int(30 * scale))
    wr = tw(d, rk, frk, 0)
    fs = int(33 * scale)
    f = font(I_BOLD, fs)
    while tw(d, name, f, 0.5) > min(430 * scale, 520 * scale - 48 * scale - wr) and fs > 11:
        fs -= 1
        f = font(I_BOLD, fs)
    wn = tw(d, name, f, 0.5)
    fw = font(BEBAS, int(40 * scale))
    ws = tw(d, fmt_money(p['worth']), fw, 0)
    pw = min(520 * scale, max(190 * scale, max(wn, ws) + 46 * scale))
    ph = 98 * scale

    # Use one deterministic callout lane for every active rank. The old code
    # silently returned when this plate touched the lower-third or portrait,
    # making labels disappear for parts of the countdown.
    panel = E.cfg('feature_portrait_box', [1480, 270, 344, 410])
    px, py, pwidth, pheight = panel
    lane_left = 930 * scale
    lane_right = min((W - 96) * scale, (px - 18) * scale)
    max_pw = max(180 * scale, lane_right - lane_left)
    pw = min(pw, max_pw)
    x0 = clamp(sx - pw / 2, lane_left, lane_right - pw)
    y0 = clamp(sy - ph, 8 * scale, 710 * scale)

    # Connect the active tower to the fixed, collision-free label lane.
    tx = clamp(sx, x0 + 18 * scale, x0 + pw - 18 * scale)
    if y0 + ph < pt[1] - 4 * scale:
        start, end = (tx, y0 + ph), (sx, pt[1] - 4 * scale)
    else:
        start, end = (sx, pt[1] + 4 * scale), (tx, y0)
    d.line([start, end], fill=col + (int(a * 0.55),), width=2)
    d.ellipse([tx - 3 * scale, (y0 + ph if y0 + ph < pt[1] - 4 * scale else y0) - 3 * scale,
               tx + 3 * scale, (y0 + ph if y0 + ph < pt[1] - 4 * scale else y0) + 3 * scale],
              fill=(255, 255, 255, a))

    lay = Image.new('RGBA', (int(pw) + 2, int(ph) + 2), (0, 0, 0, 0))
    dl = ImageDraw.Draw(lay)
    dl.rectangle([0, 0, int(pw), int(ph)], fill=(8, 12, 20, int(a * 0.80)),
                 outline=(255, 255, 255, int(a * 0.16)), width=1)
    dl.rectangle([0, 0, 3, int(ph)], fill=col + (a,))
    im.paste(lay, (int(x0), int(y0)), lay)
    d2 = ImageDraw.Draw(im, 'RGBA')
    text_alpha(im, (x0 + 22 * scale, y0 + 12 * scale), fmt_money(p['worth']), fw, col, a)
    text_alpha(im, (x0 + 22 * scale, y0 + 55 * scale), name, f, (236, 242, 255), a)
    # rank chip right
    text_alpha(im, (x0 + pw - 18 * scale - tw(d2, rk, frk, 0), y0 + 8 * scale), rk, frk, (140, 156, 178), a)
