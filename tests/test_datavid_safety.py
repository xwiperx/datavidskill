import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
PROJECT = REPO / 'projects' / 'richest-2026'
os.environ['DATAVID_PROJECT'] = str(PROJECT)
import sys
sys.path.insert(0, str(REPO / 'scripts' / 'datavid'))
import engine as E
import hud
import build
from PIL import Image, ImageDraw


class RenderSafetyTests(unittest.TestCase):
    def test_projective_quad_hits_all_four_corners(self):
        src = Image.new('RGBA', (100, 100), (0, 0, 0, 255))
        d = ImageDraw.Draw(src)
        d.rectangle((0, 0, 49, 49), fill=(255, 0, 0, 255))
        d.rectangle((50, 0, 99, 49), fill=(0, 255, 0, 255))
        d.rectangle((50, 50, 99, 99), fill=(0, 0, 255, 255))
        d.rectangle((0, 50, 49, 99), fill=(255, 255, 0, 255))
        out = Image.new('RGB', (220, 190), (5, 5, 5))
        quad = [(20, 15), (190, 35), (165, 165), (40, 145)]
        E.paste_quad(out, src, quad, 255)
        samples = [(42, 34), (166, 49), (150, 141), (54, 126)]
        colors = [out.getpixel(p) for p in samples]
        for actual, expected in zip(colors, [(255,0,0),(0,255,0),(0,0,255),(255,255,0)]):
            self.assertLess(sum(abs(a-b) for a,b in zip(actual, expected)), 80)

    def test_long_name_is_bounded_and_ellipsized(self):
        draw = ImageDraw.Draw(Image.new('RGB', (800, 100)))
        text, face = hud.fit_name(draw, 'A VERY EXTREMELY LONG HYPOTHETICAL DISPLAY NAME ' * 5,
                                  max_width=180, start_size=50, min_size=24)
        self.assertLessEqual(E.tw(draw, text, face, 0), 180)
        self.assertTrue(text.endswith('…'))

    def test_scale_range_exceeds_data_max(self):
        configured = float(E.cfg('scale_max', 0) or 0)
        dynamic = max(configured, __import__('math').ceil(E.MAXW / 100.0) * 100.0)
        self.assertGreaterEqual(dynamic, E.MAXW)
        self.assertEqual(configured, 900)

    def test_existing_final_is_never_selected_for_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / 'video.mp4'
            existing.write_bytes(b'preserve')
            with patch.object(build, 'OUT', tmp), patch.object(E, 'cfg', return_value='video.mp4'):
                chosen = Path(build._next_final_path())
            self.assertNotEqual(chosen, existing)
            self.assertEqual(chosen.name, 'video_v2.mp4')
            self.assertEqual(existing.read_bytes(), b'preserve')

    def test_segment_validator_rejects_truncated_and_accepts_full(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test.mp4'
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i',
                            'color=c=blue:s=1920x1080:r=30:d=0.2', '-frames:v', '6',
                            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(path)], check=True)
            self.assertTrue(build.valid_segment(str(path), 6))
            self.assertFalse(build.valid_segment(str(path), 7))
            path.write_bytes(b'partial')
            self.assertFalse(build.valid_segment(str(path), 6))

    def test_empty_items_fail_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = json.loads((PROJECT / 'config.json').read_text())
            (Path(tmp) / 'config.json').write_text(json.dumps(cfg))
            (Path(tmp) / 'data.json').write_text('{"items": []}')
            code = 'import sys;sys.path.insert(0,sys.argv[1]);import engine'
            p = subprocess.run([sys.executable, '-c', code, str(REPO/'scripts'/'datavid')],
                               env=dict(os.environ, DATAVID_PROJECT=tmp), capture_output=True, text=True)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn('non-empty items list', p.stderr)


if __name__ == '__main__':
    unittest.main()
