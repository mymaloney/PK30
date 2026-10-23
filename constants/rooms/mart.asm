; mart: made by tools/room_tiles.py; don't edit
DEF MART_COUNTER_1 EQU $06
DEF MART_COUNTER_2 EQU $18
DEF MART_COUNTER_3 EQU $19
DEF MART_WARPS EQUS "$0D,$FF"  ; ends with $FF
DEF MART_DOORS EQUS "$0D,$00"  ; ends with $00
; the shelves you read (BookshelfTileIDs), for tileset \1
MACRO mart_shelves
	db \1, $16
	db_tx_pre PokemonStuffText
	db \1, $17
	db_tx_pre PokemonStuffText
	db \1, $1B
	db_tx_pre PokemonStuffText
ENDM
