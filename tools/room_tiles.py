"""Kanto's rooms in Pokemon Crystal's and FireRed/LeafGreen's tiles.

Indoors, Crystal redesigned Gen 1's rooms rather than redrawing them, so
redrawing Gen 1's tiles one by one (tools/crystal_tiles.py) can't work
there. Here a Gen 1 tileset is replaced whole: every 16x16 square of every
Gen 1 block (the 4x4 tiles maps are built from) takes a square from
Crystal's tilesets, from FireRed/LeafGreen's (brought to four shades by
tools/frlg_tiles.py) or Gen 1's own, the tiles those squares use become the
tileset, and the tables that name tile numbers are worked out again so that
every map plays as before:

- where you can walk (gfx/tilesets/*.tilecoll),
- the counters you talk over, the warp and door tiles, the shelves you read,
- MORE COLOR's color for each tile (Crystal's palette maps; FireRed's hues;
  Gen 1's own).

The maps themselves don't change: they name blocks, and every block keeps
its number. Gen 1 checks a 16x16 square by its bottom-left tile, so each
square's new bottom-left tile takes over the old one's role; a tile used in
squares of different roles is put in twice. A tileset holds $60 tiles.

The picks are in tools/room_tiles/<tileset>.txt, one line per Gen 1 block:

    0F <- pokecenter:04                                      a Crystal block, whole
    14 <- mart:2B mart:2B mart:13.0 mart:13.1                four squares
    0E <- frlg:pokemon_center:2A5 gen1:0E.1 gen1:0E.2 gen1:0E.3

Four picks are the squares top left, top right, bottom left, bottom right:
`set:BB.q` is square q (0-3) of Crystal block BB (`.q` left out: the same
corner), `frlg:set:SSS` FireRed's square SSS, `gen1:BB.q` Gen 1's own.
tools/room_picker.py makes a page to choose them by eye. Blocks with no
line are proposed (Crystal blocks, by the roles of their squares and
likeness) and written to the file.

    git clone --depth 1 https://github.com/pret/pokecrystal /tmp/pokecrystal
    git clone --depth 1 https://github.com/pret/pokefirered /tmp/pokefirered
    python3 tools/room_tiles.py /tmp/pokecrystal /tmp/pokefirered pokecenter [sheet.png]

Gen 1's own tilesets are read from git (ORIGINAL), so this can be run again
after editing the picks. The graphics are pret/pokecrystal's and
pret/pokefirered's.
"""
import collections
import os
import re
import subprocess
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crystal_tiles import REPO, gray_tiles, likeness, write_png  # noqa: E402
import frlg_tiles  # noqa: E402

ORIGINAL = '4ba5456'  # the last commit with Gen 1's indoor tilesets as they were

# gen 1 graphics tileset -> the tileset constants that use it, the Crystal
# tilesets and the FireRed maps (whose tilesets) its squares are taken from
ROOMS = {
    'pokecenter': dict(constants=('MART', 'POKECENTER'), crystal=('pokecenter', 'mart', 'house'),
                       frlg=('PokemonCenter_1F_Layout', 'Mart_Layout')),
}

QUADS = ((0, 1, 4, 5), (2, 3, 6, 7), (8, 9, 12, 13), (10, 11, 14, 15))
BOTTOM_LEFT = (4, 6, 12, 14)  # the tile Gen 1 checks for each 16x16 square

# Crystal's palette names -> MORE COLOR's (custom_functions/func_enhancedcolor.asm);
# Crystal's indoor red is pinkish, MORE COLOR's red orange: red takes pink
MORE_COLOR = {'RED': 1, 'ROOF': 1, 'GRAY': 3, 'GREEN': 4, 'YELLOW': 5, 'BROWN': 6, 'WATER': 7}
WALKABLE = {'FLOOR', 'WARP_CARPET_DOWN', 'WARP_CARPET_UP', 'WARP_CARPET_LEFT', 'WARP_CARPET_RIGHT',
            'DOOR', 'LADDER', 'STAIRCASE', 'CAVE', 'TALL_GRASS', 'LONG_GRASS'}


