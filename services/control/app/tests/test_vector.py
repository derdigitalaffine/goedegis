import unittest
from app.vector import vector_id,bbox_text

class VectorTests(unittest.TestCase):
    def test_vector_id_is_area_scoped(self):
        self.assertEqual(vector_id('ABC-123'),'area-abc-123')
        with self.assertRaises(ValueError):vector_id('***')

    def test_bbox_validation(self):
        self.assertEqual(bbox_text([7.0,48.0,9.0,50.0]),'7.0,48.0,9.0,50.0')
        for bad in ([9,48,7,50],[-181,48,9,50],[7,90,9,91],[7,48,9]):
            with self.assertRaises(ValueError):bbox_text(bad)

if __name__=='__main__':unittest.main()
