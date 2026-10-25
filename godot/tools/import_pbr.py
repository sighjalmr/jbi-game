"""Copy the PBR texture sets made for the Unreal version into godot/textures/pbr/.

    python godot/tools/import_pbr.py <dir with *_BC.png, *_N.png, *_R.png>

The source normals are DirectX style (green down); Godot wants OpenGL style, so green is flipped.
Base colour and roughness are stored as JPEG to keep the repo small.
"""
import os, sys
import numpy as np
from PIL import Image

SRC = sys.argv[1]
OUT = os.path.join(os.path.dirname(__file__), '..', 'textures', 'pbr')
os.makedirs(OUT, exist_ok=True)
SETS = ['panel', 'khrush', 'public', 'garage', 'industrial', 'roof', 'asphalt', 'paving', 'grass', 'forest', 'dirt', 'ballast']
for s in SETS:
    Image.open(f'{SRC}/{s}_BC.png').convert('RGB').save(f'{OUT}/{s}_albedo.jpg', quality=90)
    Image.open(f'{SRC}/{s}_R.png').convert('L').save(f'{OUT}/{s}_rough.jpg', quality=90)
    n = np.array(Image.open(f'{SRC}/{s}_N.png').convert('RGB'))
    n[..., 1] = 255 - n[..., 1]
    Image.fromarray(n).save(f'{OUT}/{s}_normal.png', optimize=True)
print('ok')
