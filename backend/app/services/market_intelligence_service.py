"""
market_intelligence_service.py — Stock Exchange & Market Monitoring.
"""
from typing import Any, Dict, List
import random
from datetime import datetime

class MarketIntelligenceService:
    def __init__(self):
        # Professional Stock Exchanges
        self.exchanges = [
            {"id": "bist", "name": "Borsa Istanbul", "city": "Istanbul", "country": "Turkey", "index_name": "BIST 100", "coord": [28.97, 41.00], "weight": 0.8},
            {"id": "gse", "name": "Georgian Stock Exchange", "city": "Tbilisi", "country": "Georgia", "index_name": "GSE Index", "coord": [44.82, 41.71], "weight": 0.4},
            {"id": "bfex", "name": "Baku Stock Exchange", "city": "Baku", "country": "Azerbaijan", "index_name": "BFEX Composite", "coord": [49.86, 40.40], "weight": 0.5},
            {"id": "lse", "name": "London Stock Exchange", "city": "London", "country": "UK", "index_name": "FTSE 100", "coord": [-0.12, 51.50], "weight": 1.0},
            {"id": "nyse", "name": "New York Stock Exchange", "city": "New York", "country": "USA", "index_name": "S&P 500", "coord": [-74.00, 40.71], "weight": 1.0},
            {"id": "dfm", "name": "Dubai Financial Market", "city": "Dubai", "country": "UAE", "index_name": "DFM Index", "coord": [55.27, 25.20], "weight": 0.7},
        ]

    async def get_market_pulse(self) -> List[Dict[str, Any]]:
        """
        Return the current 'pulse' of global and regional stock exchanges.
        Includes simulated price movement correlated with global energy news.
        """
        pulse = []
        for ex in self.exchanges:
            # Baseline movement + some randomness
            change = round(random.uniform(-2.5, 2.5), 2)
            
            # Regional context (simulated for now)
            sentiment = "neutral"
            if change > 1.0: sentiment = "bullish"
            elif change < -1.0: sentiment = "bearish"
            
            pulse.append({
                **ex,
                "current_change_pct": change,
                "sentiment": sentiment,
                "volatility": "low" if abs(change) < 0.8 else "moderate" if abs(change) < 1.5 else "high",
                "last_price": 5000 + (random.randint(-500, 500) if ex["id"] != "nyse" else 5200),
                "timestamp": datetime.now().isoformat()
            })
            
        return pulse

market_intelligence = MarketIntelligenceService()
