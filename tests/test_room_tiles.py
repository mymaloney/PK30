"""Rooms rebuilt from Crystal's tiles (tools/room_tiles.py) play
as Gen 1's did: in every map, every 16x16 square's bottom-left tile (the one
Gen 1 checks) is walkable, a counter, a warp, a door or a shelf exactly
where the Gen 1 tile was (a counter no one can be talked to over may be a
wall)."""
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

import crystal_tiles  # noqa: E402
import room_tiles  # noqa: E402


def built_roles(name):
    """the tileset as built: tile -> role, as Gen1Room.role gives it"""
    walk = set(open(os.path.join(ROOT, f'gfx/tilesets/{name}.tilecoll'), 'rb').read().split(b'\xff')[0])
    consts = open(os.path.join(ROOT, f'constants/rooms/{name}.asm')).read()
    counters = {int(v, 16) for v in re.findall(r'_COUNTER_\d EQU \$(\w+)', consts)} - {0xFF}
    warps = {int(v, 16) for v in re.findall(r'\$(\w\w)', re.search(r'_WARPS EQUS "([^"]*)"', consts).group(1))} - {0xFF}
    doors = {int(v, 16) for v in re.findall(r'\$(\w\w)', re.search(r'_DOORS EQUS "([^"]*)"', consts).group(1))} - {0}
    shelves = {int(t, 16): text for t, text in re.findall(r'db \\1, \$(\w+)\s*\n\s*db_tx_pre (\w+)', consts)}
    return lambda t: (t in walk, t in counters, t in warps, t in doors, shelves.get(t))


class RoomTiles(unittest.TestCase):
    def test_every_square_keeps_its_role(self):
        for name in room_tiles.ROOMS:
            g1 = room_tiles.Gen1Room(name)
            bst = open(os.path.join(ROOT, f'gfx/blocksets/{name}.bst'), 'rb').read()
            new = [bst[i:i + 16] for i in range(0, len(bst), 16)]
            role = built_roles(name)
            maps = room_tiles.room_maps(name)
            self.assertTrue(maps)
            for mname, path, w, h in maps:
                # the map as Gen 1 had it: blocks painted two ways became two blocks
                old = room_tiles.git_show(os.path.relpath(path, ROOT))
                now = open(path, 'rb').read()
                self.assertEqual(len(now), w * h, mname)
                for i, (b_old, b_new) in enumerate(zip(old, now)):
                    # (a counter no one can be talked to over is a wall)
                    wanted = room_tiles.square_roles(g1, g1.blocks[b_old], b_old)
                    for q, k in enumerate(room_tiles.BOTTOM_LEFT):
                        was = wanted[q]
                        got = role(new[b_new][k])
                        # a plain wall may turn counter (talking over it finds no one)
                        if was == (False, False, False, False, None) and got == (False, True, False, False, None):
                            continue
                        self.assertEqual(got, was, f'{mname} ({i % w},{i // w}) block {b_old:02X}->{b_new:02X} '
                                                   f'square {room_tiles.BOTTOM_LEFT.index(k)}')

    def test_tileset_fits(self):
        for name in room_tiles.ROOMS:
            bst = open(os.path.join(ROOT, f'gfx/blocksets/{name}.bst'), 'rb').read()
            self.assertLess(max(bst), 0x60)
            tiles = crystal_tiles.gray_tiles(os.path.join(ROOT, f'gfx/tilesets/{name}.png'))
            self.assertLessEqual(max(bst) + 1, len(tiles))


if __name__ == '__main__':
    unittest.main()
