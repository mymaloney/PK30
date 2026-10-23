"""Pokemon FireRed/LeafGreen's map squares, read from pret/pokefirered.

A GBA map is built from 16x16 squares (metatiles), each two layers of four
8x8 tiles in 16 colors, flipped as they please. A square here is flattened
(the top layer over the bottom one), and brought to the Game Boy's four
shades by brightness, so it can stand in for one 16x16 square of a Gen 1
block (tools/crystal_rooms.py). Flips are drawn in, so a flipped tile is a
tile of its own here.

    git clone --depth 1 https://github.com/pret/pokefirered /tmp/pokefirered
"""
import json
import os
import struct

from PIL import Image

PRIMARY_TILES = 0x280      # the secondary tileset's tiles and squares start here
PRIMARY_PALETTES = 7       # palettes 0-6 the primary's, 7-12 the secondary's
# the shares of a tileset's pixels, lightest first, that are drawn white,
# light and dark (the rest black): a GBA room is pastel, a Game Boy's four
# shades need to spread over it
SHARES = (0.45, 0.78, 0.94)


def snake(name):
    """gTileset_PokemonCenter -> pokemon_center"""
    out = ''
    for c in name.replace('gTileset_', ''):
        if c.isupper() and out:
            out += '_'
        out += c.lower()
    return out


def lum(rgb):
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


def read_pal(path):
    lines = open(path).read().split('\n')[3:]
    return [tuple(int(v) for v in l.split()[:3]) for l in lines if l.strip()][:16]


class FrlgTileset:
    """a primary and a secondary tileset, as a map uses them"""

    def __init__(self, root, primary, secondary):
        self.root = root
        self.name = secondary
        base = os.path.join(root, 'data/tilesets')
        pdir, sdir = os.path.join(base, 'primary', primary), os.path.join(base, 'secondary', secondary)
        self.tiles = (self._tiles(pdir) + [bytes(64)] * PRIMARY_TILES)[:PRIMARY_TILES] + self._tiles(sdir)
        self.metatiles = self._metatiles(pdir)
        self.metatiles = (self.metatiles + [None] * PRIMARY_TILES)[:PRIMARY_TILES] + self._metatiles(sdir)
        self.palettes = [read_pal(os.path.join(pdir, f'palettes/{i:02}.pal')) for i in range(PRIMARY_PALETTES)]
        self.palettes += [read_pal(os.path.join(sdir, f'palettes/{i:02}.pal')) for i in range(PRIMARY_PALETTES, 16)]
        self._cut = None

    @staticmethod
    def _tiles(d):
        im = Image.open(os.path.join(d, 'tiles.png'))
        w, h = im.size
        px = im.load()
        return [bytes(px[tx * 8 + x, ty * 8 + y] & 15 for y in range(8) for x in range(8))
                for ty in range(h // 8) for tx in range(w // 8)]

    @staticmethod
    def _metatiles(d):
        b = open(os.path.join(d, 'metatiles.bin'), 'rb').read()
        return [struct.unpack('<8H', b[i:i + 16]) for i in range(0, len(b) - 15, 16)]

    def cuts(self):
        """the brightnesses that part the shades, from the room's own squares"""
        if self._cut is None:
            lums = sorted((lum(p) for m in self.secondary_squares() for p in self.rgb(m).getdata()), reverse=True)
            self._cut = [lums[int(len(lums) * s)] for s in SHARES]  # light -> dark
        return self._cut

    def secondary_squares(self):
        """the square numbers of the secondary tileset (the room's own)"""
        return [m for m in range(PRIMARY_TILES, len(self.metatiles)) if self.metatiles[m]]

    def rgb(self, m):
        """square m -> a 16x16 RGB image"""
        im = Image.new('RGB', (16, 16))
        px = im.load()
        entries = self.metatiles[m]
        for layer in (0, 1):
            for k in range(4):
                e = entries[layer * 4 + k]
                t, hf, vf, pal = e & 0x3FF, e >> 10 & 1, e >> 11 & 1, e >> 12
                tile = self.tiles[t] if t < len(self.tiles) else bytes(64)
                colors = self.palettes[pal]
                for y in range(8):
                    for x in range(8):
                        c = tile[(7 - y if vf else y) * 8 + (7 - x if hf else x)]
                        if c == 0 and layer == 1:
                            continue
                        px[(k % 2) * 8 + x, (k // 2) * 8 + y] = colors[c]
        return im

    def shades(self, m):
        """square m -> its four 8x8 tiles in the Game Boy's shades (0 white .. 3 black)"""
        im = self.rgb(m)
        px = im.load()
        cut = self.cuts()

        def shade(rgb):
            return sum(lum(rgb) < c for c in cut)
        return [tuple(shade(px[(k % 2) * 8 + x, (k // 2) * 8 + y]) for y in range(8) for x in range(8))
                for k in range(4)]


def layouts(root):
    d = json.load(open(os.path.join(root, 'data/layouts/layouts.json')))
    return {l['name']: l for l in d['layouts'] if 'name' in l}


def tileset_for(root, layout):
    l = layouts(root)[layout]
    return FrlgTileset(root, snake(l['primary_tileset']), snake(l['secondary_tileset']))
