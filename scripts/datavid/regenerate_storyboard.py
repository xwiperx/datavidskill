#!/usr/bin/env python3
"""Render current rank holds and motion boards (stills only; never encodes a full MP4)."""
import argparse
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    args = parser.parse_args()
    project = Path(args.project).resolve()
    os.environ['DATAVID_PROJECT'] = str(project)
    import engine as E
    import scene as S
    from PIL import Image

    out = project / 'storyboard'
    out.mkdir(parents=True, exist_ok=True)
    try:
        small_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 16)
    except OSError:
        small_font = ImageFont.load_default()
    holds = []
    frame_paths = {}
    for rank in range(1, E.N + 1):
        t = E.T_INTRO + (rank - 1 + 0.68) * E.PER_BAR
        arr = S.render(t, int(round(t * E.FPS)))
        frame = Image.fromarray(arr)
        holds.append((rank, E.PEOPLE[rank-1]['name'], E.PEOPLE[rank-1]['worth'], frame))
        if rank in (35, 59, 62, 63, 75, 91, E.N):
            frame_paths[rank] = frame.copy()
    cw, ch, label_h, cols = 352, 198, 28, 5
    for sheet in range(4):
        rows = holds[sheet*25:(sheet+1)*25]
        board = Image.new('RGB', (cw*cols, (ch+label_h)*5), (8, 12, 20))
        d = ImageDraw.Draw(board)
        for j, (rank, name, value, frame) in enumerate(rows):
            x, y = (j % cols) * cw, (j // cols) * (ch+label_h)
            thumb = frame.resize((cw, ch), Image.Resampling.LANCZOS)
            board.paste(thumb, (x, y))
            d.rectangle((x, y+ch, x+cw-1, y+ch+label_h-1), fill=(6, 9, 15))
            d.text((x+7, y+ch+5), f'#{rank:03d}  {name[:31]}  ·  ${value:,.1f}B',
                   font=small_font, fill=(225, 234, 247))
        board.save(out / f'countdown-{sheet+1:02d}.jpg', quality=90, optimize=True)
    # Single stills and motion contact sheets used for review.
    for rank, frame in frame_paths.items():
        name = 'rank-059.jpg' if rank == 59 else f'rank-{rank:03d}.jpg'
        frame.save(out / name, quality=92, optimize=True)
    intro = Image.fromarray(S.render(4.8, int(4.8*E.FPS)))
    intro.save(out / 'intro.jpg', quality=92, optimize=True)
    end_t = min(E.DUR - 0.05, E.T_ENDCARD + 2.5)
    end = Image.fromarray(S.render(end_t, int(end_t*E.FPS)))
    end.save(out / 'endcard.jpg', quality=92, optimize=True)

    def sequence(name, times):
        frames=[]
        for i, t in enumerate(times):
            t=max(0.0,min(E.DUR-0.05,t))
            frames.append((t,Image.fromarray(S.render(t,int(t*E.FPS)))))
        w,h=480,270; label=32; cols=3; rows=(len(frames)+cols-1)//cols
        board=Image.new('RGB',(w*cols,(h+label)*rows),(7,10,17)); d=ImageDraw.Draw(board)
        for i,(t,frame) in enumerate(frames):
            x=(i%cols)*w; y=(i//cols)*(h+label)
            board.paste(frame.resize((w,h),Image.Resampling.LANCZOS),(x,y))
            d.text((x+10,y+h+6),f'{t:.2f}s',font=small_font,fill=(224,232,244))
        board.save(out/name,quality=92,optimize=True)
    sequence('intro-motion-sequence.jpg',[0.8,2.2,4.8,6.5,8.4,10.5])
    sequence('outro-motion-sequence.jpg',[E.T_COUNT_END+1.5,E.T_COUNT_END+5.0,
              E.T_FINALE_END+1.0,E.T_ENDCARD+0.3,E.T_ENDCARD+2.5,E.DUR-0.05])
    growth_times=[]
    for rank in (1, 10, 50, 90, 91, 95, 100):
        start=E.T_INTRO+(rank-1)*E.PER_BAR
        for offset in (0.04, E.PER_BAR*float(E.cfg('growth_fraction',0.46)), E.PER_BAR-0.04):
            frame=int(round((start+offset)*E.FPS))
            growth_times.append(frame/E.FPS)
    sequence('countdown-growth-sequence.jpg',growth_times)
    boundary_times=[]
    for next_rank in (2, 11, 91, 100):
        boundary=E.T_INTRO+(next_rank-1)*E.PER_BAR
        center=int(round(boundary*E.FPS))
        boundary_times.extend(((center-1)/E.FPS,center/E.FPS,(center+1)/E.FPS))
    center=int(round(E.T_COUNT_END*E.FPS))
    boundary_times.extend(((center-1)/E.FPS,center/E.FPS,(center+1)/E.FPS))
    sequence('rank-boundary-sequence.jpg',boundary_times)

    manifest=E.IMAGE_MANIFEST
    cover=sum(bool(r.get('local_path')) for r in manifest)
    missing=[i+1 for i,r in enumerate(manifest) if not r.get('local_path')]
    lines=['# استوری‌بورد تازهٔ «ثروتمندترین افراد جهان» — Data Zed','',
           'این پیش‌نمایش پس از ممیزی تازهٔ داده/تصویر، HUD، projection و پایان‌کارت بازتولید شده است. تماس‌شیت‌های ۱ تا ۱۰۰ فریم مکث واقعیِ نسخهٔ فعلی‌اند؛ sequenceها نمونه‌های ثابت از موشن‌اند و هنوز ویدیوی کامل نیستند.','',
           '## مقدمه و هویت بصری','',
           'نام Data Zed و نشان YouTube زیر عنوان RICHEST قرار دارد. سطر توضیحی «one hundred people - one number each» عمداً درج نشده است. ستون‌ها مات، اشباع و نرم‌لبه‌اند؛ عنوان، عددها و عکس‌ها در نواحی مجزا نگه داشته شده‌اند.','',
           '![فریم مقدمه](intro.jpg)','',
           '![توالی فریم‌های مقدمه](intro-motion-sequence.jpg)','',
           'نمونهٔ رشد در سه لحظه (شروع، انتهای rise، مکث) برای رتبه‌های آغازین، میانی، مرز فصل‌ها و ده رتبهٔ پایانی؛ همچنین سه‌فریم قبل/لحظه/بعد از چند مرز رتبه و انتقال شمارش به اوج در این تماس‌شیت‌ها آمده است.','',
           '![توالی رشد ستون‌ها](countdown-growth-sequence.jpg)','',
           '![سه‌فریم‌های مرز رتبه و انتقال](rank-boundary-sequence.jpg)','',
           '## مکث‌های رتبه‌ها','',
           'هر رتبه یک رشد مستقل دارد؛ فصل‌بندی ۱۰تایی تا رتبهٔ ۹۰ و رشدهای مجزای ۹۱ تا ۱۰۰ حفظ شده‌اند. نوار پیشرفت اکنون در شیار پایین مستقل از lower-third است؛ نام‌های بلند با کوچک‌سازی و در صورت لزوم ellipsis مهار می‌شوند.','']
    for s in range(1,5):
        lo=(s-1)*25+1; hi=min(s*25,E.N)
        lines += [f'### رتبه‌های {lo} تا {hi}','',f'![تماس‌شیت رتبه‌های {lo} تا {hi}](countdown-{s:02d}.jpg)','',
                  '| رتبه | زمان مکث (ثانیه) | نام | ارزش تخمینی |','|---:|---:|---|---:|']
        for rank in range(lo,hi+1):
            t=E.T_INTRO+(rank-1+0.68)*E.PER_BAR
            p=E.PEOPLE[rank-1]
            lines.append(f'| {rank} | {t:.2f} | {p["name"]} | ${p["worth"]:,.1f}B |')
        lines.append('')
    lines += ['## نمونه‌ها و پایان','',
              '![رتبهٔ ۵۹ با چهرهٔ متناظر در قاب ثابت](rank-059.jpg)','',
              '![رتبهٔ ۳۵ با قاب خالی پس از حذف mismatch تصویر](rank-035.jpg)','',
              '![کارت پایانی با Data Zed و نشان YouTube](endcard.jpg)','',
              '![توالی اوج، transition و پایان‌کارت](outro-motion-sequence.jpg)','',
              '## پوشش تصویری و وضعیت تأیید','',
              f'پس از حذف هشت موردی که از نظر هویت دقیق یا کیفیت پرتره قابل اتکا نبودند، {cover} فایل محلیِ دارای منبع/مجوز در manifest باقی است و {len(missing)} قاب عمداً خالی است. این عدد، «تأیید مستقل وبیِ هر تصویر باقی‌مانده» نیست؛ تصاویر با contact sheet بررسی شدند و موارد مشکوک fail-closed حذف شدند. برای تأیید مستقل تمام {cover} منبع باقی‌مانده، بازبینی تک‌به‌تک source pageها هنوز لازم است.','',
              'مقادیر داده ۱۰۰ مورد به ترتیب صعودی‌اند و ساختار/مجموع با validator بررسی می‌شود؛ راستی‌آزمایی مستقل تمام برآوردهای ثروت در منبع اصلی بخشی از این پیش‌نمایش نیست. حداکثر مقدار داده 839B و سقف نمایشی مقیاس 900B است.','',
              'این storyboard نسخهٔ تازه‌ای است و تأیید قبلی به آن منتقل نمی‌شود. رندر کامل MP4 تا تأیید صریح همین storyboard و انتخاب کیفیت(ها) آغاز نمی‌شود.']
    (out/'storyboard.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(f'Wrote 4 contact sheets for {E.N} ranks; eligible local assets={cover}, blank={len(missing)}')
    print(f'TIMING duration={E.DUR}s fps={E.FPS} frames={E.NF} rank_hold={E.PER_BAR:.4f}s')


if __name__=='__main__':
    main()
