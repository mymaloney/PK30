"""Check painted rooms and build them into the game, on your own machine.

    python3 tools/rooms.py              check every room, build those that fit
    python3 tools/rooms.py --merge      also merge near-identical tiles where a room is over
    python3 tools/rooms.py --watch      check again whenever a painting is saved
    python3 tools/rooms.py --make       run make after building
    python3 tools/rooms.py mart         only the mart tileset (or pokecenter)

Paint in art/rooms/<tileset>/painted/<map>.png: the room at 1x in the Game
Boy's four grays (255, 170, 85, 0), the same size as before. For each room
tileset this prints whether it fits (at most 96 tiles and 3 counter tiles),
and where it doesn't, art/rooms/<tileset>/twins.png shows the tiles that
nearly match another, the pixels that differ and where they are: make them
the same and the room fits. When it fits it writes the tileset, its tables
and its maps (art/rooms/<tileset>/<map>.png is then what the game shows);
run make to build the ROM.

Needs Python 3 and Pillow (pip install pillow), and git (Gen 1's rooms are
read from the repository's history). Every square keeps what it does in
Gen 1 (walls, floor, counters, doors), whatever is painted on it.
"""
import argparse
import os
import shutil
import subprocess
import sys
import time

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import room_paint as P  # noqa: E402
import room_tiles as R  # noqa: E402

LIMIT = 0x60  # tiles a Gen 1 tileset holds
NEAR = 14     # the most pixels (of 64) --merge changes in a tile


def painted_dir(name):
    return os.path.join(P.ART, name, 'painted')


def load_paintings(name):
    """{map: shades image} from painted/, and what was wrong with them"""
    notes, arts = [], {}
    os.makedirs(painted_dir(name), exist_ok=True)
    for names, paths, w, h, blk in P.layouts(name):
        stem = names[0].lower()
        path = os.path.join(painted_dir(name), f'{stem}.png')
        built = os.path.join(P.ART, name, f'{stem}.png')
        if not os.path.exists(path):
            if not os.path.exists(built):
                notes.append(f'{stem}.png: missing (python3 tools/room_paint.py export {name} makes a start)')
                continue
            shutil.copy(built, path)  # start from what the game shows
        im = Image.open(path)
        size = (w * 32, h * 32)
        if im.size != size:
            k = im.width // size[0]
            if k >= 1 and im.size == (size[0] * k, size[1] * k):
                im = im.resize(size, Image.NEAREST)
            elif im.width <= size[0] and im.height <= size[1] and os.path.exists(built):
                # cropped: the rest from what the game shows now
                full = Image.open(built).convert('L')
                full.paste(im.convert('L'), (0, 0))
                notes.append(f'{stem}.png: {im.width}x{im.height}, should be {size[0]}x{size[1]}; '
                             f'the missing right/bottom edge was taken from the game\'s current room')
                im = full
            else:
                notes.append(f'{stem}.png: {im.width}x{im.height}, should be {size[0]}x{size[1]}')
                continue
        g = im.convert('L')
        off = sum(1 for v in g.tobytes() if v not in P.GRAYS)
        if off:
            notes.append(f'{stem}.png: {off} pixels are not one of the four grays; taken as the nearest')
        arts[stem] = P.snap(g)
    return arts, notes


