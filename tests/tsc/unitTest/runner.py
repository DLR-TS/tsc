import os
import sys
import unittest
import tscdefs
import get_trips

class TestGetTrips(unittest.TestCase):

    def test_get_name(self):
        self.assertEqual(get_trips.tripfile_name(key='blub'), os.path.join('iteration/trips','blub.csv' ))

class TestSomething(unittest.TestCase):

    def test_get_name_limit(self):
        self.assertEqual(get_trips.tripfile_name(key='blub', limit=20), os.path.join('iteration/trips','blub_limit20.csv' ))

unittest.main(sys.modules[__name__])
