# Painting the rooms

The Pokémon Centers, the marts, the Celadon Hotel and the Indigo Plateau
lobby are built from paintings in this folder. Paint, run one command, run
`make`.

## The files you paint

Each is the whole room at 1x, in the Game Boy's four grays (255, 170, 85, 0).
Keep the size (or scale it up by a whole number).

| File | What it paints |
|---|---|
| `pokecenter/painted/celadon_pokecenter.png` (224x128) | every Pokémon Center (they share one layout) |
| `pokecenter/painted/celadon_hotel.png` (224x128) | the Celadon Hotel |
| `mart/painted/cerulean_mart.png` (128x128) | every mart (they share one layout) |
| `mart/painted/indigo_plateau_lobby.png` (256x192) | the Indigo Plateau lobby |

Beside them, `<map>_guide.png` shows the 32x32 blocks with their numbers and
what each 16x16 square does: red wall, blue counter, green door or warp,
yellow shelf, unmarked floor. What a square does never changes, whatever is
painted on it.

The rooms in one folder share a tileset: together they can use 96 different
8x8 tiles and 3 different counter tiles. The same tile used twice costs once,
so reusing tiles is how a room fits.

## Checking and building

You need Python 3 with Pillow (`pip install pillow`) and the repository
cloned with git (with its history: not `--depth 1`). From the repository's
folder (on Windows the command may be `py` or `python` instead of
`python3`):

```bash
python3 tools/rooms.py            # check every room; build the ones that fit
python3 tools/rooms.py --watch    # check again every time you save a painting
python3 tools/rooms.py --merge    # where a room is over, merge near-identical tiles for you
python3 tools/rooms.py --make     # and build the ROM afterwards
```

It prints, per tileset, how many tiles and counter tiles it needs. Where a
tileset is over, `<tileset>/twins.png` lists each tile that nearly matches
another: the two side by side, the pixels that differ in red, and every
place the tile is used, as 16x16 squares counted from the room's top left.
Make each one the same as its twin and the room fits. Or run with `--merge`:
the less used of each pair takes the other's picture (never more than 14 of
its 64 pixels changed).

When a tileset fits it is written into the game (its tiles, blocks, tables
and maps), and `<tileset>/<map>.png` shows exactly what the game will show.
Then `make` builds the ROM.

A block painted differently in two places becomes two blocks, so painting a
spot differently from the others is fine; it only costs the tiles it adds.
