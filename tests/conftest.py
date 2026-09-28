"""Test Configuration"""
import os
import sys

import pytest

# Projekt-Root in den Suchpfad, unabhaengig vom Arbeitsverzeichnis.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def setup():
    """Setup fixtures for tests"""
    return True