def git_show(path):
    return subprocess.check_output(['git', '-C', REPO, 'show', f'{ORIGINAL}:{path}'])


def blocks_of(data):
    return [data[i:i + 16] for i in range(0, len(data) - 15, 16)]


class Gen1Room:
    """a Gen 1 tileset as it was: tiles, blocks and what each tile does"""

    def __init__(self, name):
        self.name = name
        consts = ROOMS[name]['constants']
        path = f'/tmp/gen1_{os.getpid()}_{name}.png'
        open(path, 'wb').write(git_show(f'gfx/tilesets/{name}.png'))
        self.tiles = gray_tiles(path)
        os.remove(path)
        self.blocks = blocks_of(git_show(f'gfx/blocksets/{name}.bst'))
        self.walkable = set(git_show(f'gfx/tilesets/{name}.tilecoll').split(b'\xff')[0])
        headers = git_show('data/tileset_headers.asm').decode()
        label = consts[0].title().replace('_', '')
        m = re.search(rf'tileset {label}_Block,.*?,\s*(\$\w+),(\$\w+),(\$\w+),', headers)
        self.counters = {int(x[1:], 16) for x in m.groups()} - {0xFF}
        warps = git_show('data/warp_tile_ids.asm').decode()
        self.warps = set()
        for c in consts:
            label = c.title().replace('_', '') + 'WarpTileIDs:'
            block = warps[warps.index(label):]
            block = block[:block.index('\n\n')] if '\n\n' in block else block
            body = re.search(r'\tdb ([^\n]*)', block).group(1)
            self.warps |= {int(x.strip()[1:], 16) for x in body.split(',') if x.strip() != '$FF'}
        doors = git_show('engine/overworld/doors.asm').decode()
        self.doors = set()
        for c in consts:
            m = re.search(rf'dbw {c},\s*(\w+)', doors)
            if m:
                body = re.search(rf'{m.group(1)}:\s*\n\s*db ([^\n]*)', doors).group(1)
                self.doors |= {int(x.strip()[1:], 16) for x in body.split(',')} - {0}
        colors = git_show('custom_functions/func_enhancedcolor.asm').decode()
        body = colors[colors.index(f'PalSettings_{consts[-1]}:'):]
        self.colors = [int(v) for line in re.findall(r'^db\s+([^\n;]*)', body, re.M)[:6] for v in line.split(',')]
        shelves = git_show('engine/hidden_object_functions3.asm').decode()
        self.shelves = {}
        for c in consts:
            for t, text in re.findall(rf'db {c},\s*\$(\w+)\s*\n\s*db_tx_pre (\w+)', shelves):
                self.shelves[int(t, 16)] = text

    def role(self, t):
        """what standing on (or facing) tile t does"""
        return (t in self.walkable, t in self.counters, t in self.warps, t in self.doors, self.shelves.get(t))


class CrystalSet:
    def __init__(self, root, name):
        self.name = name
        self.blocks = blocks_of(open(os.path.join(root, f'data/tilesets/{name}_metatiles.bin'), 'rb').read())
        self.tiles = gray_tiles(os.path.join(root, f'gfx/tilesets/{name}.png'))
        coll = open(os.path.join(root, f'data/tilesets/{name}_collision.asm')).read()
        self.coll = [m for m in re.findall(r'tilecoll (\w+), (\w+), (\w+), (\w+)', coll)]
        pal = open(os.path.join(root, f'gfx/tilesets/{name}_palette_map.asm')).read()
        names = []
        for part in re.split(r'rept 16\s*db \$ff\s*endr', pal):
            names.append([n for line in re.findall(r'tilepal \d, ([^\n;]*)', part) for n in line.replace(' ', '').split(',')])
        self.pals = names  # [bank 0 tiles 00-5F, bank 1 tiles 80-DF]

    def tile(self, t):
        i = t if t < 0x60 else 0x60 + t - 0x80
        return self.tiles[i] if 0 <= i < len(self.tiles) and (t < 0x60 or t >= 0x80) else None

    def pal(self, t):
        names = self.pals[0] if t < 0x60 else (self.pals[1] if len(self.pals) > 1 else [])
        i = t if t < 0x60 else t - 0x80
        return MORE_COLOR.get(names[i] if i < len(names) else 'GRAY', 3)


