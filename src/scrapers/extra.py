"""Registry for scrapers ported from nse-data. Each entry: name -> (fetch(session, date), Model, Schema)."""
from __future__ import annotations

from datetime import date
from typing import Any, Callable

from ..storage import models_extra as M
from ..utils.symbols import get_fno_symbols, get_watchlist
from ..validators import schemas_extra as S
from . import (
    announcements,
    corp_meetings,
    corp_results,
    delivery,
    equity_quote,
    fo_analysis,
    fo_bhavcopy,
    fo_participants,
    indices,
    insider_trading,
    market_movers,
    market_wide,
    shareholding,
)

Fetch = Callable[[Any, date], list[dict]]


def _movers(session, d: date) -> list[dict]:
    return (market_movers.fetch_gainers_losers(session, d)
            + market_movers.fetch_most_active(session, d)
            + market_movers.fetch_volume_gainers(session, d))


def _vix(session, d: date) -> list[dict]:
    return indices.fetch_all_indices(session, d)[1]


def _deals(session, d: date) -> list[dict]:
    return market_wide.fetch_bulk_deals(session, d) + market_wide.fetch_block_deals(session, d)


EXTRA_SCRAPERS: dict[str, tuple[Fetch, Any, Any]] = {
    "announcements": (lambda s, d: announcements.fetch_announcements(s, d, d), M.Announcements, S.AnnouncementsSchema),
    "board_meetings": (lambda s, d: corp_meetings.fetch_board_meetings(s), M.BoardMeetings, S.BoardMeetingsSchema),
    "financial_results": (lambda s, d: corp_results.fetch_all_financial_results(s), M.FinancialResults, S.FinancialResultsSchema),
    "insider_trading": (lambda s, d: insider_trading.fetch_insider_trading(s), M.InsiderTrading, S.InsiderTradingSchema),
    "shareholding": (lambda s, d: shareholding.fetch_shareholding_bulk(s, get_fno_symbols()), M.Shareholding, S.ShareholdingSchema),
    "delivery": (delivery.fetch_delivery, None, None),  # merged into bhavcopy_eod by orchestrator
    "equity_quote": (lambda s, d: equity_quote.fetch_equity_quotes_bulk(s, get_watchlist(), d), M.EquityQuote, S.EquityQuoteSchema),
    "market_movers": (_movers, M.EquityQuote, S.EquityQuoteSchema),
    "fo_bhavcopy": (fo_bhavcopy.fetch_fo_bhavcopy, M.FoEOD, S.FoEODSchema),
    "fo_participant_volume": (fo_participants.fetch_participant_volume, M.FoParticipantVolume, S.FoParticipantVolumeSchema),
    "index_constituents": (indices.fetch_all_index_constituents, M.IndexConstituents, S.IndexConstituentsSchema),
    "india_vix": (_vix, M.IndiaVIX, S.IndiaVIXSchema),
    "market_turnover": (market_wide.fetch_market_turnover, M.MarketTurnover, S.MarketTurnoverSchema),
    "circuit_breakers": (market_wide.fetch_circuit_breakers, M.CircuitBreakers, S.CircuitBreakersSchema),
    "deals": (_deals, M.Deals, S.DealsSchema),
}
