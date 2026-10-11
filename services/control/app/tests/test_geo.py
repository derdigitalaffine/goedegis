import unittest
from app.geo import geometry, tiles, contains

POLYGON={"type":"Polygon","coordinates":[[[8.4,49.4],[8.6,49.4],[8.6,49.6],[8.4,49.6],[8.4,49.4]]]}

class GeoTests(unittest.TestCase):
    def test_geometry(self):
        _,bounds=geometry(POLYGON)
        self.assertEqual(bounds,[8.4,49.4,8.6,49.6])
    def test_contains(self):
        self.assertTrue(contains(8.5,49.5,POLYGON))
        self.assertFalse(contains(9,49.5,POLYGON))
    def test_tiles(self):
        self.assertGreater(len(list(tiles(POLYGON,0,9))),0)
    def test_invalid(self):
        with self.assertRaises(ValueError):
            geometry({"type":"Polygon","coordinates":[[[0,0],[1,0],[0,1]]]})

if __name__=="__main__": unittest.main()
