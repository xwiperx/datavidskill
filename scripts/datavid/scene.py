import math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import engine as E
import hud as Hd
from engine import (W, H, FPS, PEOPLE, HEIGHTS, H_MIN, font, tw, draw_ls, mix, clamp, lerp,
                    smoothstep, ease_out, BEBAS, I_BLACK, I_BOLD, I_SEMI, I_MED, I_REG, I_LIGHT,
                    GOLD, WHITE, MUTED, tier_color, cam_state, bar_base, CFG, N, DUR, NF,
                    TOTAL, SECOND, MAXW, T_INTRO, T_COUNT_END, T_FINALE_END, T_ENDCARD, PER_BAR)

_rng = np.random.default_rng(11)
_GRAIN = [_rng.normal(0, 3.0, (H, W, 1)).astype(np.float32) for _ in range(6)]


def u_of_t(t):
    if t <= T_INTRO:
        return 0.0
    if t >= T_COUNT_END:
        return float(N)
    # Make each bar's local progress a direct function of wall-clock time.
    # The active rank, tower rise, featured portrait, and label now switch at
    # the same boundary instead of the old delayed eased threshold.
    return clamp((t - T_INTRO) / PER_BAR, 0.0, float(N))


def active_rank_state(t):
    """Return zero-based active rank, within-rank phase, and shared HUD alpha."""
    if t < T_INTRO or t >= T_COUNT_END:
        return None, 0.0, 0
    elapsed = t - T_INTRO
    index = min(N - 1, int(elapsed / PER_BAR))
    phase = clamp((elapsed - index * PER_BAR) / PER_BAR, 0.0, 1.0)
    # All rank-specific identity elements use one short enter/exit envelope.
    # This clears the previous portrait and copy before the next tower begins.
    fade_in = 0.72 + 0.28 * smoothstep(phase / 0.035)
    fade_out = smoothstep((1.0 - phase) / 0.055)
    return index, phase, int(255 * min(fade_in, fade_out))


def reveal_of(t, i):
    return smoothstep((t - (6.0 + i * 0.016)) / 1.05)


def scene_cam(t, u):
    if t < T_INTRO:
        p = smoothstep((t - 0.5) / 9.8)
        e = (1 - p) ** 2
        return cam_state(0, rise=27 * e, back=72 * e, side=0, tilt=3.0 * e, fov=39)
    if t > T_COUNT_END:
        p = smoothstep((t - T_COUNT_END) / 8.0)
        return cam_state(u, rise=-1.8 * p, back=4.0 * p, side=0, tilt=-0.8 * p)
    return cam_state(u, side=0)


def draw_youtube_mark(d, cx, cy, width=64, alpha=255):
    """Simple red rounded play mark used beside the channel name."""
    w=float(width); h=w*0.69
    x0,y0=cx-w/2,cy-h/2
    d.rounded_rectangle([x0,y0,x0+w,y0+h],radius=h*0.24,fill=(255,0,0,int(alpha)))
    d.polygon([(cx-w*0.10,cy-h*0.23),(cx-w*0.10,cy+h*0.23),(cx+w*0.29,cy)],
              fill=(255,255,255,int(alpha)))


