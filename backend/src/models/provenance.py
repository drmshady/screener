from datetime import datetime
from pydantic import BaseModel, Field

class SourceProvenance(BaseModel):
    """
    Provenance fields representing data fetched from an external source.
    All timestamps are ISO 8601 UTC.
    """
    source_name: str = Field(
        ..., description="Short and stable name, e.g., 'sec_edgar', 'yfinance', 'spus_holdings'"
    )
    source_as_of: datetime = Field(
        ..., description="When the catalog row or data was last refreshed"
    )

class WithAsOf(SourceProvenance):
    """
    Mixin for entities that carry source provenance fields.
    """
    pass

class Disclaimer(BaseModel):
    """
    Standard disclaimer to be included in every API response per Constitution V.
    """
    disclaimer: str = Field(
        ..., description="Constant text included in every API response for user safety"
    )
