"""keibabook HTMLパーサー群 (v2)"""

from .nittei_parser import parse_nittei_html
from .syutuba_parser import parse_syutuba_html
from .danwa_parser import parse_danwa_html
from .syoin_parser import parse_syoin_html
from .paddok_parser import parse_paddok_html
from .seiseki_parser import parse_seiseki_html
from .babakeikou_parser import parse_babakeikou_html

__all__ = [
    "parse_nittei_html",
    "parse_syutuba_html",
    "parse_danwa_html",
    "parse_syoin_html",
    "parse_paddok_html",
    "parse_seiseki_html",
    "parse_babakeikou_html",
]
