"""
LangChain tools for ReNoUn structural regime classification.

Three tools for AI agents:
  - ReNoUnRegimeTool: Check regime for a single asset before trading
  - ReNoUnBatchRegimeTool: Portfolio-level risk check across multiple assets
  - ReNoUnProvisionKeyTool: Self-provision a free API key (50 calls/day)

Usage:
    from langchain_renoun import ReNoUnRegimeTool

    tool = ReNoUnRegimeTool(api_key="rn_agent_...")
    result = tool.invoke({"symbol": "BTCUSDT"})

Patent Pending #63/923,592
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any, List, Optional, Type

from langchain_core.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun
from pydantic import BaseModel, Field


DEFAULT_API_URL = "https://web-production-817e2.up.railway.app"


# ---------------------------------------------------------------------------
# Shared HTTP helper (stdlib only — no extra deps beyond langchain)
# ---------------------------------------------------------------------------

def _api_call(
    url: str,
    method: str = "GET",
    data: Optional[dict] = None,
    api_key: Optional[str] = None,
    timeout: int = 30,
) -> dict:
    """Make an HTTP request to the ReNoUn API. Returns parsed JSON."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        try:
            detail = json.loads(error_body)
        except (json.JSONDecodeError, ValueError):
            detail = {"raw": error_body}
        raise RuntimeError(
            f"ReNoUn API error {e.code}: {json.dumps(detail, indent=2)}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"ReNoUn API connection error: {e.reason}. "
            f"Check network or API URL ({url})."
        ) from e


# ---------------------------------------------------------------------------
# Tool 1: Single-asset regime check
# ---------------------------------------------------------------------------

class _RegimeInput(BaseModel):
    symbol: str = Field(
        description="Binance USDT trading pair, e.g. BTCUSDT, ETHUSDT, SOLUSDT"
    )
    timeframe: str = Field(
        default="1h",
        description="Candle timeframe: 1m, 5m, 15m, 1h, 4h, 1d"
    )


