import json
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
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
import audio_cache
import fetch_images
import scene
import validate_project
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

    def test_endcard_handles_zero_height_span(self):
        image = Image.new('RGBA', (E.W, E.H), (0, 0, 0, 255))
        with patch.object(scene, 'PEOPLE', [scene.PEOPLE[0]]), \
             patch.object(scene, 'HEIGHTS', [scene.H_MIN]):
            scene.draw_endcard(image, scene.T_ENDCARD + 2.0)
        self.assertEqual(image.size, (E.W, E.H))

    def test_audio_only_source_invalidates_normalized_score(self):
        with tempfile.TemporaryDirectory() as td:
            outdir = Path(td) / 'out'
            outdir.mkdir()
            normalized = outdir / 'score.wav'
            import wave
            with wave.open(str(normalized), 'wb') as wav:
                wav.setnchannels(2)
                wav.setsampwidth(2)
                wav.setframerate(44100)
                wav.writeframes(b'\x00\x00\x00\x00' * 44100)
            audio_cache.publish_raw_score(outdir, b'\x01\x00\x01\x00' * 44100,
                                          expected_frames=44100)
            self.assertFalse(normalized.exists())
            with patch.object(build, 'OUT', str(outdir)), patch.object(E, 'DUR', 1.0):
                rebuilt = build._ensure_score()
            self.assertTrue(Path(rebuilt).exists())
            with wave.open(rebuilt, 'rb') as wav:
                self.assertEqual(wav.getnframes(), 44100)

    def test_engine_initializes_with_all_zero_values(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = json.loads((PROJECT / 'config.json').read_text())
            (root / 'config.json').write_text(json.dumps(config))
            (root / 'data.json').write_text(json.dumps({'items': [
                {'name': f'Item {i}', 'value': 0} for i in range(3)]}))
            code = ('import sys;sys.path.insert(0,sys.argv[1]);import engine;'
                    'assert engine.MAXW == 0 and len(engine.HEIGHTS) == 3;'
                    'assert engine.tier_color(0) == engine.TIER[0]')
            result = subprocess.run([sys.executable, '-c', code,
                                     str(REPO/'scripts'/'datavid')],
                                    env=dict(os.environ, DATAVID_PROJECT=td),
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_builder_rejects_invalid_override_values(self):
        script = REPO / 'projects' / 'richest-2026' / 'source' / 'build_data.py'
        with tempfile.TemporaryDirectory() as td:
            source = script.parent
            for name in ('forbes2026.json', 'data_overrides.json'):
                shutil.copy2(source / name, Path(td) / name)
            code = r'''import json, pathlib, sys
sys.path.insert(0, sys.argv[2])
import build_data
build_data.HERE = pathlib.Path(sys.argv[1])
base = json.loads((build_data.HERE/'data_overrides.json').read_text())
for invalid in (float('nan'), float('inf'), -1, 'not-a-number', True):
    doc = json.loads(json.dumps(base))
    doc.setdefault('rank_overrides', {}).setdefault('1', {})['value'] = invalid
    (build_data.HERE/'data_overrides.json').write_text(json.dumps(doc, allow_nan=True))
    try: build_data.build_data()
    except ValueError as exc: assert 'finite and non-negative' in str(exc), exc
    else: raise AssertionError(f'accepted invalid override {invalid!r}')
'''
            result = subprocess.run([sys.executable, '-c', code, td, str(script.parent)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_image_directory_must_stay_inside_project(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'project'
            root.mkdir()
            self.assertEqual(fetch_images.safe_image_directory(root, 'assets/entities'),
                             (root / 'assets/entities').resolve())
            for unsafe in ('../outside', str(Path(td) / 'absolute')):
                with self.subTest(unsafe=unsafe), self.assertRaises(ValueError):
                    fetch_images.safe_image_directory(root, unsafe)

    def test_validator_rejects_absolute_and_escaping_image_paths(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root = base / 'project'
            root.mkdir()
            (root / 'config.json').write_text('{"scale_max":10}')
            (root / 'data.json').write_text('{"items":[{"name":"A","value":1}]}')
            outside = base / 'outside.jpg'
            outside.write_bytes(b'outside')
            for local in ('../outside.jpg', str(outside)):
                (root / 'image_sources.json').write_text(json.dumps([
                    {'rank': 1, 'name': 'A', 'local_path': local,
                     'source_url': 'https://example.test/source', 'license': 'CC0'}]))
                errors, _ = validate_project.audit(root)
                self.assertTrue(any('must be relative and stay inside' in e for e in errors), errors)
            self.assertTrue(outside.exists())

    def test_validator_reports_malformed_rows_without_traceback(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'config.json').write_text('{"scale_max":10}')
            (root / 'data.json').write_text('{"items":[null]}')
            (root / 'image_sources.json').write_text('[null]')
            errors, _ = validate_project.audit(root)
            self.assertTrue(any('item 1 must be a JSON object' in e for e in errors))
            self.assertTrue(any('manifest row 1 must be a JSON object' in e for e in errors))

    def test_validator_rejects_boolean_as_numeric_value(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'config.json').write_text('{"scale_max":10}')
            (root / 'data.json').write_text('{"items":[{"name":"A","value":true}]}')
            (root / 'image_sources.json').write_text('[{"rank":1,"name":"A"}]')
            errors, _ = validate_project.audit(root)
            self.assertTrue(any('item 1 has an invalid value' in e for e in errors), errors)

    def test_packaged_skill_matches_current_source_tree(self):
        archive = REPO / 'dist' / 'datavid.skill'
        if not archive.exists():
            self.skipTest('distribution archive is not built yet')
        expected = [REPO / 'SKILL.md']
        for folder in ('scripts', 'references', 'templates'):
            expected.extend(path for path in (REPO / folder).rglob('*')
                            if path.is_file() and '__pycache__' not in path.parts and
                            path.suffix != '.pyc')
        with zipfile.ZipFile(archive) as zf:
            entries = set(zf.namelist())
            for source in expected:
                relative = source.relative_to(REPO).as_posix()
                self.assertIn(relative, entries, f'missing packaged file: {relative}')
                self.assertEqual(zf.read(relative), source.read_bytes(),
                                 f'stale packaged file: {relative}')

    def test_reference_dataset_rebuild_check_is_non_destructive_and_passes(self):
        script = REPO / 'projects' / 'richest-2026' / 'source' / 'build_data.py'
        subprocess.run([sys.executable, str(script), '--check'], cwd=REPO, check=True,
                       capture_output=True, text=True)

    def test_smoke_runner_refuses_to_overwrite_existing_output(self):
        sys.path.insert(0, str(REPO / 'scripts' / 'datavid'))
        import ci_smoke
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / 'smoke.mp4'
            output.write_bytes(b'preserve')
            report_dir = Path(td) / 'reports'
            code = ci_smoke.main(['--output', str(output), '--report-dir', str(report_dir)])
            self.assertEqual(code, 2)
            self.assertEqual(output.read_bytes(), b'preserve')


if __name__ == '__main__':
    unittest.main()
