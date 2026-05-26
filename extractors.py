from abc import ABC, abstractmethod
from datetime import date, datetime, time, timezone
import requests
import csv


class BaseExtractor(ABC):
    def __init__(self, source_name: str):
        self.source_name = source_name

    @abstractmethod
    def fetch_data(self):
        """Chaque enfant doit implémenter sa propre méthode de récupération"""
        pass


class APIExtractor(BaseExtractor):
    # Mapping symbole court (utilisé par notre modèle Trade) -> id CoinGecko
    # Facile à étendre : ajouter "SOL": "solana", "DOT": "polkadot", etc.
    SYMBOL_TO_COINGECKO_ID = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
    }

    def fetch_data(self):
        """
        Récupère les prix actuels (live) des cryptos suivies.
        Utilisé par les runs Airflow quotidiens, en mode "live".
        """
        print(f"Appel de l'API réelle via {self.source_name}...")

        # URL de CoinGecko pour obtenir les prix du BTC et ETH en USD
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_last_updated_at=true"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()  # Lève une erreur si l'appel échoue (ex: 404 ou 500)
            data = response.json()

            # On reformate le JSON de l'API pour qu'il corresponde à notre modèle "Trade"
            # L'API renvoie : {'bitcoin': {'usd': 65000, ...}, 'ethereum': {...}}
            formatted_data = [
                {
                    "symbol": "BTC",
                    "price": data["bitcoin"]["usd"],
                    "amount": 1.0,  # On simule un montant de 1 pour le test
                    "timestamp": data["bitcoin"]["last_updated_at"],
                    "platform": self.source_name,
                },
                {
                    "symbol": "ETH",
                    "price": data["ethereum"]["usd"],
                    "amount": 1.0,
                    "timestamp": data["ethereum"]["last_updated_at"],
                    "platform": self.source_name,
                },
            ]
            return formatted_data

        except Exception as e:
            print(f"❌ Erreur lors de la récupération : {e}")
            return []

    def fetch_historical(self, target_date: date) -> list[dict]:
        """
        Récupère les prix historiques pour une date passée.

        Utilise l'endpoint CoinGecko /coins/{id}/history qui renvoie le prix
        moyen d'un jour donné. Indispensable pour le backfill Airflow
        (rejouer plusieurs jours d'historique d'un coup via catchup=True).

        Args:
            target_date: date à récupérer (datetime.date, pas datetime).

        Returns:
            Liste de dicts compatibles modèle Trade.
            Vide si aucune donnée disponible pour cette date.

        Piège du format : CoinGecko attend la date en 'DD-MM-YYYY' (jour-mois-année),
        PAS au format ISO. D'où le strftime("%d-%m-%Y").
        """
        # Conversion 2026-05-15 -> "15-05-2026"
        coingecko_date = target_date.strftime("%d-%m-%Y")
        print(f"Récupération historique pour {target_date} via {self.source_name}...")

        # CoinGecko aggrège par jour : on assigne le timestamp à midi UTC
        # (milieu de la journée) pour que le partitionnement par day= soit correct.
        ts_midday = datetime.combine(target_date, time(12, 0, tzinfo=timezone.utc))
        ts_unix = int(ts_midday.timestamp())

        formatted_data = []
        for symbol, coingecko_id in self.SYMBOL_TO_COINGECKO_ID.items():
            url = (
                f"https://api.coingecko.com/api/v3/coins/{coingecko_id}/history"
                f"?date={coingecko_date}&localization=false"
            )
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()

                # Pour certaines dates trop anciennes ou trop récentes,
                # market_data peut être absent. On ignore gracieusement.
                market_data = data.get("market_data")
                if not market_data or "current_price" not in market_data:
                    print(f"⚠️  Pas de market_data pour {symbol} le {target_date}")
                    continue

                price_usd = market_data["current_price"].get("usd")
                if price_usd is None:
                    print(f"⚠️  Pas de prix USD pour {symbol} le {target_date}")
                    continue

                formatted_data.append({
                    "symbol": symbol,
                    "price": price_usd,
                    "amount": 1.0,
                    "timestamp": ts_unix,
                    "platform": f"{self.source_name}-Historical",
                })
                print(f"✅ {symbol} @ {target_date} = {price_usd:.2f} USD")

            except Exception as e:
                print(f"❌ Erreur {symbol} pour {target_date} : {e}")

        return formatted_data

class CSVExtractor(BaseExtractor):
    def fetch_data(self):
        file_path = "raw_data/trade.csv"
        
        print(f"Lecture du fichier CSV {self.source_name}...")
        
        formatted_data = []

        try:
            with open(file_path, mode='r', encoding ='utf-8-sig') as file:
                # DictReader utilise la première ligne (header) pour créer des dictionnaires
                reader = csv.DictReader(file)

                for row in reader:
                   # Ici, 'row' est déjà un dictionnaire : {"symbol": "BTC", "price": "63000.5", ...}
                   formatted_data.append(row)

            return formatted_data
    
        except FileNotFoundError:
            print(f"Erreur: Le fichier {file_path} est introuvable")
            return []
        except Exception as e:
            print(f"Erreur: Erreur lors de la lecture du CSV: {e}")
            return []