def tiles_of(im):
    px = im.load()
    return {(tx, ty): tuple(px[tx * 8 + i, ty * 8 + j] for j in range(8) for i in range(8))
            for ty in range(im.height // 8) for tx in range(im.width // 8)}


def apart(a, b):
    return sum(x != y for x, y in zip(a, b))


def merge_plan(name, arts, g1, chosen):
    """merge the most alike tiles until the tileset fits -> ({tile: tile it becomes}, merged arts)"""
    uses = {}
    for stem, im in arts.items():
        for t in tiles_of(im).values():
            uses[t] = uses.get(t, 0) + 1
    into = {}

    def now(t):
        while t in into:
            t = into[t]
        return t

    def apply():
        out = {}
        for stem, im in arts.items():
            new = im.copy()
            px = new.load()
            for (tx, ty), t in tiles_of(im).items():
                t = now(t)
                for j in range(8):
                    for i in range(8):
                        px[tx * 8 + i, ty * 8 + j] = t[j * 8 + i]
            out[stem] = new
        return out
    pics = list(uses)
    pairs = sorted((apart(a, b), i, j) for i, a in enumerate(pics) for j, b in enumerate(pics) if i < j)
    merged = arts
    count, counters, problems = P.tile_count(name, g1, chosen, merged)
    for d, i, j in pairs:
        if count <= LIMIT or d > NEAR:
            break
        a, b = now(pics[i]), now(pics[j])
        if a == b:
            continue
        keep, lose = (a, b) if uses[a] >= uses[b] else (b, a)
        group = [t for t in pics if now(t) == lose]
        if any(apart(t, keep) > NEAR for t in group):
            continue
        into[lose] = keep
        uses[keep] += uses[lose]
        merged = apply()
        count, counters, problems = P.tile_count(name, g1, chosen, merged)
    return {t: now(t) for t in pics if now(t) != t}, merged


def twins_sheet(name, arts, plan, out):
    """each tile the merge changes: as painted, what it becomes, the pixels
    that differ, and where it is"""
    where = {}
    for stem, im in arts.items():
        short = {'celadon_pokecenter': 'center', 'celadon_hotel': 'hotel', 'cerulean_mart': 'mart',
                 'indigo_plateau_lobby': 'lobby'}.get(stem, stem.replace('_', ' '))
        for (tx, ty), t in tiles_of(im).items():
            if t in plan:
                where.setdefault(t, []).append(f'{short} ({tx // 2},{ty // 2})')
    rows = sorted(plan.items(), key=lambda kv: (-apart(*kv), kv[0]))
    sheet = Image.new('RGB', (720, max(1, len(rows)) * 84 + 40), (244, 244, 236))
    d = ImageDraw.Draw(sheet)
    d.text((10, 10), f'{name}: {len(rows)} tiles to make the same as their twin. Left: as painted; right: '
                     f'its twin. Red: the pixels that differ. (x,y): 16x16 squares from the top left.',
           fill=(30, 30, 30))

    def tile(t, other):
        im = Image.new('RGB', (8, 8))
        im.putdata([(P.GRAYS[p],) * 3 for p in t])
        im = im.resize((64, 64), Image.NEAREST)
        dd = ImageDraw.Draw(im)
        for k in range(64):
            if t[k] != other[k]:
                dd.rectangle([(k % 8) * 8, (k // 8) * 8, (k % 8) * 8 + 7, (k // 8) * 8 + 7], outline=(230, 30, 30), width=2)
        return im
    for r, (t, twin) in enumerate(rows):
        y = 34 + r * 84
        sheet.paste(tile(t, twin), (10, y))
        sheet.paste(tile(twin, t), (90, y))
        d.text((170, y + 6), f'{apart(t, twin)} pixels differ', fill=(30, 30, 30))
        spots = where.get(t, [])
        for line in range(0, min(len(spots), 9), 3):
            d.text((170, y + 22 + line // 3 * 14), ', '.join(spots[line:line + 3]), fill=(70, 70, 70))
        if len(spots) > 9:
            d.text((170, y + 64), f'and {len(spots) - 9} more', fill=(70, 70, 70))
    sheet.save(out)


def save_arts(name, arts):
    for stem, im in arts.items():
        im.point(lambda v: P.GRAYS[min(v, 3)]).save(os.path.join(P.ART, name, f'{stem}.png'))


def check(name, merge):
    """-> True if the game's files were rewritten"""
    g1, chosen = R.Gen1Room(name), P.picked(name)
    arts, notes = load_paintings(name)
    for n in notes:
        print(f'  ! {n}')
    if len(arts) < len(P.layouts(name)):
        print(f'{name}: not built (a painting is missing or the wrong size)')
        return False
    count, counters, problems = P.tile_count(name, g1, chosen, arts)
    twins = os.path.join(P.ART, name, 'twins.png')
    status = f'{count}/{LIMIT} tiles, {counters}/3 counter tiles'
    if not problems:
        print(f'{name}: fits as painted ({status})')
        if os.path.exists(twins):
            os.remove(twins)
        save_arts(name, arts)
    else:
        if count > LIMIT:
            plan, merged = merge_plan(name, arts, g1, chosen)
            twins_sheet(name, arts, plan, twins)
            m_count, m_counters, m_problems = P.tile_count(name, g1, chosen, merged)
            worst = max((apart(a, b) for a, b in plan.items()), default=0)
            print(f'{name}: over ({status}); {len(plan)} tiles have a near-twin (at most {worst} pixels '
                  f'apart): see {os.path.relpath(twins, R.REPO)}')
            if m_problems:
                print(f'  merging them all still leaves: {"; ".join(m_problems)}. Simplify the room.')
                return False
            if not merge:
                print('  make those the same and run again, or run with --merge to merge them for you')
                return False
            print(f'  merged them ({m_count}/{LIMIT} tiles); art/rooms/{name}/<map>.png is the result')
            save_arts(name, merged)
        else:
            print(f'{name}: {"; ".join(problems)}')
            return False
    P.build(name, quiet=True)
    P.guides(name)
    print(f'  built: gfx/tilesets/{name}.png, gfx/blocksets/{name}.bst, its tables and maps')
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('tilesets', nargs='*', default=list(R.ROOMS), help=', '.join(R.ROOMS))
    ap.add_argument('--merge', action='store_true', help='merge near-identical tiles to fit')
    ap.add_argument('--watch', action='store_true', help='check again whenever a painting is saved')
    ap.add_argument('--make', action='store_true', help='run make after building')
    args = ap.parse_args()
    for t in args.tilesets:
        if t not in R.ROOMS:
            ap.error(f'{t}: not a room tileset ({", ".join(R.ROOMS)})')

    def run():
        built = [t for t in args.tilesets if check(t, args.merge)]
        if built and args.make:
            print('make ...')
            done = subprocess.run(['make'], cwd=R.REPO)
            print('make: done' if done.returncode == 0 else 'make: failed (see above)')
        elif built:
            print('run make to build the ROM')

    run()
    if args.watch:
        def stamp():
            return {f: os.path.getmtime(os.path.join(painted_dir(t), f)) for t in args.tilesets
                    for f in sorted(os.listdir(painted_dir(t))) if f.endswith('.png')}
        seen = stamp()
        print('watching art/rooms/*/painted/ (ctrl+c to stop)')
        try:
            while True:
                time.sleep(1)
                if stamp() != seen:
                    time.sleep(0.5)  # let the save finish
                    seen = stamp()
                    print()
                    run()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
