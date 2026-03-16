from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional

class Trade(BaseModel):
    symbol: str
    price: float = Field(gt=0)  # gt = Greater Than (doit être > 0)
    amount: float = Field(gt=0)
    timestamp: datetime
    platform: str
    # On ajoute un champ optionnel pour les notes de calcul
    total_value: Optional[float] = None

    @field_validator('symbol')
    @classmethod
    def uppercase_symbol(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator('timestamp', mode='before')
    @classmethod
    def parse_timestamp(cls, v):
        # Si c'est un chiffre (timestamp UNIX), Pydantic gère. 
        # Si c'est un format bizarre, on peut ajouter de la logique ici.
        return v

    def calculate_total(self):
        self.total_value = round(self.price * self.amount, 2)