def draw_intro_motion(im, t):
    """Edge-safe motion accents: sweeping scan, frame ticks and data pulses."""
    d = ImageDraw.Draw(im, 'RGBA')
    enter = smoothstep(t / 0.55)
    exit_a = clamp((11.9 - t) / 0.8, 0, 1)
    a = int(235 * enter * exit_a)
    if a <= 0:
        return
    # Thin editorial corner brackets stay in the outer safe margins.
    y0, y1 = 185, 790
    for x, direction in ((86, 1), (W-86, -1)):
        d.line([(x, y0), (x, y0+58)], fill=(113,176,231,int(a*0.78)), width=2)
        d.line([(x, y0), (x+direction*56, y0)], fill=(255,194,88,int(a*0.88)), width=2)
        d.line([(x, y1-46), (x, y1)], fill=(113,176,231,int(a*0.66)), width=2)
    # Short scan beam crosses the central field only while no lower-third is present.
    p = (t * 0.62) % 1.0
    sx = 180 + p * (W - 360)
    if 0.6 < t < 7.25:
        d.line([(sx-54, 720), (sx+54, 720)], fill=(120,220,255,int(a*0.82)), width=3)
        d.ellipse([sx-7,713,sx+7,727], fill=(226,248,255,int(a*0.98)))
    # A few animated index markers orbit the main reticle, avoiding the title lockup.
    if 1.0 < t < 7.2:
        cx, cy, rr = W/2, 438, 335
        for j in range(4):
            ang = t*0.72 + j*math.pi/2
            x, y = cx+math.cos(ang)*rr, cy+math.sin(ang)*rr
            d.rounded_rectangle([x-11,y-3,x+11,y+3],radius=3,
                                fill=(255,194,88,int(a*0.82)))
    # Restrained floating data sparks confined to the negative-space perimeter.
    for j in range(18):
        phase = (t * (0.10 + (j % 4) * 0.025) + j * 0.173) % 1.0
        x = 120 + ((j * 173) % (W-240))
        y = 145 + phase * 650
        if x < 470 or x > 1450:
            r = 1 + (j % 3)
            d.ellipse([x-r,y-r,x+r,y+r], fill=(138,202,255,int(a*(0.18+0.12*(j%4)))))


def draw_boundary_sweep(im, t, start, end, color=(105,210,255)):
    """A short, readable light wipe at editorial scene boundaries."""
    p = (t-start)/(end-start)
    if not 0 <= p <= 1:
        return
    envelope = math.sin(math.pi*p) ** 0.8
    x = -260 + (W+520)*ease_out(p)
    d = ImageDraw.Draw(im,'RGBA')
    aa = int(125*envelope)
    d.polygon([(x-120,-40),(x-38,-40),(x+230,H+40),(x+148,H+40)],
              fill=tuple(color)+(int(aa*0.20),))
    d.line([(x,0),(x+185,H)],fill=tuple(color)+(aa,),width=3)
    d.line([(x-13,0),(x+172,H)],fill=(245,252,255,int(aa*0.38)),width=1)
    flare_y = H*(0.18+0.64*p)
    d.ellipse([x-8,flare_y-8,x+8,flare_y+8],fill=(255,255,255,int(aa*0.72)))


def draw_countdown_motion(im, t, u, idx, color):
    """Repeatable per-rank motion language: arrival pulse and progress spark."""
    d = ImageDraw.Draw(im,'RGBA')
    phase = clamp(u-math.floor(u),0,1)
    start = T_INTRO + max(0,idx-1)*PER_BAR
    age = max(0,t-start)
    # Brief, edge-safe gold tick under the rank HUD, leaving all glyphs unobscured.
    kick = math.exp(-((age-0.12)/0.22)**2)
    if kick > 0.02:
        aa = int(190*kick)
        x0,x1 = W-96-224,W-96-178
        d.line([(x0,174),(x0+(x1-x0)*ease_out(min(1,age/0.28)),174)],
               fill=tuple(color)+(aa,),width=3)
        d.ellipse([x0-3,170,x0+3,176],fill=(255,245,210,aa))
    # A bright pulse follows the existing lower progress marker, not the text panels.
    frac = (idx-1)/max(1,N-1)
    x = 96+(W-192)*frac
    pulse = math.sin(math.pi*phase) if 0 < phase < 1 else 0.0
    if pulse > 0.01:
        aa = int(135*pulse)
        y = H-26
        d.line([(max(96,x-72),y),(x,y)],fill=tuple(color)+(int(aa*0.42),),width=4)
        r = 5+5*pulse
        d.ellipse([x-r,y-r,x+r,y+r],outline=(222,244,255,aa),width=2)
    # Ten-rank chapter gates punctuate the grouped climb; the last ten still
    # receive one distinct individual reveal each, with the same per-rank pulse.
    if idx in (10,20,30,40,50,60,70,80,90,100) and age < 0.70:
        cp = clamp(age/0.45,0,1)
        xx = 96+(W-192)*(frac)
        spread = 75*ease_out(cp)
        aa = int(100*(1-cp*0.25))
        d.line([(xx-spread, H-43),(xx+spread,H-43)],fill=tuple(color)+(aa,),width=2)
