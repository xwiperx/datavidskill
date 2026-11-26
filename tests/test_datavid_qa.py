import shutil
import tempfile
from unittest.mock import patch
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(REPO / 'scripts' / 'datavid'))
import qa_media
import qa_visual
import qa_compare


class VisualQATests(unittest.TestCase):
    def test_layout_overlap_is_reported(self):
        boxes = [
            {'name': 'title', 'x': 10, 'y': 10, 'width': 100, 'height': 40},
            {'name': 'rank', 'x': 90, 'y': 20, 'width': 50, 'height': 50},
        ]
        errors, overlaps = qa_visual.find_box_collisions(boxes)
        self.assertFalse(errors)
        self.assertEqual(len(overlaps), 1)
        self.assertEqual(overlaps[0]['first'], 'title')

    def test_disjoint_layout_boxes_pass(self):
        boxes = [
            {'name': 'title', 'x': 0, 'y': 0, 'width': 100, 'height': 40},
            {'name': 'caption', 'x': 0, 'y': 50, 'width': 100, 'height': 20},
        ]
        errors, overlaps = qa_visual.find_box_collisions(boxes)
        self.assertEqual((errors, overlaps), ([], []))

    def test_non_finite_layout_geometry_fails_closed(self):
        boxes = [{'name': 'title', 'x': float('nan'), 'y': 0,
                  'width': 20, 'height': 10}]
        errors, overlaps = qa_visual.find_box_collisions(boxes)
        self.assertEqual(overlaps, [])
        self.assertTrue(any(row['type'] == 'invalid_box_geometry' for row in errors))
        with tempfile.TemporaryDirectory() as td:
            layout = Path(td) / 'layout.json'
            layout.write_text('{"width":100,"height":100,"boxes":[{"name":"title","x":NaN,"y":0,"width":20,"height":10}]}')
            report = qa_visual.validate_layout(layout)
        self.assertFalse(report['passed'])

    def test_invalid_canvas_dimensions_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            layout = Path(td) / 'layout.json'
            layout.write_text('{"width":Infinity,"height":100,"boxes":[]}')
            report = qa_visual.validate_layout(layout)
        self.assertFalse(report['passed'])
        self.assertEqual(report['errors'][0]['type'], 'invalid_canvas_dimensions')

    def test_allowed_overlap_is_not_reported(self):
        boxes = [
            {'name': 'background', 'x': 0, 'y': 0, 'width': 100, 'height': 100,
             'allow_overlap_with': ['title']},
            {'name': 'title', 'x': 10, 'y': 10, 'width': 80, 'height': 30},
        ]
        self.assertFalse(qa_visual.find_box_collisions(boxes)[1])

    @unittest.skipUnless(shutil.which('tesseract'), 'Tesseract OCR is not installed')
    def test_ocr_finds_words_in_rasterized_text(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'text.png'
            im = Image.new('RGB', (700, 180), 'white')
            draw = ImageDraw.Draw(im)
            font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
            face = ImageFont.truetype(font_path, 76) if Path(font_path).exists() else ImageFont.load_default()
            draw.text((25, 35), 'HELLO DATAVID', font=face, fill='black')
            im.save(path)
            words, overlaps = qa_visual._ocr_image(path, psm=6, min_conf=20)
            self.assertGreaterEqual(len(words), 2)
            self.assertFalse(overlaps)

    def test_ocr_overlap_is_review_candidate_unless_strict(self):
        words = [{'text': 'SMALL', 'x': 10, 'y': 10, 'width': 60, 'height': 12,
                  'confidence': 90}]
        collision = {'first': 'SMALL', 'second': 'LARGE', 'intersection_ratio': 0.4,
                     'boxes': [words[0], {'text': 'LARGE', 'x': 20, 'y': 8,
                                          'width': 80, 'height': 40, 'confidence': 90}]}
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'frame.png'
            Image.new('RGB', (120, 60), 'black').save(path)
            with patch.object(qa_visual, '_ocr_image', return_value=(words, [collision])):
                review = qa_visual.inspect_media(image=path)
            with patch.object(qa_visual, '_ocr_image', return_value=(words, [collision])):
                strict = qa_visual.inspect_media(image=path, strict_ocr_overlap=True)
        self.assertTrue(review['passed'])
        self.assertEqual(len(review['overlap_candidates']), 1)
        self.assertFalse(strict['passed'])


class MediaQATests(unittest.TestCase):
    def test_black_run_is_detected(self):
        frames = np.full((40, 20, 30), 80, dtype=np.uint8)
        frames[10:14] = 0
        result = qa_media.analyze_luma_frames(frames, 30, edge_ignore_seconds=0,
                                               freeze_min_seconds=2.0)
        self.assertEqual(result['black_runs'][0]['frame_count'], 4)

    def test_reviewed_black_fade_range_is_reported_not_hidden(self):
        frames = np.full((40, 20, 30), 80, dtype=np.uint8)
        frames[10:14] = 0
        result = qa_media.analyze_luma_frames(frames, 10, edge_ignore_seconds=0,
                                               allow_black_ranges=[(0.9, 1.5)])
        self.assertFalse(result['black_runs'])
        self.assertEqual(result['allowed_black_runs'][0]['frame_count'], 4)

    def test_slow_motion_is_candidate_but_not_strict_freeze(self):
        frames = np.full((45, 20, 30), 90, dtype=np.uint8)
        for i in range(len(frames)):
            frames[i, 0, 0] = 90 + i
        result = qa_media.analyze_luma_frames(frames, 30, edge_ignore_seconds=0,
                                               freeze_min_seconds=0.8)
        self.assertFalse(result['freeze_runs'])
        self.assertTrue(result['freeze_candidates'])

    def test_long_freeze_is_detected_but_dynamic_frames_pass(self):
        static = np.full((45, 20, 30), 90, dtype=np.uint8)
        result = qa_media.analyze_luma_frames(static, 30, edge_ignore_seconds=0,
                                               freeze_min_seconds=0.8)
        self.assertTrue(result['freeze_runs'])
        dynamic = np.stack([np.full((20, 30), i * 3, dtype=np.uint8) for i in range(45)])
        self.assertFalse(qa_media.analyze_luma_frames(dynamic, 30, edge_ignore_seconds=0,
                                                       freeze_min_seconds=0.8)['freeze_runs'])

    def test_cadence_detects_duplicate_and_gap_timestamps(self):
        times = [0.0, 1/30, 2/30, 2/30, 5/30]
        issues = qa_media.cadence_issues(times, expected_fps=30)
        self.assertTrue(any(x['type'] == 'non_monotonic_pts' for x in issues))
        self.assertTrue(any(x['type'] == 'irregular_frame_cadence' for x in issues))

    def test_jump_candidate_is_reported(self):
        frames = np.zeros((5, 20, 30), dtype=np.uint8)
        frames[3:] = 255
        result = qa_media.analyze_luma_frames(frames, 30, edge_ignore_seconds=0,
                                               freeze_min_seconds=4.0, jump_delta=20)
        self.assertTrue(result['jumps'])


class ComparisonTests(unittest.TestCase):
    def test_identical_images_have_zero_error(self):
        image = np.full((32, 32, 3), 100, dtype=np.uint8)
        metrics = qa_compare.compare_arrays(image, image.copy())
        self.assertEqual(metrics['mae'], 0)
        self.assertEqual(metrics['ssim_8x8'], 1)
        self.assertEqual(metrics['changed_fraction'], 0)

    def test_changed_region_is_detected(self):
        a = np.zeros((32, 32, 3), dtype=np.uint8)
        b = a.copy()
        b[8:24, 8:24] = 255
        metrics = qa_compare.compare_arrays(a, b)
        self.assertGreater(metrics['mae'], 0)
        self.assertLess(metrics['ssim_8x8'], 1)
        self.assertGreater(metrics['changed_fraction'], 0)

    def test_empty_or_non_finite_fractions_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'at least one'):
            qa_compare.normalize_fractions(())
        with self.assertRaisesRegex(ValueError, 'finite'):
            qa_compare.normalize_fractions((float('nan'),))
        with self.assertRaisesRegex(ValueError, 'finite'):
            qa_compare.normalize_fractions((float('inf'),))

    def test_cli_empty_fraction_list_fails_before_opening_video(self):
        result = qa_compare.main(['missing-reference.mp4', 'missing-candidate.mp4',
                                  '--fractions', '', '--report', 'unused.json'])
        self.assertEqual(result, 2)


if __name__ == '__main__':
    unittest.main()
