"""Saudi (Tadawul / TASI) universe seed — Phase 16 feasibility spike (T169).

Provenance: a curated starter list of liquid large-/mid-cap TASI constituents,
hand-assembled 2026-06-11 from well-known Saudi listings (banks, materials,
telecom, consumer, healthcare, utilities, insurance, REITs). It is NOT the full
~230-name market and NOT point-in-time — it exists so the screen has real Saudi
names to run over while testing the expansion. Symbols use the Yahoo `.SR`
suffix (numeric Tadawul codes), prices are in SAR.

Replace later with an authoritative TASI constituent list (SAHMK / Saudi Exchange
/ Kaggle dataset) once a real data source is chosen.
"""
from __future__ import annotations

# Numeric Tadawul codes + .SR (Yahoo). Grouped by sector for readability only.
SAUDI_TICKERS: list[str] = [
    # Energy / Materials
    "2222.SR",  # Saudi Aramco
    "2010.SR",  # SABIC
    "1211.SR",  # Ma'aden
    "2350.SR",  # Saudi Kayan
    "2290.SR",  # Yansab
    "2310.SR",  # Sipchem (Sahara Int'l Petrochemical)
    "2060.SR",  # Tasnee
    "2380.SR",  # Petro Rabigh
    "3030.SR",  # Saudi Cement
    "3020.SR",  # Yamama Cement
    # Banks / Financials
    "1120.SR",  # Al Rajhi Bank
    "1180.SR",  # Saudi National Bank
    "1010.SR",  # Riyad Bank
    "1060.SR",  # SAB (Saudi Awwal Bank)
    "1050.SR",  # Banque Saudi Fransi
    "1080.SR",  # Arab National Bank
    "1150.SR",  # Alinma Bank
    "1140.SR",  # Bank Albilad
    "1020.SR",  # Bank Aljazira
    "1111.SR",  # Saudi Tadawul Group
    # Telecom / Tech
    "7010.SR",  # STC
    "7020.SR",  # Mobily (Etihad Etisalat)
    "7030.SR",  # Zain KSA
    # Consumer / Retail / Food
    "2280.SR",  # Almarai
    "2050.SR",  # Savola Group
    "2270.SR",  # SADAFCO
    "4190.SR",  # Jarir Marketing
    "4001.SR",  # Abdullah Al Othaim Markets
    "4003.SR",  # United Electronics (eXtra)
    "6010.SR",  # NADEC
    "6001.SR",  # Halwani Bros
    # Healthcare
    "4013.SR",  # Dr. Sulaiman Al Habib
    "4002.SR",  # Mouwasat Medical
    "4004.SR",  # Dallah Healthcare
    "2070.SR",  # SPIMACO
    # Utilities / Transport / Industrials
    "5110.SR",  # Saudi Electricity
    "4030.SR",  # Bahri (National Shipping)
    "4200.SR",  # Aldrees Petroleum
    "6004.SR",  # Saudi Airlines Catering
    # Insurance
    "8010.SR",  # Tawuniya
    "8210.SR",  # Bupa Arabia
    # Real estate
    "4020.SR",  # Dar Al Arkan
    "4250.SR",  # Jabal Omar
]


def saudi_universe() -> list[str]:
    """Deduped, sorted Saudi (.SR) starter universe."""
    return sorted({t.strip().upper() for t in SAUDI_TICKERS if t.strip()})