def draw_title(im, t):
    """Cinematic opening: kinetic numeric motif, editorial title, portrait teaser."""
    d = ImageDraw.Draw(im, 'RGBA')
    # Keep the title lockup clear: no decorative words or numerals behind text.
    d = ImageDraw.Draw(im, 'RGBA')
    # Sweeping circular reticle and tick marks establish a documentary/data tone.
    ring_a = int(115 * clamp(t/0.8, 0, 1) * clamp((7.6-t)/1.0, 0, 1))
    if ring_a > 0:
        cx, cy = W/2, 438
        rr = 294 + 10*math.sin(t*1.1)
        d.arc([cx-rr, cy-rr, cx+rr, cy+rr], start=204 + t*10, end=336 + t*10,
              fill=(90, 172, 228, ring_a), width=2)
        d.arc([cx-rr-16, cy-rr-16, cx+rr+16, cy+rr+16], start=30-t*8, end=95-t*8,
              fill=(255, 194, 88, int(ring_a*0.82)), width=2)
        for j in range(61):
            ang = (j/60.0)*math.tau - math.pi/2 + t*0.12
            r0, r1 = rr + (8 if j % 5 == 0 else 13), rr + 19
            x0, y0 = cx+math.cos(ang)*r0, cy+math.sin(ang)*r0
            x1, y1 = cx+math.cos(ang)*r1, cy+math.sin(ang)*r1
            d.line([(x0,y0),(x1,y1)], fill=(152,190,226,int(ring_a*(0.8 if j%5==0 else 0.35))), width=2 if j%5==0 else 1)
    # Thin gold sweep moves across the image as the title resolves.
    if 0.25 < t < 7.5:
        p = ease_out(clamp((t-0.25)/1.4,0,1))
        half = 640*p
        yline = 302 + 5*math.sin(t*1.2)
        a = int(210*clamp((7.5-t)/0.8,0,1))
        d.line([(W/2-half,yline),(W/2+half,yline)], fill=(255,194,88,a), width=2)
        d.ellipse([W/2+half-4,yline-4,W/2+half+4,yline+4], fill=(255,238,192,a))
    # Main title rises into its editorial lockup.
    if 0.55 < t < 7.5:
        a = int(255*clamp((t-0.55)/0.8,0,1)*clamp((7.35-t)/0.8,0,1))
        slide = 42*(1-ease_out(clamp((t-0.55)/1.2,0,1)))
        kicker = CFG.get('title_top', "THE WORLD'S")
        fk = font(I_SEMI, 19)
        draw_ls(d,(W/2-tw(d,kicker,fk,6)/2,326+slide),kicker,fk,(200,215,235),6,alpha=a)
        title = CFG.get('title_big','RICHEST')
        ft = font(BEBAS,194)
        while tw(d,title,ft,5)>W-300 and ft.size>66:
            ft=font(BEBAS,ft.size-8)
        settle = 10 * (1 - ease_out(clamp((t-0.55)/1.5,0,1)))
        draw_ls(d,(W/2-tw(d,title,ft,5)/2,348+slide+settle),title,ft,(246,249,255),5,alpha=a)
        sub = str(CFG.get('title_sub','')).strip()
        if sub:
            fs = font(I_MED,17)
            while tw(d,sub,fs,3.5)>W-360 and fs.size>10:
                fs=font(I_MED,fs.size-1)
            draw_ls(d,(W/2-tw(d,sub,fs,3.5)/2,568),sub,fs,(152,172,196),3.5,alpha=int(a*0.88))
    # Channel wordmark and YouTube play mark are the hero signature beneath RICHEST.
    if 1.3 < t < 7.6:
        brand_p = ease_out(clamp((t-1.3)/0.8,0,1))
        ba=int(255*brand_p*clamp((7.6-t)/0.6,0,1))
        brand=CFG.get('brand','DATA ZED')
        fb=font(I_BLACK,42)
        textw=tw(d,brand,fb,3.2)
        markw=62
        gap=22
        left=W/2-(textw+gap+markw)/2 + 22*(1-brand_p)
        draw_ls(d,(left,550),brand,fb,(245,248,255),3.2,alpha=ba)
        draw_youtube_mark(d,left+textw+gap+markw/2,572,markw*brand_p,ba)
    # Four rounded portrait windows briefly preview the range of the countdown.
    if 2.7 < t < 7.1:
        from PIL import ImageOps
        alpha = int(225*clamp((t-2.7)/0.65,0,1)*clamp((7.1-t)/0.55,0,1))
        ids = [max(0,N-1), max(0,int(N*0.74)), max(0,int(N*0.49)), 0]
        card_w, card_h = 146, 122
        gap = 24
        previews = [(idx, E.item_image(idx)) for idx in ids]
        previews = [(idx, imsrc) for idx, imsrc in previews if imsrc is not None]
        x0 = W/2 - (len(previews)*card_w+max(0,len(previews)-1)*gap)/2
        for k, (idx, imsrc) in enumerate(previews):
            label = f'#{idx+1:02d}'
            x = int(x0+k*(card_w+gap))
            pane = ImageOps.fit(imsrc,(card_w,card_h),method=Image.Resampling.LANCZOS,centering=(0.5,0.34)).convert('RGBA')
            mask = Image.new('L',pane.size,0)
            ImageDraw.Draw(mask).rounded_rectangle((0,0,card_w-1,card_h-1),radius=16,fill=alpha)
            pane.putalpha(mask)
            im.paste(pane,(x,655),pane)
            d.rounded_rectangle([x,655,x+card_w,655+card_h],radius=16,outline=(255,255,255,int(alpha*0.62)),width=2)
            d.rounded_rectangle([x+7,663,x+52,690],radius=9,fill=(4,8,15,int(alpha*0.82)))
            draw_ls(d,(x+16,667),label,font(BEBAS,20),(255,205,110),0,alpha=alpha)
    # Topic reveal lands between the logo and portrait strip, then clears cleanly.
    if 4.0 < t < 7.3:
        ta = int(235*clamp((t-4.0)/0.35,0,1)*clamp((7.3-t)/0.35,0,1))
        progress = ease_out(clamp((t-4.1)/0.7,0,1))
        tag = 'GLOBAL BILLIONAIRE RANKING  ·  ESTIMATED NET WORTH'
        ftick = font(I_SEMI, 13)
        draw_ls(d,(W/2-tw(d,tag,ftick,2.8)/2,615),tag,ftick,(174,205,235),2.8,alpha=ta)
        d.line([(W/2-260, 642), (W/2-260+520*progress, 642)], fill=(72,182,239,int(ta*0.9)), width=2)
    # Countdown premise returns briefly as a compact ticker before the first reveal.
    if 7.0 < t < 10.9:
        ta = int(225*clamp((t-7.0)/0.45,0,1)*clamp((10.9-t)/0.5,0,1))
        progress = ease_out(clamp((t-7.1)/1.0,0,1))
        d.line([(W/2-220, 790), (W/2-220+440*progress, 790)], fill=(72,182,239,int(ta*0.82)), width=2)
        tag = 'NET WORTH  /  RANKED FROM 1 TO 100'
        ftick = font(I_SEMI, 14)
        draw_ls(d,(W/2-tw(d,tag,ftick,3.4)/2,802),tag,ftick,(174,205,235),3.4,alpha=ta)
    # Source lower third settles before the first rank appears.
    if 7.15 < t < 12.1:
        a = int(255*clamp((t-7.15)/0.75,0,1)*clamp((12.05-t)/0.65,0,1))
        d.rounded_rectangle([94,850,98,958],radius=2,fill=(255,194,88,a))
        draw_ls(d,(122,858),CFG.get('lower_kicker',f'RANKED #1 TO #{N}'),font(I_SEMI,17),(255,194,88),3.6,alpha=a)
        draw_ls(d,(122,890),CFG.get('lower_mid','BY ESTIMATED NET WORTH'),font(I_MED,16),(205,218,236),3.0,alpha=a)
        draw_ls(d,(122,922),CFG.get('source_line',''),font(I_REG,14),(126,142,164),2.4,alpha=int(a*0.9))
