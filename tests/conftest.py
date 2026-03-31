"""
conftest.py : Configuration de pytest pour ValidaTrade-Ingestor.
Ajoute la racine du projet au PYTHONPATH pour que les imports fonctionnent.
"""
import sys
import os

# On ajoute le dossier parent (racine du projet) au chemin de recherche Python
# Cela permet de faire "from models import Trade" dans les tests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
