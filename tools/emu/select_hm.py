"""SELECT uses Cut, Surf, Flash or Strength when the move is only in a party
mon's temporary field move slot (wTempFieldMoveSlots)."""
from story import *
from dxlib import screen
PARTY=[('PIKACHU',50,['THUNDERSHOCK']),('RATTATA',50,['TACKLE'])]
def prep(move):
    setup(badges=0xFF, party=PARTY)
    for i in range(6): m[A('wTempFieldMoveSlots')+i]=0
    m[A('wTempFieldMoveSlots')+1]=MV[move]     # the second mon's slot only
def select():
    g.press('select',10)
    for k in range(60): g.tick(4)
def find_tile(tile):
    """a coordinate next to (left of) the first screen tile `tile`, and the direction"""
    t=g.tiles(); px,py=m[A('wXCoord')],m[A('wYCoord')]
    for ty in range(0,18,2):
        for tx in range(0,20,2):
            if t[ty*20+tx]==tile:
                return px+(tx-8)//2, py+(ty-8)//2
    return None
res={}
# Strength: the Warden's boulder at (8,4), from (7,4) facing right
prep('STRENGTH'); enter('FUCHSIA_HOUSE_2', pos=(7,4))
for k in range(10): g.tick(10)
g.press('right',4); select()
res['strength']=bool(m[A('wd728')]&1)
# Surf: Pallet Town's shore, facing down at the water
prep('SURF'); enter('PALLET_TOWN', pos=(4,13))
for k in range(10): g.tick(10)
g.press('down',4); select()
for k in range(30): g.tick(4)
res['surf']=m[A('wWalkBikeSurfState')]==2
# Flash: Rock Tunnel, dark
prep('FLASH'); enter('ROCK_TUNNEL_1')
for k in range(10): g.tick(10)
m[A('wMapPalOffset')]=6
select()
res['flash']=m[A('wMapPalOffset')]==0
print(res, 'crash', crash[0])
# the same with the slot empty: nothing happens
for k in list(res): res[k]=None
def prep_empty(move):
    setup(badges=0xFF, party=PARTY)
    for i in range(6): m[A('wTempFieldMoveSlots')+i]=0
prep_empty('STRENGTH'); enter('FUCHSIA_HOUSE_2', pos=(7,4))
for k in range(10): g.tick(10)
g.press('right',4); select(); res['strength']=bool(m[A('wd728')]&1)
prep_empty('SURF'); enter('PALLET_TOWN', pos=(4,13))
for k in range(10): g.tick(10)
g.press('down',4); select()
for k in range(30): g.tick(4)
res['surf']=m[A('wWalkBikeSurfState')]==2
prep_empty('FLASH'); enter('ROCK_TUNNEL_1')
for k in range(10): g.tick(10)
m[A('wMapPalOffset')]=6; select(); res['flash']=m[A('wMapPalOffset')]==0
print('empty slot:', res)
# Cut: Cerulean City's tree at (19,28)
for slot in (True, False):
    for (x,y),d in (((18,28),'right'),((20,28),'left'),((19,29),'up'),((19,27),'down')):
        (prep if slot else prep_empty)('CUT')
        if not enter('CERULEAN_CITY',pos=(x,y)) or (m[A('wXCoord')],m[A('wYCoord')])!=(x,y): continue
        for k in range(10): g.tick(10)
        g.press(d,4)
        before=list(g.tiles())
        select()
        for k in range(40): g.tick(4)
        print('cut', 'slot' if slot else 'empty', (x,y), d, 'tree gone' if list(g.tiles())!=before else 'no change', 'crash', crash[0], flush=True)
        g.pb.screen.image.save(f'/tmp/pk30emu/out/cut_{slot}.png')
        break
