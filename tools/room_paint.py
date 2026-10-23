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
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crystal_tiles  # noqa: E402
import room_tiles as R  # noqa: E402

GRAYS = (255, 170, 85, 0)
ART = os.path.join(R.REPO, 'art/rooms')


def room_maps(name):
    """the room tileset's maps, those with the same blocks merged: [(names, w, h, blocks)]"""
    maps = crystal_tiles.Gen1()
    seen = {}
    for mname, (gset, path) in sorted(maps.maps.items()):
        if gset != name:
            continue
        w, h = maps.dims[mname]
        key = (w, h, open(path, 'rb').read())
        seen.setdefault(key, []).append(mname)
    return [(names, key[0], key[1], key[2]) for key, names in seen.items()]


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
            for q, (walk, counter, warp, door, shelf) in enumerate(R.square_roles(g1, g1.blocks[b])):
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
    for names, w, h, blk in room_maps(name):
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


if __name__ == '__main__':
    root, what, name = sys.argv[1:4]
    if what == 'export':
        export(root, name)