def draw_feature_portrait(im, index, alpha=255):
    """Fixed-size portrait card in the reserved right-side negative space."""
    portrait=E.item_image(index)
    x0,y0,w,h=map(int,CFG.get('feature_portrait_box',[1480,270,344,410]))
    a=int(clamp(alpha,0,255))
    d=ImageDraw.Draw(im,'RGBA')
    col=tier_color(PEOPLE[index]['worth'])
    d.rounded_rectangle([x0,y0,x0+w,y0+h],radius=18,
                        fill=(5,9,17,int(a*0.92)),outline=(col[0],col[1],col[2],int(a*0.82)),width=2)
    d.rectangle([x0+20,y0+18,x0+66,y0+22],fill=(255,194,88,a))
    label='FEATURED PORTRAIT'
    draw_ls(d,(x0+20,y0+34),label,font(I_SEMI,14),(164,181,205),2.2,alpha=a)
    ix,iy,iw= x0+20,y0+68,304
    if portrait is not None:
        from PIL import ImageOps
        pane=ImageOps.fit(portrait,(iw,iw),method=Image.Resampling.LANCZOS,centering=(0.5,0.38)).convert('RGBA')
        mask=Image.new('L',pane.size,0)
        ImageDraw.Draw(mask).rounded_rectangle((1,1,iw-2,iw-2),radius=15,fill=a)
        pane.putalpha(mask)
        im.paste(pane,(ix,iy),pane)
        d=ImageDraw.Draw(im,'RGBA')
        d.rounded_rectangle([ix,iy,ix+iw,iy+iw],radius=15,outline=(226,238,255,int(a*0.70)),width=2)
    else:
        # Preserve the exact same portrait window without inventing a substitute.
        d.rounded_rectangle([ix,iy,ix+iw,iy+iw],radius=15,
                            fill=(10,16,27,int(a*0.88)),outline=(96,116,145,int(a*0.48)),width=1)
        d.line([(ix+28,iy+iw-28),(ix+iw-28,iy+28)],fill=(96,116,145,int(a*0.38)),width=2)
        draw_ls(d,(ix+28,iy+iw+18),'NO VERIFIED IMAGE',font(I_SEMI,12),(128,145,168),1.8,alpha=a)
    # Item identity is already printed in the lower-third; keep this card image-led.


