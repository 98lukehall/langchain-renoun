# langchain-renoun

LangChain tools for [ReNoUn](https://harrisoncollab.com) structural market regime classification.

**Know when NOT to trade.** ReNoUn analyzes market microstructure across 17 channels to classify the current regime as `bounded`, `active`, or `unstable` — then tells your agent whether to `proceed`, `reduce`, `avoid`, or `monitor`.

Earlier accuracy claims for ReNoUn have been withdrawn; they were never compared against a base rate.

## Installation

```bash
pip install langchain-renoun
```

## Quick Start

```python
from langchain_renoun import ReNoUnRegimeTool

# Get a free API key (50 calls/day, no payment required)
from langchain_renoun import ReNoUnProvisionKeyTool
provisioner = ReNoUnProvisionKeyTool()
print(provisioner.invoke({"email": "you@example.com"}))

# Check BTC regime before trading
tool = ReNoUnRegimeTool(api_key="rn_agent_your_key_here")
result = tool.invoke({"symbol": "BTCUSDT"})
print(result)
```

Output:
```
Symbol: BTCUSDT
Regime: bounded
Action: proceed
DHS: 0.72
Confidence: 0.85
Constellation: CLOSED_LOOP
Exposure: 0.80
Envelope: ±2.0%
Detail: Structure healthy. Position size: 80% of intended.
Description: Range-bound, <2% move expected
Stability: 0.78 (halflife: 240min, risk: low, urgency: normal)
```

## Tools

### `ReNoUnRegimeTool`

Pre-trade risk check for a single asset. Call this before any crypto trade.

```python
from langchain_renoun import ReNoUnRegimeTool

tool = ReNoUnRegimeTool(api_key="rn_agent_...")
result = tool.invoke({"symbol": "ETHUSDT", "timeframe": "4h"})
```

**Returns:** regime, action, DHS health score, stability estimate, position sizing, news alerts, transition warnings.

### `ReNoUnBatchRegimeTool`

Portfolio-level risk check across multiple assets.

```python
from langchain_renoun import ReNoUnBatchRegimeTool

tool = ReNoUnBatchRegimeTool(api_key="rn_agent_...")
result = tool.invoke({
    "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    "timeframe": "1h"
})
```

**Returns:** per-asset regime + portfolio-level action. If 2+ assets are unstable, portfolio action is `avoid`.

### `ReNoUnProvisionKeyTool`

Self-provision a free API key. No payment required.

```python
from langchain_renoun import ReNoUnProvisionKeyTool

tool = ReNoUnProvisionKeyTool()
result = tool.invoke({"email": "agent@example.com", "agent_name": "my-trading-bot"})
```

**Returns:** API key with 50 free calls/day.

## Use with LangChain Agents

```python
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_renoun import ReNoUnRegimeTool, ReNoUnBatchRegimeTool

# Set up tools
tools = [
    ReNoUnRegimeTool(api_key="rn_agent_..."),
    ReNoUnBatchRegimeTool(api_key="rn_agent_..."),
]

# Create agent
llm = ChatOpenAI(model="gpt-4o")
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a crypto trading assistant. Always check the market regime before recommending trades."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools)

result = executor.invoke({"input": "Should I buy ETH right now?"})
```

## Regime Reference

| Regime | Meaning | Typical Action |
|--------|---------|---------------|
| `bounded` | Range-bound, low volatility expected | `proceed` at full size |
| `active` | Trending or recovering, moderate moves | `proceed` or `reduce` size |
| `unstable` | Structure fragmenting, high risk | `avoid` — skip the trade |

## API Details

- **Base URL:** `https://web-production-817e2.up.railway.app`
- **Auth:** Bearer token (`Authorization: Bearer rn_agent_...`)
- **Free tier:** 50 calls/day, no payment required
- **Rate limit:** 1000 calls/hour
- **Cache:** 60-second regime cache per symbol/timeframe
- **No external dependencies** beyond `langchain-core` (uses stdlib `urllib`)

## Links

- [Documentation](https://harrisoncollab.com/agents)
- [API Status](https://web-production-817e2.up.railway.app/v1/status)
- [Patent Pending #63/923,592](https://harrisoncollab.com)
