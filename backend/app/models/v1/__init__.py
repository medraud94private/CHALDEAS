# CHALDEAS V1 Models
# Historical Chain 기반 신규 데이터 모델
#
# Theoretical Basis:
# - CIDOC-CRM: Event-centric ontology
# - Braudel/Annales: Temporal scales (evenementielle, conjuncture, longue_duree)
# - Prosopography: Person network analysis
# - Historical GIS: Dual hierarchies, temporal validity

from .period import Period
from .polity import Polity
from .chain import HistoricalChain, ChainSegment, ChainEntityRole
from .text_mention import TextMention, EntityAlias, ImportBatch, PendingEntity

__all__ = [
    # Existing
    "Period",
    # New: Political entities
    "Polity",
    # New: Historical Chain
    "HistoricalChain",
    "ChainSegment",
    "ChainEntityRole",
    # New: Source tracking
    "TextMention",
    "EntityAlias",
    "ImportBatch",
    "PendingEntity",
]
