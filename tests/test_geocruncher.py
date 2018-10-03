import os

import geocruncher.main as main

import pytest


def test_geocruncher():
    main.main(['', 'all', 'dummy_project/boundaries.json', 'dummy_project/geocruncher_project.xml', 'dummy_project/geocruncher_dem.asc'])