def draw_finale(im, t, u):
    d = ImageDraw.Draw(im, 'RGBA')
    p = clamp((t - T_COUNT_END - 0.9) / 1.4, 0, 1)
    if p <= 0:
        return
    a = int(255 * p)
    X = 1440
    top = PEOPLE[-1]
    d.rectangle([X, 236, X + 44, 240], fill=(255, 194, 88, a))
    draw_ls(d, (X, 260), CFG.get('finale_kicker', "WORLD  #1"), font(I_SEMI, 17), (255, 194, 88), 4.4,
            alpha=a)
    lines = CFG.get('finale_lines', ["THE RICHEST", "PERSON", "ON EARTH"])
    f = font(BEBAS, 108)
    widest = max(lines, key=lambda s: tw(d, s, f, 2.0))
    while tw(d, widest, f, 2.0) > 630 and f.size > 54:
        f = font(BEBAS, f.size - 4)
    lh = f.size * 0.93
    for i, line in enumerate(lines):
        aa = int(255 * clamp((t - T_COUNT_END - 0.9 - i * 0.12) / 1.2, 0, 1))
        draw_ls(d, (X - 4, 296 + i * lh), line, f, (244, 248, 255), 2.0, alpha=aa)
    p2 = clamp((t - T_COUNT_END - 2.4) / 1.3, 0, 1)
    if p2 > 0:
        a2 = int(255 * p2)
        d.line([(X, 640), (X + 620, 640)], fill=(255, 255, 255, int(a2 * 0.20)), width=1)
        draw_ls(d, (X, 664), top['name'].upper(), font(I_BOLD, 34), (236, 242, 255), 1.2, alpha=a2)
        draw_ls(d, (X, 712), Hd.fmt_money_long(top['worth']), font(BEBAS, 86), (255, 194, 88), 1.4,
                alpha=a2)
        meta = top['source'] or top['industry']
        draw_ls(d, (X, 812), meta, font(I_MED, 17), (140, 156, 178), 2.6, alpha=int(a2 * 0.95))
    p3 = clamp((t - T_COUNT_END - 3.8) / 1.3, 0, 1)
    if p3 > 0:
        a3 = int(255 * p3)
        stats = CFG.get('finale_stats') or [
            [f"{top['worth'] / max(SECOND, 1e-6):.1f}x", "THE NEXT PERSON"],
            [Hd.fmt_money(TOTAL), f"ALL {N} COMBINED"],
        ]
        for i, (val, lab) in enumerate(stats[:2]):
            draw_ls(d, (X + i * 300, 878), val, font(BEBAS, 46), (255, 194, 88), 1.2, alpha=a3)
            draw_ls(d, (X + i * 300, 930), lab, font(I_SEMI, 12), (126, 142, 164), 2.6,
                    alpha=int(a3 * 0.9))


