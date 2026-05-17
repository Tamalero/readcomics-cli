#!/usr/bin/env python3
"""Generate docs/icon.ico — Catppuccin Mocha comic-book icon used by the Windows EXE."""
import os

try:
    from PIL import Image, ImageDraw

    sizes = [16, 32, 48, 64, 128, 256]
    frames = []
    for size in sizes:
        img = Image.new('RGBA', (size, size), (30, 30, 46, 255))   # Catppuccin base
        d   = ImageDraw.Draw(img)
        m   = max(1, size // 8)
        r   = max(1, size // 6)
        # Comic page background
        d.rounded_rectangle([m, m, size - m, size - m], radius=r, fill=(137, 180, 250, 255))
        # Dark inner area (open book)
        i = size // 4
        d.rectangle([i, i, size - i, size - i + size // 8], fill=(30, 30, 46, 255))
        # Three text lines
        lm, lw, lh = size // 3, size // 3, max(1, size // 16)
        for row in range(3):
            y = i + size // 6 + row * (lh + max(1, size // 20))
            d.rectangle([lm, y, lm + lw, y + lh], fill=(137, 180, 250, 200))
        frames.append(img)

    os.makedirs('docs', exist_ok=True)
    frames[0].save('docs/icon.ico', format='ICO',
                   sizes=[(s, s) for s in sizes],
                   append_images=frames[1:])
    print('Icon saved: docs/icon.ico')

except Exception as exc:
    print(f'Warning: icon generation failed ({exc}) — EXE will use default icon')