def square_roles(g1, block):
    return [g1.role(block[k]) for k in BOTTOM_LEFT]


def score(g1, cr, gblock, cs, m):
    """how well Crystal block m of cs stands in for a Gen 1 block: the same
    walkable squares above all, then counters, then the look"""
    roles = square_roles(g1, gblock)
    coll = cr[cs].coll[m] if m < len(cr[cs].coll) else ('WALL',) * 4
    s = 0
    for (walk, counter, warp, door, shelf), c in zip(roles, coll):
        s += 4 * (walk == (c in WALKABLE))
        s += 2 * (counter == (c == 'COUNTER'))
        s += 1 * ((warp or door) == c.startswith('WARP') or c == 'DOOR')
    cb = cr[cs].blocks[m]
    look = sum(likeness(g1.tiles[gblock[k]] if gblock[k] < len(g1.tiles) else (0,) * 64,
                        cr[cs].tile(cb[k]) or (0,) * 64) for k in range(16)) / 16
    return s + 4 * look


def propose(g1, cr, b):
    best = None
    for cs in cr:
        for m in range(len(cr[cs].blocks)):
            if not any(cr[cs].tile(t) for t in cr[cs].blocks[m]):
                continue
            sc = score(g1, cr, g1.blocks[b], cs, m)
            if best is None or sc > best[0]:
                best = (sc, cs, m)
    return [('cr', best[1], best[2], i) for i in range(4)]


def frlg_color(px):
    """MORE COLOR's palette nearest a FireRed tile's hue"""
    import colorsys
    ink = [c for c in px if frlg_tiles.lum(c) < 235] or px
    r, g, b = (sum(c[i] for c in ink) / len(ink) / 255 for i in range(3))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if s < 0.18:
        return 3  # gray
    h *= 360
    for top, color in ((15, 0), (45, 6), (75, 5), (170, 4), (255, 7), (295, 2), (340, 1), (360, 0)):
        if h < top:
            return color


