; pokecenter: made by tools/room_tiles.py; don't edit
DEF POKECENTER_COUNTER_1 EQU $06
DEF POKECENTER_COUNTER_2 EQU $18
DEF POKECENTER_COUNTER_3 EQU $19
DEF POKECENTER_WARPS EQUS "$0D"
DEF POKECENTER_DOORS EQUS "$0D"
; the shelves you read (BookshelfTileIDs), for tileset \1
MACRO pokecenter_shelves
	db \1, $16
	db_tx_pre PokemonStuffText
	db \1, $17
	db_tx_pre PokemonStuffText
	db \1, $1B
	db_tx_pre PokemonStuffText
ENDM