class ReNoUnRegimeTool(BaseTool):
    """Check the structural market regime for a crypto asset before trading.

    Returns regime (bounded/active/unstable), action (proceed/reduce/avoid),
    DHS health score, stability estimate, and position sizing guidance.

    Use this tool BEFORE executing any crypto trade to check if market
    structure supports the trade.
    """

    name: str = "renoun_regime"
    description: str = (
        "Check the structural market regime for a crypto trading pair. "
        "Returns regime classification (bounded/active/unstable), "
        "recommended action (proceed/reduce/avoid/monitor), "
        "health score (DHS 0-1), stability estimate, and position sizing. "
        "Use BEFORE any crypto trade to assess structural risk. "
        "Example: check BTCUSDT regime before a BTC buy."
    )
    args_schema: Type[BaseModel] = _RegimeInput

    api_key: str = Field(description="ReNoUn API key (rn_agent_... or rn_live_...)")
    api_url: str = Field(default=DEFAULT_API_URL, description="ReNoUn API base URL")

    def _run(
        self,
        symbol: str,
        timeframe: str = "1h",
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        url = f"{self.api_url}/v1/regime/live/{symbol.upper()}?timeframe={timeframe}"
        result = _api_call(url, method="GET", api_key=self.api_key)

        # Return a clean, agent-readable summary
        lines = [
            f"Symbol: {result.get('symbol', symbol.upper())}",
            f"Regime: {result.get('regime', 'unknown')}",
            f"Action: {result.get('action', 'unknown')}",
            f"DHS: {result.get('dhs', 'N/A')}",
            f"Confidence: {result.get('confidence', 'N/A')}",
            f"Constellation: {result.get('constellation', 'N/A')}",
            f"Exposure: {result.get('exposure', 'N/A')}",
            f"Envelope: ±{result.get('envelope_pct', 'N/A')}%",
            f"Detail: {result.get('action_detail', '')}",
            f"Description: {result.get('description', '')}",
        ]

        # Add stability info if present
        stability = result.get("stability")
        if stability:
            lines.append(f"Stability: {stability.get('stability_score', 'N/A')} "
                         f"(halflife: {stability.get('halflife_minutes', 'N/A')}min, "
                         f"risk: {stability.get('instability_risk', 'N/A')}, "
                         f"urgency: {stability.get('urgency', 'N/A')})")

        # Add news alert if present
        news = result.get("news_alert")
        if news:
            lines.append(f"News Alert: {news.get('level', 'none')} — {news.get('detail', '')}")

        # Add transition warning if present
        tw = result.get("transition_warning")
        if tw:
            lines.append(f"Transition Warning: drifting toward {tw.get('drifting_toward', '?')} "
                         f"(drift: {tw.get('drift_score', '?')}, "
                         f"est. {tw.get('estimated_transition_minutes', '?')}min)")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 2: Batch/portfolio regime check
# ---------------------------------------------------------------------------

class _BatchRegimeInput(BaseModel):
    symbols: List[str] = Field(
        description="List of Binance USDT pairs to check, e.g. ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']. Max 10."
    )
    timeframe: str = Field(
        default="1h",
        description="Candle timeframe: 1m, 5m, 15m, 1h, 4h, 1d"
    )


class ReNoUnBatchRegimeTool(BaseTool):
    """Check structural regime for multiple crypto assets at once.

    Returns per-asset regime classification plus a portfolio-level action.
    Use this for portfolio-wide risk assessment before rebalancing or
    entering multiple positions.
    """

    name: str = "renoun_batch_regime"
    description: str = (
        "Check structural market regime for multiple crypto assets at once. "
        "Returns per-asset regime and a portfolio-level action "
        "(proceed/reduce/avoid). Max 10 symbols. "
        "Use for portfolio risk checks before rebalancing. "
        "Example: check ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'] before allocating."
    )
    args_schema: Type[BaseModel] = _BatchRegimeInput

    api_key: str = Field(description="ReNoUn API key (rn_agent_... or rn_live_...)")
    api_url: str = Field(default=DEFAULT_API_URL, description="ReNoUn API base URL")

    def _run(
        self,
        symbols: List[str],
        timeframe: str = "1h",
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        url = f"{self.api_url}/v1/regime/batch"
        payload = {
            "symbols": [s.upper() for s in symbols],
            "timeframe": timeframe,
        }
        result = _api_call(url, method="POST", data=payload, api_key=self.api_key)

        lines = [
            f"Portfolio Action: {result.get('portfolio_action', 'unknown')}",
            f"Portfolio Exposure: {result.get('portfolio_exposure', 'N/A')}",
            f"Unstable Assets: {result.get('unstable_count', 0)}",
            "",
        ]

        regimes = result.get("regimes", {})
        for sym, data in regimes.items():
            lines.append(
                f"  {sym}: {data.get('regime', '?')} | "
                f"{data.get('action', '?')} | "
                f"DHS {data.get('dhs', '?')} | "
                f"{data.get('description', '')}"
            )

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 3: Self-provision API key
# ---------------------------------------------------------------------------

class _ProvisionInput(BaseModel):
    email: str = Field(description="Email address for the API key owner")
    agent_name: str = Field(
        default="langchain-agent",
        description="Name for this agent (used to identify the key)"
    )


class ReNoUnProvisionKeyTool(BaseTool):
    """Provision a free ReNoUn API key for regime classification.

    Returns an API key with 50 free calls/day. Use this if you need
    a key to call the other ReNoUn tools. No payment required for
    the free tier.
    """

    name: str = "renoun_provision_key"
    description: str = (
        "Get a free ReNoUn API key for structural regime classification. "
        "50 free calls/day, no payment required. "
        "Provide an email address to receive the key. "
        "Use this key with renoun_regime and renoun_batch_regime tools."
    )
    args_schema: Type[BaseModel] = _ProvisionInput

    api_url: str = Field(default=DEFAULT_API_URL, description="ReNoUn API base URL")

    def _run(
        self,
        email: str,
        agent_name: str = "langchain-agent",
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        url = f"{self.api_url}/v1/keys/provision"
        payload = {"email": email, "agent_name": agent_name}
        result = _api_call(url, method="POST", data=payload, api_key=None)

        api_key = result.get("api_key", "")
        if api_key.startswith("(previously"):
            return (
                f"Key already provisioned for {email} / {agent_name}.\n"
                f"Key ID: {result.get('key_id', 'unknown')}\n"
                f"If you lost the key, revoke and re-provision.\n"
                f"Free tier: {result.get('free_daily', 50)} calls/day"
            )

        return (
            f"API Key: {api_key}\n"
            f"Tier: {result.get('tier', 'agent')}\n"
            f"Free calls: {result.get('free_daily', 50)}/day\n"
            f"Quick start: Use this key with ReNoUnRegimeTool(api_key=\"{api_key}\")\n"
            f"Docs: {result.get('docs_url', 'https://harrisoncollab.com/agents')}"
        )
