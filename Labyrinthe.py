import json
from pathlib import Path
from typing import Any, Dict, List, Union

JSONType = Union[Dict[str, Any], List[Any]]

def lire_json(chemin: str) -> JSONType:
    """
    Ouvre un fichier JSON et retourne son contenu.
    Lève FileNotFoundError et json.JSONDecodeError si problème.
    """
    p = Path(chemin)
    if not p.exists():
        raise FileNotFoundError(f"Fichier introuvable : {chemin}")
    if p.suffix.lower() != ".json":
        raise ValueError("Le fichier doit être en .json")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def charger_labyrinthe(chemin_json: str) -> Dict[str, Any]:
    data = lire_json(chemin_json)
    if not isinstance(data, dict):
        raise ValueError("Le labyrinthe JSON doit être un objet racine (dictionnaire).")
    return data


if __name__ == "__main__":
    chemin = input("Chemin vers le fichier labyrinthe JSON : ").strip()
    try:
        labyrinthe = charger_labyrinthe(chemin)
        print("Labyrinthe chargé avec succès.")
        print(labyrinthe)
    except FileNotFoundError as e:
        print("Erreur : fichier non trouvé.", e)
    except json.JSONDecodeError as e:
        print("Erreur : JSON invalide.", e)
    except ValueError as e:
        print("Erreur de format :", e)
