from abc import ABC, abstractmethod
import requests

class BaseExtractor(ABC):
    def __init__(self, source_name: str):
        self.source_name = source_name

    @abstractmethod
    def fetch_data(self):
        """Chaque enfant doit implémenter sa propre méthode de récupération"""
        pass

class APIExtractor(BaseExtractor):
    def fetch_data(self):
        print(f"Appel de l'API réelle via {self.source_name}...")
        
        # URL de CoinGecko pour obtenir les prix du BTC et ETH en USD
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_last_updated_at=true"
        
        try:
            response = requests.get(url)
            response.raise_for_status() # Lève une erreur si l'appel échoue (ex: 404 ou 500)
            data = response.json()
            
            # On reformate le JSON de l'API pour qu'il corresponde à notre modèle "Trade"
            # L'API renvoie : {'bitcoin': {'usd': 65000, ...}, 'ethereum': {...}}
            formatted_data = [
                {
                    "symbol": "BTC",
                    "price": data["bitcoin"]["usd"],
                    "amount": 1.0, # On simule un montant de 1 pour le test
                    "timestamp": data["bitcoin"]["last_updated_at"],
                    "platform": self.source_name
                },
                {
                    "symbol": "ETH",
                    "price": data["ethereum"]["usd"],
                    "amount": 1.0,
                    "timestamp": data["ethereum"]["last_updated_at"],
                    "platform": self.source_name
                }
            ]
            return formatted_data
            
        except Exception as e:
            print(f"❌ Erreur lors de la récupération : {e}")
            return []

class CSVExtractor(BaseExtractor):
    def fetch_data(self):
        # Simulation d'une lecture de fichier CSV
        print(f"Lecture du fichier CSV {self.source_name}...")
        return [
            {"symbol": "sol ", "price": 140.0, "amount": 10, "timestamp": "2026-03-13 11:00:00", "platform": "LocalFile"}
        ]