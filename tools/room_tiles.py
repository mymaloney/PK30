"""Kanto's rooms in Pokemon Crystal's tiles.

Indoors, Crystal redesigned Gen 1's rooms rather than redrawing them, so
redrawing Gen 1's tiles one by one (tools/crystal_tiles.py) can't work
there. Here a Gen 1 tileset is replaced whole: every 16x16 square of every
Gen 1 block (the 4x4 tiles maps are built from) takes a square from any of
Crystal's tilesets (Johto's too) or Gen 1's own, the tiles those squares use become the
tileset, and the tables that name tile numbers are worked out again so that
every map plays as before:

- where you can walk (gfx/tilesets/*.tilecoll),
- the counters you talk over, the warp and door tiles, the shelves you read,
- MORE COLOR's color for each tile (Crystal's palette maps; Gen 1's own).

The maps themselves don't change: they name blocks, and every block keeps
its number. Gen 1 checks a 16x16 square by its bottom-left tile, so each
square's new bottom-left tile takes over the old one's role; a tile used in
squares of different roles is put in twice. A tileset holds $60 tiles.

The picks are in tools/room_tiles/<tileset>.txt, one line per Gen 1 block:

    0F <- pokecenter:04                                      a Crystal block, whole
    14 <- mart:2B mart:2B mart:13.0 mart:13.1                four squares
    0E <- house:06.0 gen1:0E.1 gen1:0E.2 gen1:0E.3

Four picks are the squares top left, top right, bottom left, bottom right:
`set:BB.q` is square q (0-3) of Crystal block BB (`.q` left out: the same
corner), `gen1:BB.q` Gen 1's own.
tools/room_picker.py makes a page to choose them by eye. Blocks with no
line are proposed (Crystal blocks, by the roles of their squares and
likeness) and written to the file.

    git clone --depth 1 https://github.com/pret/pokecrystal /tmp/pokecrystal
    python3 tools/room_tiles.py /tmp/pokecrystal pokecenter [sheet.png]

Gen 1's own tilesets are read from git (ORIGINAL), so this can be run again
after editing the picks. The graphics are pret/pokecrystal's.
"""
import collections
import os
import re
import subprocess
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crystal_tiles import REPO, gray_tiles, likeness, write_png  # noqa: E402

ORIGINAL = '4ba5456'  # the last commit with Gen 1's indoor tilesets as they were

