# inventory_move.rpy  -  Movable Inventory Items
#
# Hold the left mouse button on an item, drag it onto another square and let go: the two swap places.  Works in every
# grid the Inventory Scroll Mod draws (ITEMS, SPELLS, Equip > Appearance and Accessories), so it needs that mod on.
# While dragging, a faded "ghost" stays in the original square; letting go anywhere that isn't a square of the same
# grid moves nothing.  Item safety: see apex_grid.rpy.

init 7 python:
    if tom_mod_ok('inventory_move'):
        if str(tom_mod_status.get('inventory_scroll', '')).startswith('on'):
            APEX_GRID_MOVABLE = True
        else:
            tom_mod_status['inventory_move'] = 'off: needs the Inventory Scroll Mod'
