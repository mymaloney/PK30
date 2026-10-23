"""Paint Kanto's rooms over: export them as pictures, read the painting back.

    python3 tools/room_paint.py /tmp/pokecrystal export pokecenter

renders every map of a room tileset, as tools/room_tiles/<tileset>.txt picks
it, into art/rooms/<tileset>/:

- <map>.png, the map at 1x in the Game Boy's four grays (255, 170, 85, 0),
  to paint on: keep it the same size (or scale it by a whole number) and
  in those four grays (near ones are snapped to them);
- <map>_guide.png, the same at 4x with the 32x32 blocks, their numbers and
  what each 16x16 square does (red: wall, blue: counter, green: warp or
  door, yellow: shelf; unmarked: floor), for reference only.

A block used in several places is drawn the same everywhere in the game, so
a painting can change it in one place and leave the others, and the
importer will ask which to keep.
"""
import collections
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import room_tiles as R  # noqa: E402

GRAYS = (255, 170, 85, 0)
ART = os.path.join(R.REPO, 'art/rooms')


def square_image(squares):
    """four 8x8 tiles of shades -> a 16x16 gray image"""
    im = Image.new('L', (16, 16))
    for k, (px, color) in enumerate(squares):
        tile = Image.new('L', (8, 8))
        tile.putdata([GRAYS[p] for p in px])
        im.paste(tile, ((k % 2) * 8, (k // 2) * 8))
    return im


def render(src, picks, w, h, blk):
    im = Image.new('L', (w * 32, h * 32))
    for y in range(h):
        for x in range(w):
            for q, ref in enumerate(picks[blk[y * w + x]]):
                im.paste(square_image(src.square(ref)), (x * 32 + (q % 2) * 16, y * 32 + (q // 2) * 16))
    return im


def guide(g1, im, w, h, blk, scale=4):
    big = im.convert('RGB').resize((im.width * scale, im.height * scale), Image.NEAREST)
    over = Image.new('RGBA', big.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    S = 16 * scale
    for y in range(h):
        for x in range(w):
            b = blk[y * w + x]
            for q, (walk, counter, warp, door, shelf) in enumerate(R.square_roles(g1, g1.blocks[b], b)):
                sx, sy = (x * 2 + q % 2) * S, (y * 2 + q // 2) * S
                color = ((255, 210, 0, 90) if shelf else (40, 110, 255, 90) if counter else
                         (0, 200, 80, 90) if warp or door else None if walk else (255, 40, 40, 45))
                if color:
                    d.rectangle([sx, sy, sx + S - 1, sy + S - 1], fill=color)
                d.rectangle([sx, sy, sx + S - 1, sy + S - 1], outline=(255, 255, 255, 60))
            d.rectangle([x * 2 * S, y * 2 * S, (x + 1) * 2 * S - 1, (y + 1) * 2 * S - 1], outline=(255, 0, 255, 200), width=2)
            d.rectangle([x * 2 * S + 3, y * 2 * S + 3, x * 2 * S + 21, y * 2 * S + 15], fill=(255, 255, 255, 220))
            d.text((x * 2 * S + 5, y * 2 * S + 4), f'{b:02X}', fill=(200, 0, 120, 255))
    return Image.alpha_composite(big.convert('RGBA'), over).convert('RGB')


def export(crystal_root, name):
    g1 = R.Gen1Room(name)
    src = R.Sources(g1, crystal_root)
    picks, notes = R.read_picks(name)
    for b in range(len(g1.blocks)):
        picks.setdefault(b, [('gen1', b, q) for q in range(4)])
    out = os.path.join(ART, name)
    os.makedirs(out, exist_ok=True)
    written = []
    for names, paths, w, h, blk in layouts(name):
        stem = names[0].lower()
        im = render(src, picks, w, h, blk)
        im.save(os.path.join(out, f'{stem}.png'))
        guide(g1, im, w, h, blk).save(os.path.join(out, f'{stem}_guide.png'))
        written.append((stem, names))
    readme = [f'# {name}: rooms to paint over (tools/room_paint.py)', '',
              'Paint on the plain PNGs, in the four grays (255, 170, 85, 0), keeping the size.',
              'The _guide PNGs show the blocks and what each square does:',
              'red wall, blue counter, green warp or door, yellow shelf, unmarked floor.', '']
    for stem, names in written:
        readme.append(f'- {stem}.png: ' + ', '.join(n.lower() for n in names))
    open(os.path.join(out, 'README.md'), 'w').write('\n'.join(readme) + '\n')
    print('\n'.join(os.path.join(out, f'{s}.png') for s, _ in written))


def layouts(name):
    """the room tileset's maps (as Gen 1 had them), those with the same blocks
    merged: [(names, paths, w, h, blocks)]"""
    seen = {}
    for mname, path, w, h in R.room_maps(name):
        # Gen 1's map, as it was before blocks were painted apart
        key = (w, h, R.git_show(os.path.relpath(path, R.REPO)))
        names, paths = seen.setdefault(key, ([], []))
        names.append(mname)
        if path not in paths:
            paths.append(path)
    return [(names, paths, key[0], key[1], key[2]) for key, (names, paths) in seen.items()]


def snap(im):
    """a painting -> its pixels as shades 0-3 (white to black), nearest gray"""
    g = im.convert('L')
    return g.point(lambda v: min(range(4), key=lambda i: abs(GRAYS[i] - v)))


def read_painting(path, w, h):
    im = Image.open(path)
    if im.size != (w * 32, h * 32):
        k = im.width // (w * 32)
        if k < 1 or im.size != (w * 32 * k, h * 32 * k):
            raise SystemExit(f'{path}: {im.size}, not {w * 32}x{h * 32} or a whole multiple')
        im = im.resize((w * 32, h * 32), Image.NEAREST)
    return snap(im)


def painted_blocks(g1, src, picks, name):
    """every block as painted -> (uses for room_tiles.assemble, new map blocks per layout)

    A Gen 1 block painted the same everywhere keeps its number; one painted
    differently somewhere becomes a new block there (after the Gen 1 ones),
    with the same roles. Colors (MORE COLOR) come from the squares the picks
    named."""
    found = []  # (layout, x, y, gen 1 block, 32x32 shades)
    lays = layouts(name)
    for names, paths, w, h, blk in lays:
        art = os.path.join(ART, name, f'{names[0].lower()}.png')
        if not os.path.exists(art):
            raise SystemExit(f'no painting {art}')
        px = read_painting(art, w, h).load()
        for y in range(h):
            for x in range(w):
                shades = tuple(px[x * 32 + i, y * 32 + j] for j in range(32) for i in range(32))
                found.append((names[0], x, y, blk[y * w + x], shades))
    versions = {}
    for lay, x, y, b, sh in found:
        versions.setdefault(b, collections.Counter())[sh] += 1
    ids = {}  # (gen 1 block, shades) -> block number
    for b, c in versions.items():
        ids[(b, c.most_common(1)[0][0])] = b
    extra = len(g1.blocks)
    for b in sorted(versions):
        for sh, n in versions[b].most_common()[1:]:
            ids[(b, sh)] = extra
            extra += 1
    source = {i: key for key, i in ids.items()}
    uses = []
    filler = None
    borders = R.border_blocks(name)
    for i in range(extra):
        if i not in source and i in borders:  # drawn past the map's edges: as picked, no roles
            uses.append([None] * 16)
            for q, ref in enumerate(picks[i]):
                for k, (px, color) in zip(R.QUADS[q], src.square(ref)):
                    uses[-1][k] = (px, color, None)
            continue
        if i not in source:  # a block no map shows: any pictures, no roles
            uses.append(None)
            continue
        b, sh = source[i]
        roles = square_roles_of(g1, b)
        colors = [color for ref in picks[b] for px, color in src.square(ref)]
        row = [None] * 16
        for k in range(16):
            tx, ty = (k % 4) * 8, (k // 4) * 8
            px = tuple(sh[(ty + j) * 32 + tx + i2] for j in range(8) for i2 in range(8))
            q = (k // 8) * 2 + (k % 4) // 2  # the square tile k is in
            color = colors[q * 4 + R.QUADS[q].index(k)]
            row[k] = (px, color, roles[R.BOTTOM_LEFT.index(k)] if k in R.BOTTOM_LEFT else None)
        uses.append(row)
        filler = filler or row
    uses = [u if u else [(px, c, None) for px, c, r in filler] for u in uses]
    new_maps = []
    for names, paths, w, h, blk in lays:
        cells = {(x, y): ids[(b, sh)] for lay, x, y, b, sh in found if lay == names[0]}
        new_maps.append((paths, bytes(cells[(x, y)] for y in range(h) for x in range(w))))
    return uses, new_maps, {b: len(c) for b, c in versions.items() if len(c) > 1}


def guides(name):
    """a guide beside each painting: blocks, numbers, roles (Gen 1's blocks)"""
    g1 = R.Gen1Room(name)
    for names, paths, w, h, blk in layouts(name):
        art = os.path.join(ART, name, f'{names[0].lower()}.png')
        if os.path.exists(art):
            im = read_painting(art, w, h).point(lambda v: GRAYS[min(v, 3)])
            guide(g1, im, w, h, blk).save(art.replace('.png', '_guide.png'))


def square_roles_of(g1, b):
    return R.square_roles(g1, g1.blocks[b], b)


def build(crystal_root, name):
    g1 = R.Gen1Room(name)
    src = R.Sources(g1, crystal_root)
    picks, notes = R.read_picks(name)
    for b in range(len(g1.blocks)):
        picks.setdefault(b, [('gen1', b, q) for q in range(4)])
    uses, new_maps, split = painted_blocks(g1, src, picks, name)
    built, problems = R.assemble(uses)
    print(f'{name}: {len(uses)} blocks ({sum(split.values()) - len(split)} new, from '
          f'{", ".join(f"{b:02X}" for b in sorted(split)) or "none"}), {len(built[0])} tiles, '
          f'{len(built[3])} counter tiles')
    if problems:
        raise SystemExit('\n'.join(problems))
    R.write(name, g1, built)
    guides(name)
    for paths, data in new_maps:
        for path in paths:
            open(path, 'wb').write(data)


def tile_count(crystal_root, name):
    g1 = R.Gen1Room(name)
    src = R.Sources(g1, crystal_root)
    picks, notes = R.read_picks(name)
    for b in range(len(g1.blocks)):
        picks.setdefault(b, [('gen1', b, q) for q in range(4)])
    uses, new_maps, split = painted_blocks(g1, src, picks, name)
    built, problems = R.assemble(uses)
    return len({px for row in uses for px, c, r in row}), problems


def optimize(crystal_root, name, limit=14):
    """Bring a room tileset's paintings within its tiles: the two most alike
    tiles (the fewest pixels apart, never more than limit) become one, the
    one used less taking the other's picture, until it fits. The paintings
    are saved as merged; the painter's own are kept in painted/, and
    changes.png marks every pixel that changed (red), at 4x."""
    lays = layouts(name)
    arts, pics = {}, collections.Counter()
    for names, paths, w, h, blk in lays:
        stem = names[0].lower()
        mine = os.path.join(ART, name, 'painted', f'{stem}.png')
        path = mine if os.path.exists(mine) else os.path.join(ART, name, f'{stem}.png')
        im = read_painting(path, w, h)
        arts[stem] = (im, w, h)
        px = im.load()
        for ty in range(h * 4):
            for tx in range(w * 4):
                pics[tuple(px[tx * 8 + i, ty * 8 + j] for j in range(8) for i in range(8))] += 1

    def apart(a, b):
        return sum(x != y for x, y in zip(a, b))
    into = {}  # picture -> the picture it now is

    def now(t):
        while t in into:
            t = into[t]
        return t

    def save():
        os.makedirs(os.path.join(ART, name, 'painted'), exist_ok=True)
        marks = []
        for stem, (im, w, h) in arts.items():
            mine = os.path.join(ART, name, 'painted', f'{stem}.png')
            if not os.path.exists(mine):
                im.point(lambda v: GRAYS[min(v, 3)]).save(mine)
            out = im.copy()
            px, op = im.load(), out.load()
            for ty in range(h * 4):
                for tx in range(w * 4):
                    t = now(tuple(px[tx * 8 + i, ty * 8 + j] for j in range(8) for i in range(8)))
                    for j in range(8):
                        for i in range(8):
                            op[tx * 8 + i, ty * 8 + j] = t[j * 8 + i]
            out.point(lambda v: GRAYS[min(v, 3)]).save(os.path.join(ART, name, f'{stem}.png'))
            big = out.point(lambda v: GRAYS[min(v, 3)]).convert('RGB').resize((w * 128, h * 128), Image.NEAREST)
            d = ImageDraw.Draw(big)
            for y in range(h * 32):
                for x in range(w * 32):
                    if px[x, y] != op[x, y]:
                        d.rectangle([x * 4, y * 4, x * 4 + 3, y * 4 + 3], fill=(230, 30, 30))
            marks.append(big)
        sheet = Image.new('RGB', (max(m.width for m in marks), sum(m.height + 8 for m in marks)), (60, 60, 60))
        y = 0
        for m in marks:
            sheet.paste(m, (0, y))
            y += m.height + 8
        sheet.save(os.path.join(ART, name, 'changes.png'))

    save()
    count, problems = tile_count(crystal_root, name)
    pairs = sorted((apart(a, b), a, b) for i, a in enumerate(pics) for b in list(pics)[i + 1:])
    merged = []
    for d, a, b in pairs:
        if not problems:
            break
        if d > limit:
            break
        a, b = now(a), now(b)
        if a == b:
            continue
        keep, lose = (a, b) if pics[a] >= pics[b] else (b, a)
        # every picture that becomes this one stays within limit of it
        if any(apart(t, keep) > limit for t in list(into) + [lose] if now(t) == lose or t == lose):
            continue
        into[lose] = keep
        pics[keep] += pics[lose]
        merged.append(d)
        save()
        count, problems = tile_count(crystal_root, name)
    print(f'{name}: {len(merged)} tiles merged (at most {max(merged or [0])} pixels apart), '
          f'{count} pictures' + (': ' + '; '.join(problems) if problems else ', fits'))


if __name__ == '__main__':
    root, what, name = sys.argv[1:4]
    if what == 'export':
        export(root, name)
    elif what == 'build':
        build(root, name)
    elif what == 'guides':
        guides(name)
    elif what == 'optimize':
        optimize(root, name)