class Sources:
    """every square a pick can name: (kind, ...) -> four (tile pixels, MORE COLOR color)"""

    def __init__(self, g1, crystal_root, frlg_root):
        self.g1 = g1
        spec = ROOMS[g1.name]
        self.cr = {cs: CrystalSet(crystal_root, cs) for cs in spec['crystal']}
        self.fr = {}
        if frlg_root:
            for layout in spec['frlg']:
                fs = frlg_tiles.tileset_for(frlg_root, layout)
                self.fr[fs.name] = fs
        self._cache = {}

    def square(self, ref):
        if ref in self._cache:
            return self._cache[ref]
        kind = ref[0]
        if kind == 'cr':
            _, cs, m, q = ref
            cb = self.cr[cs].blocks[m]
            out = [(self.cr[cs].tile(cb[k]) or (0,) * 64, self.cr[cs].pal(cb[k])) for k in QUADS[q]]
        elif kind == 'frlg':
            _, fs, m = ref
            if fs not in self.fr:
                raise SystemExit(f'FireRed tileset {fs}: pass pokefirered, and list its map in ROOMS')
            rgb = self.fr[fs].rgb(m)
            out = []
            for k, px in enumerate(self.fr[fs].shades(m)):
                part = rgb.crop(((k % 2) * 8, (k // 2) * 8, (k % 2) * 8 + 8, (k // 2) * 8 + 8))
                out.append((px, frlg_color(list(part.getdata()))))
        else:
            _, b, q = ref
            blank = (0,) * 64
            gb = self.g1.blocks[b]
            out = [(self.g1.tiles[gb[k]] if gb[k] < len(self.g1.tiles) else blank,
                    self.g1.colors[gb[k]] if gb[k] < len(self.g1.colors) else 3) for k in QUADS[q]]
        self._cache[ref] = out
        return out


PICK = r'frlg:(\w+):([0-9A-Fa-f]{3})|gen1:([0-9A-Fa-f]{2})(?:\.([0-3]))?|(\w+):([0-9A-Fa-f]{2})(?:\.([0-3]))?'


def parse_pick(text):
    """a picks line's refs -> four refs"""
    refs = []
    for fs, fm, gb, gq, cs, cm, cq in re.findall(PICK, text):
        if fs:
            refs.append([('frlg', fs, int(fm, 16))])
        elif gb:
            refs.append([('gen1', int(gb, 16), int(gq) if gq else i) for i in range(4)] if not gq else
                        [('gen1', int(gb, 16), int(gq))])
        else:
            refs.append([('cr', cs, int(cm, 16), int(cq) if cq else i) for i in range(4)] if not cq else
                        [('cr', cs, int(cm, 16), int(cq))])
    if len(refs) == 1 and len(refs[0]) == 4:
        return refs[0]
    if len(refs) == 4:
        # a block named without .q means the same corner of it
        return [r[i] if len(r) == 4 else r[0] for i, r in enumerate(refs)]
    return None


def read_picks(name):
    """block -> four refs, and the comments"""
    path = os.path.join(REPO, f'tools/room_tiles/{name}.txt')
    picks, notes = {}, {}
    if os.path.exists(path):
        for n, line in enumerate(open(path), 1):
            m = re.match(r'\s*([0-9A-Fa-f]{2})\s*<-\s*((?:(?:frlg:\w+:[0-9A-Fa-f]{3}|\w+:[0-9A-Fa-f]{2}(?:\.[0-3])?)\s*)+)(.*)', line)
            if not m:
                continue
            pick = parse_pick(m.group(2))
            if not pick:
                raise SystemExit(f'{name}.txt line {n}: a block takes 1 or 4 picks')
            picks[int(m.group(1), 16)] = pick
            notes[int(m.group(1), 16)] = m.group(3).strip()
    return picks, notes


def ref_text(ref, i=None):
    if ref[0] == 'frlg':
        return f'frlg:{ref[1]}:{ref[2]:03X}'
    if ref[0] == 'gen1':
        return f'gen1:{ref[1]:02X}' + ('' if ref[2] == i else f'.{ref[2]}')
    return f'{ref[1]}:{ref[2]:02X}' + ('' if ref[3] == i else f'.{ref[3]}')


def pick_text(pick):
    if pick[0][0] != 'frlg' and all(r[:-1] == pick[0][:-1] and r[-1] == i for i, r in enumerate(pick)):
        return ref_text(pick[0], 0)
    return ' '.join(ref_text(r, i) for i, r in enumerate(pick))


def write_picks(name, picks, notes):
    path = os.path.join(REPO, f'tools/room_tiles/{name}.txt')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [f'# {name}: Gen 1 block <- its four squares (see tools/room_tiles.py)']
    for b in sorted(picks):
        lines.append(f'{b:02X} <- {pick_text(picks[b]):<52} {notes.get(b, "")}'.rstrip())
    open(path, 'w').write('\n'.join(lines) + '\n')


def build(g1, src, picks):
    """-> (tiles, blocks, walkable ids, counter ids, warp ids, door ids, {shelf id: text}, colors), problems"""
    uses = []  # per block: 16 (pixels, color, role or None)
    for b, gblock in enumerate(g1.blocks):
        roles = square_roles(g1, gblock)
        row = [None] * 16
        for i, ref in enumerate(picks[b]):
            for k_to, (px, color) in zip(QUADS[i], src.square(ref)):
                role = roles[BOTTOM_LEFT.index(k_to)] if k_to in BOTTOM_LEFT else None
                row[k_to] = (px, color, role)
        uses.append(row)
    # a counter is a wall you can talk over: a picture used as both a
    # counter and a plain wall is a counter everywhere (talking over a back
    # wall finds no one)
    counter_px = {px for row in uses for px, color, role in row if role and role[1]}
    uses = [[(px, color, (role[0], True) + role[2:] if role and px in counter_px and role == (False, False, False, False, None)
              else role) for px, color, role in row] for row in uses]
    # one tile per picture and role; pictures with no role join the first
    ids, tiles, colors, roles_of = {}, [], [], {}
    for row in uses:
        for px, color, role in row:
            if role is not None and (px, role) not in ids:
                ids[(px, role)] = len(tiles)
                tiles.append(px)
                colors.append(color)
                roles_of[len(tiles) - 1] = role
    for row in uses:
        for px, color, role in row:
            if role is None and not any(k[0] == px for k in ids):
                ids[(px, None)] = len(tiles)
                tiles.append(px)
                colors.append(color)
    problems = []
    if len(tiles) > 0x60:
        problems.append(f'{len(tiles)} tiles: more than the $60 a Gen 1 tileset holds')

    def tile_id(px, role):
        if role is not None:
            return ids[(px, role)]
        return ids.get((px, None), next((i for k, i in ids.items() if k[0] == px), None))
    blocks = [bytes(min(tile_id(px, role), 0x5F) for px, color, role in row) for row in uses]
    walk = sorted(t for t, r in roles_of.items() if r[0])
    counters = sorted(t for t, r in roles_of.items() if r[1])
    warps = sorted(t for t, r in roles_of.items() if r[2])
    doors = sorted(t for t, r in roles_of.items() if r[3])
    shelves = {t: r[4] for t, r in roles_of.items() if r[4]}
    if len(counters) > 3:
        problems.append(f'{len(counters)} counter tiles: a tileset header holds 3')
    return (tiles[:0x60], blocks, walk, counters, warps, doors, shelves, colors[:0x60]), problems


def hexes(ids):
    return ','.join(f'${t:02X}' for t in ids)


def write(name, g1, built):
    tiles, blocks, walk, counters, warps, doors, shelves, colors = built
    write_png(tiles, os.path.join(REPO, f'gfx/tilesets/{name}.png'))
    open(os.path.join(REPO, f'gfx/blocksets/{name}.bst'), 'wb').write(b''.join(blocks))
    open(os.path.join(REPO, f'gfx/tilesets/{name}.tilecoll'), 'wb').write(bytes(walk) + b'\xff')
    up = name.upper()
    out = [f'; {name}: made by tools/room_tiles.py; don\'t edit',
           *[f'DEF {up}_COUNTER_{i + 1} EQU ${t:02X}' for i, t in enumerate((counters + [0xFF] * 3)[:3])],
           f'DEF {up}_WARPS EQUS "{hexes(warps)}"',
           f'DEF {up}_DOORS EQUS "{hexes(doors)}"',
           '; the shelves you read (BookshelfTileIDs), for tileset \\1',
           f'MACRO {name}_shelves']
    for t, text in sorted(shelves.items()):
        out += [f'\tdb \\1, ${t:02X}', f'\tdb_tx_pre {text}']
    out.append('ENDM')
    open(os.path.join(REPO, f'constants/rooms/{name}.asm'), 'w').write('\n'.join(out) + '\n')
    rows = [colors[i:i + 16] + [3] * (16 - len(colors[i:i + 16])) for i in range(0, 0x60, 16)]
    rows = [r if len(r) == 16 else [3] * 16 for r in rows]
    while len(rows) < 6:
        rows.append([3] * 16)
    col = [f'; {name}: MORE COLOR\'s color for each tile (tools/room_tiles.py)']
    col += ['db\t' + ',\t'.join(str(c) for c in r) for r in rows]
    open(os.path.join(REPO, f'data/tilesets/{name}_colors.asm'), 'w').write('\n'.join(col) + '\n')


def tile_image(px, scale=1):
    im = Image.new('L', (8, 8))
    im.putdata([255 - 85 * p for p in px])
    return im.resize((8 * scale, 8 * scale), Image.NEAREST)


def block_image(tilefn, block, scale=2):
    im = Image.new('L', (32, 32))
    for k in range(16):
        im.paste(tile_image(tilefn(block[k])), ((k % 4) * 8, (k // 4) * 8))
    return im.resize((32 * scale, 32 * scale), Image.NEAREST)


def review_sheet(g1, picks, notes, built, out):
    """Gen 1 block | Crystal pick, per block, with numbers"""
    blank = (0,) * 64
    tiles = built[0]
    cols = 4
    W, H = 64 * 2 + 40, 64 + 28
    n = len(g1.blocks)
    im = Image.new('RGB', (cols * W, ((n + cols - 1) // cols) * H), (228, 232, 222))
    d = ImageDraw.Draw(im)
    for b in range(n):
        x, y = (b % cols) * W + 6, (b // cols) * H + 4
        im.paste(block_image(lambda t: g1.tiles[t] if t < len(g1.tiles) else blank, g1.blocks[b]), (x, y + 12))
        im.paste(block_image(lambda t: tiles[t], built[1][b]), (x + 68, y + 12))
        d.text((x, y), f'{b:02X} <- {pick_text(picks[b])}'[:30], fill=(20, 40, 20))
        if notes.get(b):
            d.text((x, y + 78), notes[b][:24], fill=(90, 90, 90))
    im.save(out)


def map_previews(g1, built, out, scale=2):
    """every map with this tileset, Gen 1 above, new below"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import crystal_tiles
    maps = crystal_tiles.Gen1()
    seen, ims = set(), []
    blank = (0,) * 64
    for mname, (gset, path) in sorted(maps.maps.items()):
        if gset != g1.name or path in seen:
            continue
        seen.add(path)
        w, h = maps.dims[mname]
        blk = open(path, 'rb').read()
        im = Image.new('L', (w * 64, h * 64 * 2 + 4), 128)
        for y in range(h):
            for x in range(w):
                bl = blk[y * w + x]
                im.paste(block_image(lambda t: g1.tiles[t] if t < len(g1.tiles) else blank, g1.blocks[bl]), (x * 64, y * 64))
                im.paste(block_image(lambda t: built[0][t], built[1][bl]), (x * 64, h * 64 + 4 + y * 64))
        ims.append(im)
    W = sum(i.width + 8 for i in ims)
    o = Image.new('L', (W, max(i.height for i in ims)), 60)
    x = 0
    for i in ims:
        o.paste(i, (x, 0))
        x += i.width + 8
    o.resize((o.width * scale // 2, o.height * scale // 2), Image.NEAREST).save(out)


def main(crystal_root, frlg_root, name, sheet=None):
    g1 = Gen1Room(name)
    src = Sources(g1, crystal_root, frlg_root)
    picks, notes = read_picks(name)
    for b in range(len(g1.blocks)):
        if b not in picks:
            picks[b] = propose(g1, src.cr, b)
            notes[b] = 'proposed'
    write_picks(name, picks, notes)
    built, problems = build(g1, src, picks)
    if sheet:
        review_sheet(g1, picks, notes, built, sheet)
        map_previews(g1, built, sheet.replace('.png', '_maps.png'))
    if problems:
        raise SystemExit('\n'.join(problems))
    write(name, g1, built)
    print(f'{name}: {len(built[0])} tiles; walkable {len(built[2])}, counters {hexes(built[3])}, '
          f'warps {hexes(built[4])}, doors {hexes(built[5])}, shelves {hexes(built[6])}')


if __name__ == '__main__':
    main(*sys.argv[1:5])
