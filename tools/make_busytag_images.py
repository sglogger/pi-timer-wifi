"""Renders the Busy Tag display pictures in static/busytag/ (240x280 PNG, one per timer phase)
and the overview images/busytag-display.png used in the documentation.

Needs Pillow and a bold TrueType font; only run on a development machine when colours or
labels change. The server uploads the committed files and never runs this script.
Usage: python tools/make_busytag_images.py [FONT.ttf]
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from ui_config import COLORS, LABELS, OVERDUE_DIM  # noqa: E402

SIZE = (240, 280)
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUT = os.path.join(ROOT, 'static', 'busytag')
ORDER = ('off', 'green', 'yellow', 'orange', 'red', 'overdue')
FONT = sys.argv[1] if len(sys.argv) > 1 else '/System/Library/Fonts/Supplemental/Arial Bold.ttf'


def fitted(draw, lines, width, start):
    size = start
    while True:
        font = ImageFont.truetype(FONT, size)
        if all(draw.textlength(line, font=font) <= width for line in lines):
            return font
        size -= 2


def render(name, lines, background, foreground):
    image = Image.new('RGB', SIZE, background)
    draw = ImageDraw.Draw(image)
    font = fitted(draw, lines, SIZE[0] - 24, 80)
    boxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
    gap = font.size // 4
    height = sum(b[3] - b[1] for b in boxes) + gap * (len(lines) - 1)
    y = (SIZE[1] - height) / 2
    for line, (left, top, right, bottom) in zip(lines, boxes):
        draw.text(((SIZE[0] - (right - left)) / 2 - left, y - top), line, font=font, fill=foreground)
        y += bottom - top + gap
    image.save(os.path.join(OUT, 'timer-%s.png' % name), optimize=True)


def split(label):
    words = label.split()
    if len(words) < 3:
        return words if len(label) > 10 else [label]
    middle = len(words) // 2
    return [' '.join(words[:middle]), ' '.join(words[middle:])]


os.makedirs(OUT, exist_ok=True)
render('off', ['SwiNOG'], 'black', 'white')
for phase in ('green', 'yellow', 'orange', 'red'):
    render(phase, split(LABELS[phase]), COLORS[phase], 'black')
# Differs from red although the LEDs show the same colour (they blink instead).
render('overdue', split(LABELS['overdue']), OVERDUE_DIM, 'white')

GAP = 12
overview = Image.new('RGB', (len(ORDER) * (SIZE[0] + GAP) - GAP, SIZE[1]), 'white')
for index, phase in enumerate(ORDER):
    overview.paste(Image.open(os.path.join(OUT, 'timer-%s.png' % phase)), (index * (SIZE[0] + GAP), 0))
overview.resize((overview.width // 2, overview.height // 2), Image.LANCZOS).save(
    os.path.join(ROOT, 'images', 'busytag-display.png'), optimize=True)
