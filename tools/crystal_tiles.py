"""Match this game's map tiles to Gold/Silver/Crystal's redrawn ones.

Kanto is in both games. For every Gen 1 map that Crystal has too, the two
maps' block grids are laid over each other (both games build maps from 4x4
tile blocks); where they line up, each Gen 1 tile votes for the Crystal tile
drawn in the same place. The winners, checked by eye, replace the Gen 1
tiles' graphics, keeping their numbers (so collision, warps, grass, water,
ledges and the rest behave as before), in Crystal's four shades (the DMG's).

    git clone --depth 1 https://github.com/pret/pokecrystal /tmp/pokecrystal
    python3 tools/crystal_tiles.py /tmp/pokecrystal votes   # the matches
    python3 tools/crystal_tiles.py /tmp/pokecrystal apply   # write the tilesets

Only the overworld and the forest's grass are applied (APPLY): Crystal
remastered Kanto's outdoors keeping Gen 1's tile numbers, but redesigned the
interiors, caves and gyms, where no tile-for-tile match holds up (tried and
reviewed: furniture came out half-redrawn, floors lost their texture, a
cave's ladders vanished). The choices are written to
tools/crystal_tiles_choices.txt.

The graphics are pret/pokecrystal's (gfx/tilesets).
"""
import collections
import os
import re
import sys

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Gen 1 tileset constant -> the tileset file (data/tileset_headers.asm and
# main.asm: several share one)
GEN1_FILES = {
    'OVERWORLD': 'overworld', 'REDS_HOUSE_1': 'reds_house', 'REDS_HOUSE_2': 'reds_house',
    'MART': 'pokecenter', 'POKECENTER': 'pokecenter', 'FOREST': 'forest', 'DOJO': 'gym', 'GYM': 'gym',
    'HOUSE': 'house', 'FOREST_GATE': 'gate', 'MUSEUM': 'gate', 'GATE': 'gate',
    'UNDERGROUND': 'underground', 'SHIP': 'ship', 'SHIP_PORT': 'ship_port', 'CEMETERY': 'cemetery',
    'INTERIOR': 'interior', 'CAVERN': 'cavern', 'LOBBY': 'lobby', 'MANSION': 'mansion', 'LAB': 'lab',
    'CLUB': 'club', 'FACILITY': 'facility', 'PLATEAU': 'plateau',
}

# Gen 1 map -> Crystal map, where the names differ
ALIASES = {
    'MT_MOON_1': 'MOUNT_MOON', 'ROCK_TUNNEL_1': 'ROCK_TUNNEL_1F', 'ROCK_TUNNEL_2': 'ROCK_TUNNEL_B1F',
    'VICTORY_ROAD_1': 'VICTORY_ROAD', 'DIGLETTS_CAVE': 'DIGLETTS_CAVE',
    'REDS_HOUSE_1F': 'REDS_HOUSE_1F', 'REDS_HOUSE_2F': 'REDS_HOUSE_2F', 'OAKS_LAB': 'OAKS_LAB',
    'BLUES_HOUSE': 'BLUES_HOUSE', 'POWER_PLANT': 'POWER_PLANT',
    'ROUTE_5_GATE': 'ROUTE_5_SAFFRON_GATE', 'ROUTE_6_GATE': 'ROUTE_6_SAFFRON_GATE',
    'ROUTE_7_GATE': 'ROUTE_7_SAFFRON_GATE', 'ROUTE_8_GATE': 'ROUTE_8_SAFFRON_GATE',
    'ROUTE_16_GATE_1F': 'ROUTE_16_GATE', 'PATH_ENTRANCE_ROUTE_5': 'ROUTE_5_UNDERGROUND_PATH_ENTRANCE',
    'PATH_ENTRANCE_ROUTE_6': 'ROUTE_6_UNDERGROUND_PATH_ENTRANCE', 'UNDERGROUND_PATH_NS': 'UNDERGROUND_PATH',
    'CELADON_MANSION_1': 'CELADON_MANSION_1F', 'CELADON_MANSION_2': 'CELADON_MANSION_2F',
    'CELADON_MANSION_3': 'CELADON_MANSION_3F', 'CELADON_MART_1': 'CELADON_DEPT_STORE_1F',
    'CELADON_MART_2': 'CELADON_DEPT_STORE_2F', 'CELADON_MART_3': 'CELADON_DEPT_STORE_3F',
    'CELADON_MART_4': 'CELADON_DEPT_STORE_4F', 'CELADON_MART_5': 'CELADON_DEPT_STORE_5F',
    'CELADON_MART_ELEVATOR': 'CELADON_DEPT_STORE_ELEVATOR', 'GAME_CORNER': 'CELADON_GAME_CORNER',
    'CELADON_PRIZE_ROOM': 'CELADON_GAME_CORNER_PRIZE_ROOM', 'VERMILION_DOCK': 'VERMILION_PORT',
    'SS_ANNE_1': 'FAST_SHIP_1F', 'SS_ANNE_9': 'FAST_SHIP_CABINS_SW_SSW_NW',
}

# Crystal tilesets to look through by likeness alone, for Gen 1 tilesets
# whose maps Crystal doesn't have (or has redrawn past matching)
LIKENESS = {
    'cemetery': ['tower', 'house'], 'forest': ['forest', 'park'], 'lab': ['lab'],
    'ship': ['ship', 'port'], 'club': ['gate', 'house'], 'interior': ['house'],
    'house': ['house'], 'gate': ['gate'], 'lobby': ['mart', 'game_corner'],
    'mansion': ['mansion', 'house'], 'underground': ['underground'], 'plateau': ['kanto', 'champions_room'],
}

# where Crystal kept Gen 1's tile numbers (the same tile number is a candidate)
SAME_NUMBERS = {'overworld': 'kanto'}

# reviewed by eye: where Crystal's same number is another object, the tile
# that is this one
OVERRIDE = {('overworld', 0x32): ('kanto', 0x33)}

# tiles Crystal numbers the same but draws as something else: kept
KEEP = {'overworld': (0x0D, 0x1D, 0x3C, 0x5E, 0x5F)}

INDOOR_GOOD = 0.88  # least likeness for a voted match away from the overworld
STRICT = 0.90 # least likeness for a match by likeness alone


def gray_tiles(path):
    """a tileset PNG -> [16 shade indices per row x 8 rows] per tile, 0 the lightest"""
    im = Image.open(path).convert('L')
    w, h = im.size
    px = im.load()
    levels = sorted({px[x, y] for y in range(h) for x in range(w)}, reverse=True)
    # four shades: map each gray to 0-3 by brightness
    def shade(v):
        return min(3, round((255 - v) / 85))
    tiles = []
    for ty in range(h // 8):
        for tx in range(w // 8):
            tiles.append(tuple(shade(px[tx * 8 + x, ty * 8 + y]) for y in range(8) for x in range(8)))
    return tiles


class Gen1:
    def __init__(self):
        consts = open(os.path.join(REPO, 'constants/map_constants.asm')).read()
        self.dims = {m.group(1): (int(m.group(3)), int(m.group(2))) for m in
                     re.finditer(r'mapconst (\w+),\s*(\d+),\s*(\d+)', consts)}  # name -> (w, h)
        main = open(os.path.join(REPO, 'main.asm')).read()
        blk = dict(re.findall(r'^(\w+Blocks):\s*INCBIN\s+"([^"]+)"', main, re.M))
        self.maps = {}
        hdr_dir = os.path.join(REPO, 'data/mapHeaders')
        for f in sorted(os.listdir(hdr_dir)):
            t = open(os.path.join(hdr_dir, f)).read()
            ts = re.search(r'db (\w+) ; tileset', t)
            dim = re.search(r'db (\w+)_HEIGHT', t)
            bl = re.search(r'dw (\w+Blocks)', t)
            if not (ts and dim and bl) or bl.group(1) not in blk:
                continue
            name = dim.group(1)
            if name not in self.dims or ts.group(1) not in GEN1_FILES:
                continue
            self.maps[name] = (GEN1_FILES[ts.group(1)], os.path.join(REPO, blk[bl.group(1)]))
        self.blocksets = {}
        self.tiles = {}
        for name in set(GEN1_FILES.values()):
            b = open(os.path.join(REPO, f'gfx/blocksets/{name}.bst'), 'rb').read()
            self.blocksets[name] = [b[i:i + 16] for i in range(0, len(b), 16)]
            self.tiles[name] = gray_tiles(os.path.join(REPO, f'gfx/tilesets/{name}.png'))


class Crystal:
    def __init__(self, root):
        self.root = root
        consts = open(os.path.join(root, 'constants/map_constants.asm')).read()
        self.dims = {m.group(1): (int(m.group(2)), int(m.group(3))) for m in
                     re.finditer(r'map_const (\w+),\s*(\d+),\s*(\d+)', consts)}
        attrs = open(os.path.join(root, 'data/maps/attributes.asm')).read()
        label_of = {m.group(2): m.group(1) for m in re.finditer(r'map_attributes (\w+), (\w+),', attrs)}
        maps_asm = open(os.path.join(root, 'data/maps/maps.asm')).read()
        tileset_of = dict(re.findall(r'^\s*map (\w+), TILESET_(\w+)', maps_asm, re.M))
        # blocks: several labels can share one file (data/maps/blocks.asm)
        blk_of, pending = {}, []
        for line in open(os.path.join(root, 'data/maps/blocks.asm')):
            m = re.match(r'^(\w+)_Blocks:', line)
            if m:
                pending.append(m.group(1))
            m = re.match(r'\s*INCBIN "([^"]+\.blk)"', line)
            if m:
                for label in pending:
                    blk_of[label] = os.path.join(root, m.group(1))
                pending = []
        self.maps = {}
        for const, label in label_of.items():
            if label in tileset_of and label in blk_of:
                self.maps[const] = (tileset_of[label].lower(), blk_of[label])
        self.metatiles = {}
        self.tiles = {}

    def tileset(self, name):
        if name not in self.metatiles:
            b = open(os.path.join(self.root, f'data/tilesets/{name}_metatiles.bin'), 'rb').read()
            self.metatiles[name] = [b[i:i + 16] for i in range(0, len(b), 16)]
            self.tiles[name] = gray_tiles(os.path.join(self.root, f'gfx/tilesets/{name}.png'))
        return self.metatiles[name], self.tiles[name]

    def tile(self, name, t):
        """tile number t of tileset name -> its pixels (None for the font's)"""
        tiles = self.tileset(name)[1]
        if t < 0x60:
            i = t
        elif t >= 0x80:
            i = 0x60 + t - 0x80
        else:
            return None
        return tiles[i] if i < len(tiles) else None


def pairs(g1, cr):
    """(gen 1 map, crystal map) with the same name (or an alias)"""
    out = []
    for name in g1.maps:
        c = ALIASES.get(name, name)
        if c not in cr.maps:
            c = c + '_1F'
        if c in cr.maps:
            out.append((name, c))
    return out


def grids(g1, cr, name, cname):
    gset, gpath = g1.maps[name]
    cset, cpath = cr.maps[cname]
    gw, gh = g1.dims[name]
    cw, ch = cr.dims[cname]
    gb = open(gpath, 'rb').read()
    cb = open(cpath, 'rb').read()
    return gset, [gb[i * gw:(i + 1) * gw] for i in range(gh)], cset, [cb[i * cw:(i + 1) * cw] for i in range(ch)]


def votes(g1, cr, offsets=None):
    """(gen 1 tileset, tile) -> Counter of (crystal tileset, tile)"""
    v = collections.defaultdict(collections.Counter)
    for name, cname in pairs(g1, cr):
        gset, ggrid, cset, cgrid = grids(g1, cr, name, cname)
        meta, _ = cr.tileset(cset)
        dx, dy = (offsets or {}).get(name, (0, 0))
        for y, row in enumerate(ggrid):
            cy = y + dy
            if not 0 <= cy < len(cgrid):
                continue
            for x, gblock in enumerate(row):
                cx = x + dx
                if not 0 <= cx < len(cgrid[cy]) or gblock >= len(g1.blocksets[gset]) or cgrid[cy][cx] >= len(meta):
                    continue
                gtiles = g1.blocksets[gset][gblock]
                ctiles = meta[cgrid[cy][cx]]
                for k in range(16):
                    v[(gset, gtiles[k])][(cset, ctiles[k])] += 1
    return v


def best_offsets(g1, cr, first):
    """per map pair, the block offset whose tiles agree most with the first
    votes' winners"""
    win = {k: c.most_common(1)[0][0] for k, c in first.items()}
    out = {}
    for name, cname in pairs(g1, cr):
        gset, ggrid, cset, cgrid = grids(g1, cr, name, cname)
        meta, _ = cr.tileset(cset)
        best = (0, (0, 0))
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                score = 0
                for y, row in enumerate(ggrid):
                    cy = y + dy
                    if not 0 <= cy < len(cgrid):
                        continue
                    for x, gblock in enumerate(row):
                        cx = x + dx
                        if not 0 <= cx < len(cgrid[cy]) or gblock >= len(g1.blocksets[gset]) or cgrid[cy][cx] >= len(meta):
                            continue
                        for k in range(16):
                            if win.get((gset, g1.blocksets[gset][gblock][k])) == (cset, meta[cgrid[cy][cx]][k]):
                                score += 1
                best = max(best, (score, (dx, dy)))
        out[name] = best[1]
    return out


def likeness(a, b):
    """1 for the same pixels, 0 for opposite shades everywhere"""
    return 1 - sum(abs(x - y) for x, y in zip(a, b)) / (64 * 3)


def choose(g1, cr, v):
    """(gen 1 tileset, tile) -> (crystal tileset, tile, how), for the tiles
    with a good enough match; the rest keep their graphics"""
    out = {}
    for gset in sorted(g1.tiles, key=lambda g: g != 'overworld'):  # the overworld first
        tiles = g1.tiles[gset]
        for t, px in enumerate(tiles):
            if not any(px):
                continue  # blank: nothing to redraw
            # the same picture as an overworld tile (the forest's grass):
            # the overworld's replacement, so they match
            if gset != 'overworld' and px in g1.tiles['overworld']:
                ot = g1.tiles['overworld'].index(px)
                if ('overworld', ot) in out:
                    o = out[('overworld', ot)]
                    out[(gset, t)] = (o[0], o[1], 'overworld', o[3])
                    continue
            cands = []
            c = v.get((gset, t), collections.Counter())
            total = sum(c.values()) or 1
            for key, n in c.most_common(8):
                cp = cr.tile(*key)
                if cp:
                    cands.append((likeness(px, cp), n / total, key, 'votes'))
            if gset in SAME_NUMBERS:
                # Crystal kept these numbers, its redrawn tile the default:
                # another only when it is all but the same and this one isn't
                same = (SAME_NUMBERS[gset], t)
                cp = cr.tile(*same)
                exact = [x for x in cands if x[0] >= 0.95]
                if (gset, t) in OVERRIDE:
                    o = OVERRIDE[(gset, t)]
                    out[(gset, t)] = (o[0], o[1], 'override', likeness(px, cr.tile(*o)))
                elif cp and t not in KEEP.get(gset, ()):
                    l = likeness(px, cp)
                    if exact and l < 0.9:
                        best = max(exact, key=lambda x: (x[0], x[1]))
                        out[(gset, t)] = (best[2][0], best[2][1], best[3], best[0])
                    else:
                        out[(gset, t)] = (same[0], same[1], 'number', l)
                continue
            # elsewhere Crystal redesigned the rooms: only a close redraw of
            # the same shape, about as bright, is taken
            bright = sum(px) / 64
            good = [x for x in cands if x[0] >= INDOOR_GOOD
                    and abs(sum(cr.tile(*x[2])) / 64 - bright) <= 0.25]
            if good:
                best = max(good, key=lambda x: (round(x[0], 2), x[1]))
                out[(gset, t)] = (best[2][0], best[2][1], best[3], best[0])
                continue
            # by likeness alone, strictly
            best = None
            for cset in LIKENESS.get(gset, []):
                if not os.path.exists(os.path.join(cr.root, f'data/tilesets/{cset}_metatiles.bin')):
                    continue
                ctiles = cr.tileset(cset)[1]
                for i, cp in enumerate(ctiles):
                    ct = i if i < 0x60 else 0x80 + i - 0x60
                    l = likeness(px, cp)
                    if l >= STRICT and (best is None or l > best[0]):
                        best = (l, cset, ct)
            if best and abs(sum(cr.tile(best[1], best[2])) / 64 - bright) <= 0.25:
                out[(gset, t)] = (best[1], best[2], 'likeness', best[0])
    return out


BLOCK_GOOD = 0.80  # least mean likeness of a whole block to a Crystal block


def candidate_tilesets(cr, v, gset):
    sets = {cs for (g, t), c in v.items() if g == gset for (cs, ct) in c}
    sets |= set(LIKENESS.get(gset, []))
    return sorted(s for s in sets if os.path.exists(os.path.join(cr.root, f'data/tilesets/{s}_metatiles.bin')))


def choose_blocks(g1, cr, v, gset):
    """Interiors: a Gen 1 block's tiles are replaced only together, by the
    Crystal block (metatile) that looks most like the whole of it, and only
    when that one is close enough; a tile used in several blocks takes the
    replacement most of them agree on."""
    blank = (0,) * 64
    tiles = g1.tiles[gset] + [blank] * (256 - len(g1.tiles[gset]))  # (blocks can name tiles past the end)
    proposals = collections.defaultdict(collections.Counter)
    sets = candidate_tilesets(cr, v, gset)
    for block in g1.blocksets[gset]:
        if all(not any(tiles[t]) for t in block):
            continue
        best = None
        for cs in sets:
            meta, _ = cr.tileset(cs)
            for m in meta:
                cps = [cr.tile(cs, ct) for ct in m]
                if any(cp is None for cp in cps):
                    continue
                score = sum(likeness(tiles[t], cp) for t, cp in zip(block, cps)) / 16
                if best is None or score > best[0]:
                    best = (score, cs, m)
        if best and best[0] >= BLOCK_GOOD:
            for t, ct in zip(block, best[2]):
                proposals[t][(best[1], ct)] += 1
    out = {}
    for t, c in proposals.items():
        (cs, ct), n = c.most_common(1)[0]
        l = likeness(tiles[t], cr.tile(cs, ct))
        if t < len(g1.tiles[gset]) and l < 1:  # (identical tiles: nothing to change)
            out[(gset, t)] = (cs, ct, 'block', l)
    return out


APPLY = ('overworld', 'forest')
# the other builds' variants of a tileset: a tile is replaced where it is
# the same as the main tileset's
VARIANTS = {'overworld': ['green/overworld', 'overworld_bluejp'], 'forest': ['green/forest']}
FLOWERS = ['flower/flower1', 'flower/flower2', 'green/flower/flower1', 'green/flower/flower2']


def write_png(tiles, path, width=16):
    rows = (len(tiles) + width - 1) // width
    im = Image.new('L', (width * 8, rows * 8), 255)
    for t, px in enumerate(tiles):
        tile = Image.new('L', (8, 8))
        tile.putdata([255 - 85 * p for p in px])
        im.paste(tile, ((t % width) * 8, (t // width) * 8))
    im.save(path)


def apply(g1, cr, chosen):
    lines = []
    for gset in APPLY:
        old = g1.tiles[gset]
        new = new_tiles(g1, cr, chosen, gset)
        write_png(new, os.path.join(REPO, f'gfx/tilesets/{gset}.png'))
        for var in VARIANTS.get(gset, []):
            path = os.path.join(REPO, f'gfx/tilesets/{var}.png')
            vt = gray_tiles(path)
            write_png([new[t] if t < len(old) and vt[t] == old[t] else vt[t] for t in range(len(vt))], path)
        for t in range(len(old)):
            pick = chosen.get((gset, t))
            if pick:
                lines.append(f'{gset} {t:02X} <- {pick[0]} {pick[1]:02X} ({pick[2]}, likeness {pick[3]:.2f})')
    # the flower: Crystal's two DMG frames
    frames = [gray_tiles(os.path.join(cr.root, f'gfx/tilesets/flower/dmg_{i}.png'))[0] for i in (1, 2)]
    for k, f in enumerate(FLOWERS):
        path = os.path.join(REPO, f'gfx/tilesets/{f}.png')
        if os.path.exists(path):
            write_png([frames[k % 2]], path, 1)
    lines.append('flower <- flower/dmg_1, flower/dmg_2')
    open(os.path.join(REPO, 'tools/crystal_tiles_choices.txt'), 'w').write('\n'.join(lines) + '\n')


def main(root, what):
    g1, cr = Gen1(), Crystal(root)
    print(len(pairs(g1, cr)), 'map pairs:', ' '.join(f'{a}={b}' for a, b in pairs(g1, cr)))
    first = votes(g1, cr)
    offs = best_offsets(g1, cr, first)
    v = votes(g1, cr, offs)
    print('offsets', {k: o for k, o in offs.items() if o != (0, 0)})
    if what == 'apply':
        apply(g1, cr, {k: c for k, c in choose(g1, cr, v).items() if k[0] in APPLY})
    if what == 'votes':
        for (gset, t), c in sorted(v.items()):
            total = sum(c.values())
            (cs, ct), n = c.most_common(1)[0]
            print(f'{gset:12} {t:02X} -> {cs}:{ct:02X} {n}/{total}')
    return g1, cr, v



def tile_image(pixels, scale=4):
    im = Image.new('L', (8, 8))
    im.putdata([255 - 85 * p for p in pixels])
    return im.resize((8 * scale, 8 * scale), Image.NEAREST)


def sheet(g1, cr, v, gset, out, choice=None):
    """gen 1 tile | crystal pick, for every tile of gen 1 tileset gset"""
    from PIL import ImageDraw
    tiles = g1.tiles[gset]
    cols = 8
    cw, chh = 32 * 2 + 24, 32 + 14
    rows = (len(tiles) + cols - 1) // cols
    im = Image.new('L', (cols * cw, rows * chh), 200)
    d = ImageDraw.Draw(im)
    for t, px in enumerate(tiles):
        x, y = (t % cols) * cw, (t // cols) * chh
        im.paste(tile_image(px), (x, y))
        pick = (choice or {}).get(t)
        c = v.get((gset, t))
        if pick is None and c:
            pick = c.most_common(1)[0][0]
        label = f'{t:02X}'
        if pick:
            cp = cr.tile(*pick)
            if cp:
                im.paste(tile_image(cp), (x + 36, y))
            if c:
                label += f' {pick[1]:02X} {100 * c[pick] // max(1, sum(c.values()))}%'
        d.text((x, y + 33), label, fill=0)
    im.save(out)


def choice_sheet(g1, cr, chosen, gset, out):
    """every tile of gen 1 tileset gset: its graphics, then what replaces it
    (blank where it stays), the Crystal tile and how it was found"""
    from PIL import ImageDraw
    tiles = g1.tiles[gset]
    cols, S = 8, 4
    cw, chh = 16 * S + 30, 8 * S + 14
    rows = (len(tiles) + cols - 1) // cols
    im = Image.new('L', (cols * cw, rows * chh), 200)
    d = ImageDraw.Draw(im)
    for t, px in enumerate(tiles):
        x, y = (t % cols) * cw, (t // cols) * chh
        im.paste(tile_image(px, S), (x, y))
        pick = chosen.get((gset, t))
        label = f'{t:02X}'
        if pick:
            im.paste(tile_image(cr.tile(pick[0], pick[1]), S), (x + 8 * S + 2, y))
            label += f' {pick[2][0]}{int(pick[3] * 100)}'
        d.text((x, y + 8 * S + 1), label, fill=0)
    im.save(out)


def new_tiles(g1, cr, chosen, gset, skip=()):
    """gen 1 tileset gset's tiles with the chosen ones replaced"""
    out = list(g1.tiles[gset])
    for t in range(len(out)):
        pick = chosen.get((gset, t))
        if pick and t not in skip:
            out[t] = cr.tile(pick[0], pick[1])
    return out


def render_map(g1, name, tiles, scale=2):
    """a gen 1 map drawn from its blocks with these tiles"""
    gset, path = g1.maps[name]
    w, h = g1.dims[name]
    blk = open(path, 'rb').read()
    im = Image.new('L', (w * 32, h * 32))
    for by in range(h):
        for bx in range(w):
            block = g1.blocksets[gset][blk[by * w + bx]]
            for k in range(16):
                im.paste(tile_image(tiles[block[k]], 1), (bx * 32 + (k % 4) * 8, by * 32 + (k // 4) * 8))
    return im.resize((w * 32 * scale, h * 32 * scale), Image.NEAREST)


def compare_map(g1, cr, chosen, name, out, scale=2):
    gset = g1.maps[name][0]
    a = render_map(g1, name, g1.tiles[gset], scale)
    b = render_map(g1, name, new_tiles(g1, cr, chosen, gset), scale)
    im = Image.new('L', (a.width * 2 + 8, a.height), 128)
    im.paste(a, (0, 0))
    im.paste(b, (a.width + 8, 0))
    im.save(out)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'votes')
