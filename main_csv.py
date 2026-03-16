from models import Trade
from extractors import CSVExtractor
import requests
import json

def main():
    #On instancie notre extracteur
    source_csv = CSVExtractor("trades_csv")

    print ("-- Démarrage du pipeline d'ingestion via fichier csv")

    #Récupération des données brutes
    raw_data = source_csv.fetch_data()
    # On gère le cas où aucune donnée n'est récupérée
    if not raw_data:
        print("Aucune donnée récupérée. Arrêt du pipeline")
        return
    
    validated_trades = []

    for item in raw_data:
        try:
            #Pydantic valide et nettoie les données
            trade_obj = Trade(**item)

            # On utilise une méthode de notre classe POO
            trade_obj.calculate_total()

            validated_trades.append(trade_obj)
            print(f"Validation réussie pour {trade_obj.symbol}")

        except Exception as e:
            #Si Pydantic trouve unn erreur, on logue sans crash
            print(f"Erreur de validation sur un élément: {e}")

    print(f"\n---Résumé: {len(validated_trades)} trades prêts pour le stockage ---")

    for t in validated_trades:
        print (t.model_dump())

if __name__ == "__main__":
    main()