import os

import geocruncher.main as main

import pytest

def test_geocruncher():
    main.run_geocruncher(['', 'all', 'tests/dummy_project/sections.json', 'tests/dummy_project/geocruncher_project.xml', 'tests/dummy_project/geocruncher_dem.asc'])

