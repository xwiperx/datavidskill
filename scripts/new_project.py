#!/usr/bin/env python3
"""Create a datavid project folder with config.json and data.json templates."""
import argparse, json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(os.path.dirname(HERE), 'templates')

ap = argparse.ArgumentParser()
ap.add_argument('path')
a = ap.parse_args()
dst = os.path.abspath(a.path)
os.makedirs(dst, exist_ok=True)
for name in ('config.json', 'data.json'):
    src = os.path.join(TPL, name)
    out = os.path.join(dst, name)
    if not os.path.exists(out):
        shutil.copy(src, out)
print(f'project ready: {dst}')
print('next: fill data.json (items sorted ascending is automatic), edit config.json, then')
print(f'  python3 {os.path.join(HERE, "render.py")} --project {dst} --stills 3 20 40')
