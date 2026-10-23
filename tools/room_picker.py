"""A page to choose a room tileset's squares by eye (tools/room_tiles.py).

Every Gen 1 block's four 16x16 squares can each take a square from Crystal's
tilesets, FireRed/LeafGreen's (in four shades) or Gen 1's own. The page
shows every map of the tileset as picked, cycles the candidates for a
square (or Crystal's whole blocks for a block), counts the tiles against the
$60 a tileset holds, and gives the picks file to paste into
tools/room_tiles/<tileset>.txt.

    python3 tools/room_picker.py /tmp/pokecrystal /tmp/pokefirered pokecenter picker.html
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crystal_tiles  # noqa: E402
import frlg_tiles  # noqa: E402
import room_tiles as R  # noqa: E402

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'room_picker.html')
ROLE_NAMES = ('walk', 'counter', 'warp', 'door', 'shelf')


def role_key(role):
    return ','.join(['1' if role[0] else '0', '1' if role[1] else '0', '1' if role[2] else '0',
                     '1' if role[3] else '0', role[4] or ''])


def main(crystal_root, frlg_root, name, out):
    g1 = R.Gen1Room(name)
    src = R.Sources(g1, crystal_root, frlg_root)
    atlas, atlas_ids = [], {}
    squares, by_pixels, ref_index = [], {}, {}
    groups = []

    def tile_id(px):
        if px not in atlas_ids:
            atlas_ids[px] = len(atlas)
            atlas.append(''.join(map(str, px)))
        return atlas_ids[px]

    def add(group, ref):
        tiles = tuple(tile_id(px) for px, color in src.square(ref))
        text = R.ref_text(ref)
        if tiles in by_pixels:  # the same picture under another name
            ref_index[text] = by_pixels[tiles]
            return by_pixels[tiles]
        by_pixels[tiles] = len(squares)
        ref_index[text] = len(squares)
        squares.append(dict(ref=text, g=len(groups) - 1, t=tiles))
        return len(squares) - 1

    whole = []
    for cs, cset in src.cr.items():
        groups.append(f'Crystal {cs}')
        for m in range(len(cset.blocks)):
            if not any(cset.tile(t) for t in cset.blocks[m]):
                continue
            whole.append(dict(name=f'{cs}:{m:02X}', sq=[add(None, ('cr', cs, m, q)) for q in range(4)]))
    for fs, fset in src.fr.items():
        groups.append(f'FireRed {fs}')
        for m in fset.secondary_squares():
            if any(any(px) for px, c in src.square(('frlg', fs, m))):
                add(None, ('frlg', fs, m))
    for fs, fset in list(src.fr.items())[:1]:
        groups.append('FireRed building (shared)')
        for m in range(frlg_tiles.PRIMARY_TILES):
            if fset.metatiles[m] and any(any(px) for px, c in src.square(('frlg', fs, m))):
                add(None, ('frlg', fs, m))

    # Gen 1's own last: an identical Crystal or FireRed square keeps its name
    groups.append(f'Gen 1 {name}')
    for b in range(len(g1.blocks)):
        for q in range(4):
            add(None, ('gen1', b, q))
    picks, notes = R.read_picks(name)
    blocks = []
    for b, gb in enumerate(g1.blocks):
        pick = picks.get(b) or [('gen1', b, q) for q in range(4)]
        cur = []
        for i, ref in enumerate(pick):
            text = R.ref_text(ref)
            cur.append(ref_index[text] if text in ref_index else add(None, ref))
        names = [R.ref_text(ref, i) for i, ref in enumerate(pick)]
        blocks.append(dict(names=names, orig=[ref_index[R.ref_text(('gen1', b, q))] for q in range(4)], pick=cur, note=notes.get(b, ''),
                           roles=[role_key(r) for r in R.square_roles(g1, gb)]))

    maps = crystal_tiles.Gen1()
    seen = {}
    for mname, (gset, path) in sorted(maps.maps.items()):
        if gset != name:
            continue
        data = open(path, 'rb').read()
        w, h = maps.dims[mname]
        key = (w, h, data)
        if key in seen:
            seen[key]['names'].append(mname)
        else:
            seen[key] = dict(names=[mname], w=w, h=h, blk=list(data))
    data = dict(room=name, atlas=atlas, squares=squares, groups=groups, whole=whole, blocks=blocks,
                maps=list(seen.values()))
    html = open(TEMPLATE).read().replace('/*DATA*/null', json.dumps(data, separators=(',', ':')))
    open(out, 'w').write(html)
    print(f'{out}: {len(squares)} squares, {len(atlas)} tiles, {len(whole)} Crystal blocks, {len(seen)} maps')


if __name__ == '__main__':
    main(*sys.argv[1:5])
