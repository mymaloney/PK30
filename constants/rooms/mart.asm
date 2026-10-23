; mart: made by tools/room_tiles.py; don't edit
DEF MART_COUNTER_1 EQU $08
DEF MART_COUNTER_2 EQU $19
DEF MART_COUNTER_3 EQU $FF
DEF MART_WARPS EQUS "$10,$1D,$FF"  ; ends with $FF
DEF MART_DOORS EQUS "$10,$1D,$00"  ; ends with $00
; the shelves you read (BookshelfTileIDs), for tileset \1
MACRO mart_shelves
	db \1, $17
	db_tx_pre PokemonStuffText
ENDM