def draw_endcard(im, t):
    p = clamp((t - T_ENDCARD - 0.2) / 1.2, 0, 1)
    if p <= 0:
        return
    d = ImageDraw.Draw(im, 'RGBA')
    a = int(255 * p)
    # Animated ring, sweep and edge streaks give the closing card a decisive reveal.
    ep = clamp((t - T_ENDCARD - 0.15) / 2.6, 0, 1)
    cx, cy = W/2, 440
    ring_r = 370 + 36 * (1 - ease_out(ep))
    ring_a = int(a * 0.24 * (1 - 0.25 * ep))
    d.arc([cx-ring_r,cy-ring_r,cx+ring_r,cy+ring_r], start=198+t*32, end=325+t*32,
          fill=(85,178,238,ring_a), width=2)
    d.arc([cx-ring_r-18,cy-ring_r-18,cx+ring_r+18,cy+ring_r+18], start=24-t*25, end=76-t*25,
          fill=(255,194,88,int(ring_a*0.82)), width=2)
    sweep_x = -220 + (W+440) * ease_out(clamp((t-T_ENDCARD-0.25)/2.1,0,1))
    if sweep_x < W+180:
        d.polygon([(sweep_x-125,235),(sweep_x-62,235),(sweep_x+132,805),(sweep_x+69,805)],
                  fill=(93,188,255,int(a*0.12)))
        d.line([(sweep_x,245),(sweep_x+72,790)],fill=(164,224,255,int(a*0.32)),width=2)
    n = len(PEOPLE)
    total_w = 1080
    x0 = W / 2 - total_w / 2
    base_y = 792
    max_h = 168
    for i, pp in enumerate(PEOPLE):
        bx = x0 + total_w * i / n
        bw = total_w / n + 0.6
        hh = 8 + max_h * (HEIGHTS[i] - H_MIN) / (max(HEIGHTS) - H_MIN)
        col = tier_color(pp['worth'])
        reveal = ease_out(clamp((t - T_ENDCARD - 0.25 - i*0.012) / 1.05, 0, 1))
        d.rectangle([bx, base_y - hh*reveal, bx + bw, base_y], fill=col + (int(a * 0.92*reveal),))
    d.line([(x0, base_y + 1), (x0 + total_w, base_y + 1)], fill=(255, 255, 255, int(a * 0.22)), width=1)
    f5 = font(I_MED, 13)
    draw_ls(d, (x0, base_y + 13), "01", f5, (118, 134, 156), 2.0, alpha=int(a * 0.8))
    s6 = str(n)
    draw_ls(d, (x0 + total_w - tw(d, s6, f5, 2.0), base_y + 13), s6, f5, (255, 194, 88), 2.0,
            alpha=int(a * 0.9))
    s1 = CFG.get('end_title', f"{n} ENTRIES")
    f = font(BEBAS, 56)
    while tw(d, s1, f, 7) > W - 300 and f.size > 24:
        f = font(BEBAS, f.size - 2)
    draw_ls(d, (W / 2 - tw(d, s1, f, 7) / 2, 300), s1, f, (222, 232, 246), 7, alpha=a)
    s2 = CFG.get('end_total') or (Hd.fmt_money_long(TOTAL) if TOTAL < 1000 else
                                  f"{CFG.get('value_prefix', '$')}{TOTAL / 1000:.2f} TRILLION")
    f2 = font(BEBAS, 150)
    while tw(d, s2, f2, 3) > W - 300 and f2.size > 60:
        f2 = font(BEBAS, f2.size - 6)
    draw_ls(d, (W / 2 - tw(d, s2, f2, 3) / 2, 356), s2, f2, (255, 194, 88), 3, alpha=a)
    f3 = font(I_SEMI, 17)
    s3 = CFG.get('end_caption', "COMBINED VALUE")
    draw_ls(d, (W / 2 - tw(d, s3, f3, 5.0) / 2, 528), s3, f3, (136, 152, 174), 5.0, alpha=a)
    d.line([(W / 2 - 90, 592), (W / 2 + 90, 592)], fill=(255, 255, 255, int(a * 0.22)), width=1)
    f4 = font(I_MED, 14)
    s4 = CFG.get('source_note', CFG.get('source_line', ""))
    draw_ls(d, (W / 2 - tw(d, s4, f4, 2.8) / 2, 620), s4, f4, (112, 128, 150), 2.8, alpha=int(a * 0.95))
    brand = CFG.get('brand', "DATA ZED")
    fb = font(I_BOLD, 40)
    bw=tw(d,brand,fb,5); markw=62; gap=22
    left=W/2-(bw+gap+markw)/2
    draw_ls(d,(left,678),brand,fb,(238,244,255),5,alpha=int(a*0.98))
    draw_youtube_mark(d,left+bw+gap+markw/2,703,markw,int(a*0.98))
    # Closing pulse: soft horizontal highlights sweep over the ranked value ribbon.
    pulse_x = x0 + ((t-T_ENDCARD)*540) % total_w
    d.line([(pulse_x,base_y-max_h-12),(pulse_x,base_y+4)],
           fill=(232,246,255,int(a*0.42)),width=2)


