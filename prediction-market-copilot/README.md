# Prediction Market Copilot

Local read-only dashboard for:

- Watching Polymarket trader wallets
- Simulating copy-trade rules
- Scanning Polymarket and Kalshi markets for possible arbitrage
- Reviewing risk before any real execution is added

## Run

Use the bundled Codex Node runtime or any local Node 18+:

```powershell
node server.js
```

Then open:

```text
http://localhost:4173
```

## What I Need From You Later

The app works without secrets for the first read-only version. To enable account-specific tracking or real execution later, I will need:

- Polymarket wallet address or addresses you want to follow
- Polymarket wallet/API setup only if you want execution
- Kalshi demo or live API key only if you want account/order execution
- Your copy rules: max trade size, categories to include, stop-loss, and whether trades require approval

## Safety Defaults

- No real trades are placed.
- API keys are not required.
- Trader watchlists are stored in your browser.
- Arbitrage results are signals only; they still need liquidity, fee, settlement, and terms checks before trading.
