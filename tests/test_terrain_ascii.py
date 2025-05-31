import pytest
from TerrainAscii import TerrainAscii
from godot import Vector2i

class DummyTileMap(TerrainAscii):
    def __init__(self):
        # simulate TileMap without actual rendering
        self.cells = {}
        super().__init__()
    def set_cell(self, layer, pos, tile):
        # record cell updates
        self.cells[(pos.x, pos.y)] = tile

@pytest.fixture(autouse=True)
def patch_tilemap(monkeypatch):
    # Ensure our DummyTileMap is used when instantiating
    monkeypatch.setattr('TerrainAscii', DummyTileMap)

def test_full_update(tmp_path):
    ascii = DummyTileMap()
    # small 2x2 map: values [0.1, 0.5, 0.9, 0.0]
    data = [0.1,0.5,0.9,0.0]
    ascii.update_tiles(0,0,data,1)
    # verify all 4 cells set
    assert ascii.cells == {(0,0):0, (1,0):5, (0,1):9, (1,1):0}

def test_diff_update():
    ascii = DummyTileMap()
    # base state
    base = [0.1,0.2,0.3]
    ascii.previous_tiles[Vector2i(0,0)] = base.copy()
    # diffs: index 1->0.8
    diffs = [{'index':1, 'value':0.8}]
    ascii.update_tiles(0,0,diffs,0)
    # only cell (1) changed
    assert ascii.cells[(1,0)] == pytest.approx(int(0.8 * ascii.tile_variants))