def bloom(arr, strength=0.85, thresh=0.30):
    f = arr.astype(np.float32) / 255.0
    lum = f.max(axis=2, keepdims=True)
    bright = f * np.clip((lum - thresh) / (1 - thresh + 1e-4), 0, 1)
    small = bright.reshape(arr.shape[0] // 4, 4, arr.shape[1] // 4, 4, 3).mean(axis=(1, 3))
    im = Image.fromarray((np.clip(small, 0, 1) * 255).astype(np.uint8))
    im = im.filter(ImageFilter.GaussianBlur(6))
    im = im.filter(ImageFilter.GaussianBlur(6))
    up = np.array(im.resize((arr.shape[1], arr.shape[0]), Image.BILINEAR), np.float32) / 255.0
    out = f + up * strength
    return np.clip(out, 0, 1)


def render(t, fi=0):
    if t >= T_ENDCARD:
        return render_end(t)
    u = u_of_t(t)
    cam = scene_cam(t, u)
    far = cam.pos + np.array([cam.fwd[0], 0, cam.fwd[2]]) * 8000
    hy = float(cam.project(np.array([far]))[0][1])
    bg = E.background(cam, hy)
    im = Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8), 'RGB')
    E.draw_floor(im, cam, u)

    order = []
    for i in range(len(PEOPLE)):
        vz = cam.view([bar_base(i)])[0][2]
        if vz < 9.5 or vz > 190:
            continue
        order.append((vz, i))
    order.sort(reverse=True)

    em = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    E.draw_ground_fx(im, em, cam, u, order)

    if t < T_INTRO:
        # A single rounded hero-column rises in the opening; the montage hints at
        # the range without prematurely revealing the count.
        for vz, i in reversed(order):
            if i != 0:
                continue
            rv = smoothstep((t - 1.1) / 5.8)
            if rv > 0.002:
                E.draw_one_bar(im, em, cam, i, HEIGHTS[i] * rv, u, vz)
    else:
        E.draw_bars(im, cam, u, em, order)

    im.paste(em, (0, 0), em)
    arr = np.array(im.convert('RGB'), np.float32) * E.vignette()

    sf = 1.0
    if t < 8.0:
        sf = 0.10 + 0.90 * smoothstep((t - 4.4) / 2.5)
    arr = arr * sf
    arr = bloom(arr) * 255.0

    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), 'RGB')

    # ---- typography on top of the graded scene
    if t < T_INTRO:
        intro_rank = clamp((t - 8.4) / 1.0, 0, 1)
        clear_before_countdown = 1 - smoothstep((t - (T_INTRO - 0.65)) / 0.65)
        a = int(255 * intro_rank * clear_before_countdown)
        if a > 0:
            Hd.draw_topbar(out, PEOPLE[0], 1, alpha=a, total=N)
    elif t < T_COUNT_END:
        active_index, phase, active_alpha = active_rank_state(t)
        idx = active_index + 1
        p = PEOPLE[active_index]
        Hd.draw_topbar(out, p, idx, alpha=active_alpha, total=N)
        Hd.draw_card(out, p, alpha=active_alpha, appear=1.0)
        Hd.draw_scale(out, p['worth'], alpha=int(235 * active_alpha / 255))
        Hd.draw_progress(out, (idx - 1) / max(1, N - 1), tier_color(p['worth']),
                         alpha=int(220 * active_alpha / 255))
        Hd.draw_plate(out, cam, p, idx, alpha=active_alpha, scale=1.0)
        draw_feature_portrait(out, active_index, alpha=active_alpha)
    else:
        p = PEOPLE[-1]
        # Rank-specific topbar, plate and portrait have all cleared at the
        # boundary. Only the finale progress trace may remain on screen.
        pr = int(220 * (1 - clamp((t - T_FINALE_END) / 1.0, 0, 1)))
        Hd.draw_progress(out, 1.0, tier_color(p['worth']), alpha=pr)

    if t < T_INTRO:
        draw_intro_motion(out, t)
    if t >= T_INTRO and t < T_COUNT_END:
        idx = int(clamp(int(u)+1,1,N))
        draw_countdown_motion(out,t,u,idx,tier_color(PEOPLE[idx-1]['worth']))
    draw_title(out, t)
    if t >= T_COUNT_END:
        draw_finale(out, t, u)
    if t < T_INTRO:
        draw_boundary_sweep(out,t,11.15,12.0,(94,205,255))
    elif T_ENDCARD-1.25 <= t < T_ENDCARD:
        draw_boundary_sweep(out,t,T_ENDCARD-1.25,T_ENDCARD,(255,194,88))

    a = np.array(out, np.float32)
    a = a + _GRAIN[fi % len(_GRAIN)] * 0.8
    a = np.clip(a, 0, 255)
    if t > T_ENDCARD - 2.2:
        k = clamp((t - (T_ENDCARD - 2.2)) / 2.0, 0, 1)
        a = a * (1 - k)
    return a.astype(np.uint8)


def render_end(t):
    im = Image.new('RGB', (W, H), (2, 3, 7))
    # soft radial glow behind
    g = Image.new('RGB', (W, H), (2, 3, 7))
    dd = ImageDraw.Draw(g, 'RGBA')
    dd.ellipse([W / 2 - 700, 420 - 420, W / 2 + 700, 420 + 420], fill=(16, 34, 58, 90))
    g = g.filter(ImageFilter.GaussianBlur(160))
    im = g
    draw_endcard(im, t)
    a = np.array(im, np.float32)
    a = a + _GRAIN[0] * 0.8
    a = np.clip(a, 0, 255)
    if t > 178.4:
        a = a * (1.0 - clamp((t - 178.4) / 1.45, 0, 1))
    return a.astype(np.uint8)
