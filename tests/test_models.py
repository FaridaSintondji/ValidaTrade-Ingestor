"""
tests/test_models.py : Tests unitaires pour les modèles Pydantic de ValidaTrade-Ingestor.

Objectif : Vérifier que nos règles de validation métier fonctionnent correctement.
Ces tests tournent automatiquement à chaque push via GitHub Actions.
"""
import pytest
from pydantic import ValidationError
from datetime import datetime

# Import du modèle que l'on veut tester
from models import Trade


# ============================================================
# DONNÉES DE TEST (fixtures pytest)
# ============================================================

@pytest.fixture
def valid_trade_data() -> dict:
    """Fournit un dictionnaire avec des données valides pour créer un Trade."""
    return {
        "symbol": "btc",       # Minuscule intentionnel → doit être converti en "BTC"
        "price": 65000.50,
        "amount": 0.5,
        "timestamp": "2024-01-15T10:30:00",
        "platform": "CoinGecko"
    }


# ============================================================
# TESTS DE VALIDATION POSITIVE (cas qui DOIVENT réussir)
# ============================================================

class TestTradeValidation:
    """Tests qui vérifient qu'un Trade valide est bien créé."""

    def test_create_valid_trade(self, valid_trade_data):
        """Un Trade avec des données correctes doit être instancié sans erreur."""
        trade = Trade(**valid_trade_data)
        assert trade is not None
        assert trade.symbol == "BTC"
        assert trade.price == 65000.50
        assert trade.amount == 0.5
        assert trade.platform == "CoinGecko"

    def test_symbol_is_uppercased(self, valid_trade_data):
        """Le @field_validator doit normaliser le symbole en majuscules."""
        trade = Trade(**valid_trade_data)
        assert trade.symbol == "BTC"  # "btc" doit devenir "BTC"

    def test_symbol_strips_whitespace(self, valid_trade_data):
        """Le @field_validator doit aussi supprimer les espaces autour du symbole."""
        valid_trade_data["symbol"] = "  eth  "
        trade = Trade(**valid_trade_data)
        assert trade.symbol == "ETH"  # "  eth  " doit devenir "ETH"

    def test_timestamp_accepts_string(self, valid_trade_data):
        """Pydantic doit convertir une chaîne ISO 8601 en objet datetime."""
        trade = Trade(**valid_trade_data)
        assert isinstance(trade.timestamp, datetime)

    def test_timestamp_accepts_unix_integer(self, valid_trade_data):
        """Pydantic doit aussi accepter un timestamp Unix (entier)."""
        valid_trade_data["timestamp"] = 1705314600  # Timestamp Unix valide
        trade = Trade(**valid_trade_data)
        assert isinstance(trade.timestamp, datetime)

    def test_total_value_is_none_by_default(self, valid_trade_data):
        """Le champ total_value doit être None si calculate_total() n'est pas appelé."""
        trade = Trade(**valid_trade_data)
        assert trade.total_value is None

    def test_calculate_total(self, valid_trade_data):
        """calculate_total() doit calculer price * amount et arrondir à 2 décimales."""
        trade = Trade(**valid_trade_data)
        trade.calculate_total()
        expected = round(65000.50 * 0.5, 2)  # = 32500.25
        assert trade.total_value == expected


# ============================================================
# TESTS DE VALIDATION NÉGATIVE (cas qui DOIVENT échouer)
# ============================================================

class TestTradeValidationErrors:
    """Tests qui vérifient que les données invalides sont bien rejetées."""

    def test_price_must_be_positive(self, valid_trade_data):
        """Un prix négatif doit lever une ValidationError."""
        valid_trade_data["price"] = -100.0
        with pytest.raises(ValidationError) as exc_info:
            Trade(**valid_trade_data)
        # On vérifie que c'est bien le champ "price" qui pose problème
        assert "price" in str(exc_info.value)

    def test_price_cannot_be_zero(self, valid_trade_data):
        """Un prix à zéro doit lever une ValidationError (gt=0 signifie strictement > 0)."""
        valid_trade_data["price"] = 0
        with pytest.raises(ValidationError) as exc_info:
            Trade(**valid_trade_data)
        assert "price" in str(exc_info.value)

    def test_amount_must_be_positive(self, valid_trade_data):
        """Un montant négatif doit lever une ValidationError."""
        valid_trade_data["amount"] = -0.5
        with pytest.raises(ValidationError) as exc_info:
            Trade(**valid_trade_data)
        assert "amount" in str(exc_info.value)

    def test_amount_cannot_be_zero(self, valid_trade_data):
        """Un montant à zéro doit lever une ValidationError."""
        valid_trade_data["amount"] = 0
        with pytest.raises(ValidationError) as exc_info:
            Trade(**valid_trade_data)
        assert "amount" in str(exc_info.value)

    def test_price_as_text_raises_error(self, valid_trade_data):
        """Un prix sous forme de texte non-numérique doit lever une ValidationError.
        C'est exactement le cas de Data Quality décrit dans ton rapport !
        """
        valid_trade_data["price"] = "pas_un_prix"
        with pytest.raises(ValidationError) as exc_info:
            Trade(**valid_trade_data)
        assert "price" in str(exc_info.value)

    def test_missing_required_field_raises_error(self):
        """Omettre un champ obligatoire comme 'platform' doit lever une ValidationError."""
        with pytest.raises(ValidationError):
            Trade(
                symbol="BTC",
                price=65000.0,
                amount=1.0,
                timestamp="2024-01-15T10:30:00"
                # 'platform' est manquant volontairement
            )