# gen 1 graphics tileset -> the tileset constants that use it, and the
# Crystal tilesets its blocks are proposed from (picks can name any)
# (gen1: the Gen 1 tileset it began as; MART and POKECENTER shared one)
ROOMS = {
    'pokecenter': dict(constants=('POKECENTER',), gen1='pokecenter', crystal=('pokecenter', 'mart', 'house')),
    'mart': dict(constants=('MART',), gen1='pokecenter', crystal=('mart', 'pokecenter', 'house')),
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
        self.talked_over = None  # counters_talked_over, when first needed
        consts = ROOMS[name]['constants']
        gen1 = ROOMS[name].get('gen1', name)
        path = f'/tmp/gen1_{os.getpid()}_{name}.png'
        open(path, 'wb').write(git_show(f'gfx/tilesets/{gen1}.png'))
        self.tiles = gray_tiles(path)
        os.remove(path)
        self.blocks = blocks_of(git_show(f'gfx/blocksets/{gen1}.bst'))
        self.walkable = set(git_show(f'gfx/tilesets/{gen1}.tilecoll').split(b'\xff')[0])
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


def room_maps(name):
    """the maps with this room tileset: [(map, .blk path, width, height)]"""
    main = open(os.path.join(REPO, 'main.asm')).read()
    blk = dict(re.findall(r'^(\w+Blocks):\s*INCBIN\s+"([^"]+)"', main, re.M))
    # labels stacked on one INCBIN share it
    for group in re.findall(r'((?:^\w+Blocks:\s*\n)+)(^\w+Blocks):\s*INCBIN\s+"([^"]+)"', main, re.M):
        for label in re.findall(r'(\w+Blocks):', group[0]):
            blk[label] = group[2]
    consts = open(os.path.join(REPO, 'constants/map_constants.asm')).read()
    dims = {m.group(1): (int(m.group(3)), int(m.group(2))) for m in
            re.finditer(r'mapconst (\w+),\s*(\d+),\s*(\d+)', consts)}
    out = []
    hdr_dir = os.path.join(REPO, 'data/mapHeaders')
    for f in sorted(os.listdir(hdr_dir)):
        t = open(os.path.join(hdr_dir, f)).read()
        ts = re.search(r'db (\w+) ; tileset', t)
        dim = re.search(r'db (\w+)_HEIGHT', t)
        bl = re.search(r'dw (\w+Blocks)', t)
        if ts and dim and bl and ts.group(1) in ROOMS[name]['constants'] and bl.group(1) in blk:
            w, h = dims[dim.group(1)]
            out.append((dim.group(1), os.path.join(REPO, blk[bl.group(1)]), w, h))
    return out


def border_blocks(name):
    """the blocks drawn past the edges of this room tileset's maps"""
    objects = {}
    for f in os.listdir(os.path.join(REPO, 'data/mapObjects')):
        t = open(os.path.join(REPO, 'data/mapObjects', f)).read()
        for label, b in re.findall(r'^(\w+Object):\s*\n\s*db \$?(\w+) ; border block', t, re.M):
            objects[label] = int(b, 16)
    out = set()
    hdr_dir = os.path.join(REPO, 'data/mapHeaders')
    for f in sorted(os.listdir(hdr_dir)):
        t = open(os.path.join(hdr_dir, f)).read()
        ts = re.search(r'db (\w+) ; tileset', t)
        ob = re.search(r'dw (\w+Object) ; objects', t)
        if ts and ob and ts.group(1) in ROOMS[name]['constants'] and ob.group(1) in objects:
            out.add(objects[ob.group(1)])
    return out


def map_people(name):
    """{map: ([(x, y) of each person], [(x, y) of each warp])} for this room tileset's maps"""
    objects = {}
    for f in os.listdir(os.path.join(REPO, 'data/mapObjects')):
        t = open(os.path.join(REPO, 'data/mapObjects', f)).read()
        for label, body in re.findall(r'^(\w+Object):(.*?)(?=^\w+Object:|\Z)', t, re.M | re.S):
            objects[label] = ([(int(x), int(y)) for x, y in re.findall(r'^\s*object \w+, (\d+), (\d+)', body, re.M)],
                              [(int(x), int(y)) for x, y in re.findall(r'^\s*warp (\d+), (\d+)', body, re.M)])
    out = {}
    hdr_dir = os.path.join(REPO, 'data/mapHeaders')
    for f in sorted(os.listdir(hdr_dir)):
        t = open(os.path.join(hdr_dir, f)).read()
        ts = re.search(r'db (\w+) ; tileset', t)
        dim = re.search(r'db (\w+)_HEIGHT', t)
        ob = re.search(r'dw (\w+Object) ; objects', t)
        if ts and dim and ob and ts.group(1) in ROOMS[name]['constants']:
            out[dim.group(1)] = objects.get(ob.group(1), ([], []))
    return out


def counters_talked_over(g1):
    """(block, square) of Gen 1's counters you can talk over in some map: a
    person stands on one side and the other is a square you can walk to from
    the doors. The others are walls"""
    people = map_people(g1.name)
    out = set()
    for mname, path, w, h in room_maps(g1.name):
        blk = git_show(os.path.relpath(path, REPO))
        here, warps = (set(v) for v in people.get(mname, ([], [])))

        def square(sx, sy):
            b = blk[(sy // 2) * w + sx // 2]
            return b, (sy % 2) * 2 + sx % 2, g1.role(g1.blocks[b][BOTTOM_LEFT[(sy % 2) * 2 + sx % 2]])
        # the squares you can reach from the doors
        reach, todo = set(), [p for p in warps if 0 <= p[0] < w * 2 and 0 <= p[1] < h * 2]
        while todo:
            sx, sy = todo.pop()
            if (sx, sy) in reach or not (0 <= sx < w * 2 and 0 <= sy < h * 2) or not square(sx, sy)[2][0]:
                continue
            reach.add((sx, sy))
            todo += [(sx + 1, sy), (sx - 1, sy), (sx, sy + 1), (sx, sy - 1)]
        for sx in range(w * 2):
            for sy in range(h * 2):
                b, q, role = square(sx, sy)
                if role[1] and any((sx + dx, sy + dy) in here and (sx - dx, sy - dy) in reach
                                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    out.add((b, q))
    return out


def square_roles(g1, block, b=None):
    """what each 16x16 square of a Gen 1 block does; with the block's number,
    a counter no one stands behind is a wall"""
    roles = [g1.role(block[k]) for k in BOTTOM_LEFT]
    if b is None:
        return roles
    if g1.talked_over is None:
        g1.talked_over = counters_talked_over(g1)
    return [r[:1] + (False,) + r[2:] if r[1] and (b, q) not in g1.talked_over else r for q, r in enumerate(roles)]


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


class Sources:
    """every square a pick can name: (kind, ...) -> four (tile pixels, MORE COLOR color)"""

    def __init__(self, g1, crystal_root):
        self.g1 = g1
        self.root = crystal_root
        self.cr = {cs: CrystalSet(crystal_root, cs) for cs in ROOMS[g1.name]['crystal']}
        self._cache = {}

    def crystal(self, cs):
        if cs not in self.cr:
            if not os.path.exists(os.path.join(self.root, f'data/tilesets/{cs}_metatiles.bin')):
                raise SystemExit(f'no Crystal tileset {cs}')
            self.cr[cs] = CrystalSet(self.root, cs)
        return self.cr[cs]

    def square(self, ref):
        if ref in self._cache:
            return self._cache[ref]
        kind = ref[0]
        if kind == 'cr':
            _, cs, m, q = ref
            cset = self.crystal(cs)
            cb = cset.blocks[m]
            out = [(cset.tile(cb[k]) or (0,) * 64, cset.pal(cb[k])) for k in QUADS[q]]
        else:
            _, b, q = ref
            blank = (0,) * 64
            gb = self.g1.blocks[b]
            out = [(self.g1.tiles[gb[k]] if gb[k] < len(self.g1.tiles) else blank,
                    self.g1.colors[gb[k]] if gb[k] < len(self.g1.colors) else 3) for k in QUADS[q]]
        self._cache[ref] = out
        return out


PICK = r'gen1:([0-9A-Fa-f]{2})(?:\.([0-3]))?|(\w+):([0-9A-Fa-f]{2})(?:\.([0-3]))?'


def parse_pick(text):
    """a picks line's refs -> four refs"""
    refs = []
    for gb, gq, cs, cm, cq in re.findall(PICK, text):
        if gb:
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
            m = re.match(r'\s*([0-9A-Fa-f]{2})\s*<-\s*((?:\w+:[0-9A-Fa-f]{2}(?:\.[0-3])?\s*)+)(.*)', line)
            if not m:
                continue
            pick = parse_pick(m.group(2))
            if not pick:
                raise SystemExit(f'{name}.txt line {n}: a block takes 1 or 4 picks')
            picks[int(m.group(1), 16)] = pick
            notes[int(m.group(1), 16)] = m.group(3).strip()
    return picks, notes


def ref_text(ref, i=None):
    if ref[0] == 'gen1':
        return f'gen1:{ref[1]:02X}' + ('' if ref[2] == i else f'.{ref[2]}')
    return f'{ref[1]}:{ref[2]:02X}' + ('' if ref[3] == i else f'.{ref[3]}')


def pick_text(pick):
    if all(r[:-1] == pick[0][:-1] and r[-1] == i for i, r in enumerate(pick)):
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
        roles = square_roles(g1, gblock, b)
        row = [None] * 16
        for i, ref in enumerate(picks[b]):
            for k_to, (px, color) in zip(QUADS[i], src.square(ref)):
                role = roles[BOTTOM_LEFT.index(k_to)] if k_to in BOTTOM_LEFT else None
                row[k_to] = (px, color, role)
        uses.append(row)
    return assemble(uses)


def assemble(uses):
    """blocks as 16 (tile pixels, MORE COLOR color, role at a bottom-left or None) -> the tileset"""
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
    if 0 in doors:
        problems.append('tile $00 is a door, but $00 ends the door list')
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
           f'DEF {up}_WARPS EQUS "{hexes(warps + [0xFF])}"  ; ends with $FF',
           f'DEF {up}_DOORS EQUS "{hexes(doors + [0x00])}"  ; ends with $00',
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


def main(crystal_root, name, sheet=None):
    g1 = Gen1Room(name)
    src = Sources(g1, crystal_root)
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
    main(*sys.argv[1:4])
