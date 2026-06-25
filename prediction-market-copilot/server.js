import http from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL(".", import.meta.url));
const publicDir = join(root, "public");
const port = Number(process.env.PORT || 4173);

const cache = new Map();
const CACHE_MS = 30_000;
const LEADERBOARD_CACHE_MS = 5 * 60_000;

const mimeTypes = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon"
};

async function cachedJson(key, ttlMs, loader) {
  const hit = cache.get(key);
  if (hit && Date.now() - hit.time < ttlMs) return hit.data;
  const data = await loader();
  cache.set(key, { time: Date.now(), data });
  return data;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      accept: "application/json",
      "user-agent": "prediction-market-copilot/0.1",
      ...(options.headers || {})
    }
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`${response.status} ${response.statusText}: ${text.slice(0, 180)}`);
  }

  return response.json();
}

function parseJsonish(value) {
  if (Array.isArray(value)) return value;
  if (typeof value !== "string") return [];
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function numberFrom(value) {
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function normalizePolymarketMarket(market) {
  const outcomes = parseJsonish(market.outcomes);
  const prices = parseJsonish(market.outcomePrices).map(numberFrom);
  const yesIndex = outcomes.findIndex((item) => String(item).toLowerCase() === "yes");
  const noIndex = outcomes.findIndex((item) => String(item).toLowerCase() === "no");
  const yesPrice = yesIndex >= 0 ? prices[yesIndex] : prices[0];
  const noPrice = noIndex >= 0 ? prices[noIndex] : prices[1];
  const inferredYesPrice = yesPrice ?? (noPrice === null || noPrice === undefined ? null : 1 - noPrice);
  const inferredNoPrice = noPrice ?? (yesPrice === null || yesPrice === undefined ? null : 1 - yesPrice);

  return {
    id: String(market.id || market.conditionId || market.slug || market.question),
    platform: "Polymarket",
    question: market.question || market.title || market.slug || "Untitled market",
    slug: market.slug || "",
    url: market.slug ? `https://polymarket.com/event/${market.slug}` : "https://polymarket.com",
    yesPrice: inferredYesPrice,
    noPrice: inferredNoPrice,
    liquidity: numberFrom(market.liquidityNum ?? market.liquidity),
    volume: numberFrom(market.volumeNum ?? market.volume),
    endDate: market.endDate || market.end_date || null,
    raw: market
  };
}

function normalizeKalshiMarket(market) {
  const yesBid = numberFrom(market.yes_bid);
  const yesAsk = numberFrom(market.yes_ask);
  const noBid = numberFrom(market.no_bid);
  const noAsk = numberFrom(market.no_ask);
  const yesBidDollars = numberFrom(market.yes_bid_dollars);
  const yesAskDollars = numberFrom(market.yes_ask_dollars);
  const noBidDollars = numberFrom(market.no_bid_dollars);
  const noAskDollars = numberFrom(market.no_ask_dollars);
  const yesMidCents = yesBid !== null && yesAsk !== null ? (yesBid + yesAsk) / 2 : yesAsk ?? yesBid ?? null;
  const noMidCents = noBid !== null && noAsk !== null ? (noBid + noAsk) / 2 : noAsk ?? noBid ?? null;
  const yesMidDollars =
    yesBidDollars !== null && yesAskDollars !== null
      ? (yesBidDollars + yesAskDollars) / 2
      : yesAskDollars ?? yesBidDollars ?? null;
  const noMidDollars =
    noBidDollars !== null && noAskDollars !== null
      ? (noBidDollars + noAskDollars) / 2
      : noAskDollars ?? noBidDollars ?? null;
  const yesPrice = yesMidDollars ?? (yesMidCents === null ? null : yesMidCents / 100);
  const noPrice = noMidDollars ?? (noMidCents === null ? null : noMidCents / 100);

  return {
    id: market.ticker,
    platform: "Kalshi",
    question: market.title || market.subtitle || market.ticker,
    slug: market.ticker,
    url: market.ticker ? `https://kalshi.com/markets/${market.ticker}` : "https://kalshi.com",
    yesPrice: yesPrice ?? (noPrice === null ? null : 1 - noPrice),
    noPrice: noPrice ?? (yesPrice === null ? null : 1 - yesPrice),
    liquidity: numberFrom(market.liquidity_dollars ?? market.liquidity),
    volume: numberFrom(market.volume_dollars ?? market.volume),
    endDate: market.close_time || market.expiration_time || null,
    raw: market
  };
}

async function getPolymarketMarkets() {
  return cachedJson("polymarket-markets", CACHE_MS, async () => {
    const params = new URLSearchParams({
      active: "true",
      closed: "false",
      limit: "120",
      order: "volume",
      ascending: "false"
    });
    const data = await fetchJson(`https://gamma-api.polymarket.com/markets?${params}`);
    const markets = Array.isArray(data) ? data : data.markets || [];
    return markets.map(normalizePolymarketMarket).filter((market) => market.question);
  });
}

async function getKalshiMarkets() {
  return cachedJson("kalshi-markets", CACHE_MS, async () => {
    const params = new URLSearchParams({
      status: "open",
      limit: "120"
    });
    const data = await fetchJson(`https://api.elections.kalshi.com/trade-api/v2/markets?${params}`);
    const markets = Array.isArray(data.markets) ? data.markets : [];
    return markets.map(normalizeKalshiMarket).filter((market) => market.question);
  });
}

function tokenize(text) {
  const stop = new Set([
    "will",
    "the",
    "and",
    "for",
    "with",
    "from",
    "this",
    "that",
    "market",
    "before",
    "after",
    "between",
    "during",
    "which",
    "what",
    "when",
    "where"
  ]);

  return String(text)
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter((word) => word.length > 2 && !stop.has(word));
}

function similarity(a, b) {
  const left = new Set(tokenize(a));
  const right = new Set(tokenize(b));
  if (!left.size || !right.size) return 0;
  let shared = 0;
  for (const word of left) {
    if (right.has(word)) shared += 1;
  }
  return shared / Math.sqrt(left.size * right.size);
}

function usablePrice(price) {
  return Number.isFinite(price) && price > 0.01 && price < 0.99;
}

function findArbitrage(polymarket, kalshi) {
  const matches = [];
  for (const poly of polymarket) {
    let best = null;
    for (const kal of kalshi) {
      const score = similarity(poly.question, kal.question);
      if (score >= 0.28 && (!best || score > best.score)) {
        best = { kal, score };
      }
    }

    if (!best) continue;
    const canPricePolyYesKalNo = usablePrice(poly.yesPrice) && usablePrice(best.kal.noPrice);
    const canPriceKalYesPolyNo = usablePrice(best.kal.yesPrice) && usablePrice(poly.noPrice);
    const polyYesKalNo = canPricePolyYesKalNo ? 1 - (poly.yesPrice + best.kal.noPrice) : null;
    const kalYesPolyNo = canPriceKalYesPolyNo ? 1 - (best.kal.yesPrice + poly.noPrice) : null;
    const edge = Math.max(polyYesKalNo ?? -Infinity, kalYesPolyNo ?? -Infinity);
    const side =
      edge === polyYesKalNo
        ? "Buy Polymarket YES + Kalshi NO"
        : "Buy Kalshi YES + Polymarket NO";

    matches.push({
      id: `${poly.id}-${best.kal.id}`,
      poly,
      kalshi: best.kal,
      score: best.score,
      edge: Number.isFinite(edge) ? edge : null,
      side: Number.isFinite(edge) ? side : "Review manually",
      warning:
        !Number.isFinite(edge)
          ? "Price is too wide, missing, or near 0/100c. Review only."
          : best.score < 0.45
          ? "Loose text match. Confirm settlement language before trading."
          : "Confirm liquidity, fees, and settlement terms."
    });
  }

  return matches
    .sort((a, b) => (b.edge ?? -Infinity) - (a.edge ?? -Infinity) || b.score - a.score)
    .slice(0, 40);
}

async function getTraderActivity(address) {
  const cleanAddress = String(address || "").trim();
  if (!/^0x[a-fA-F0-9]{40}$/.test(cleanAddress)) {
    return { address: cleanAddress, trades: [], error: "Enter a valid EVM wallet address." };
  }

  return cachedJson(`trader-${cleanAddress.toLowerCase()}`, CACHE_MS, async () => {
    const params = new URLSearchParams({
      user: cleanAddress,
      limit: "50",
      offset: "0"
    });
    const data = await fetchJson(`https://data-api.polymarket.com/activity?${params}`);
    const trades = Array.isArray(data) ? data : data.activity || [];
    return { address: cleanAddress, trades };
  });
}

function cleanPolymarketUndefined(value) {
  return value === "$undefined" ? null : value;
}

function parseEmbeddedLeaderboard(html) {
  const match = html.match(/\\\"data\\\":\[(\{\\\"rank[\s\S]*?)\],\\\"dataUpdateCount/);
  if (!match) return [];

  const jsonText = `[${match[1].replaceAll('\\"', '"').replaceAll("\\u0026", "&")}]`;
  const rows = JSON.parse(jsonText);

  return rows
    .map((row) => {
      const volume = numberFrom(row.volume ?? row.amount) ?? 0;
      const pnl = numberFrom(row.pnl) ?? 0;
      const roi = volume > 0 ? pnl / volume : 0;
      return {
        rank: Number(row.rank),
        address: String(row.proxyWallet || "").toLowerCase(),
        name: row.name || row.pseudonym || "Unnamed trader",
        pnl,
        volume,
        roi,
        profileImage: cleanPolymarketUndefined(row.profileImageOptimized || row.profileImage),
        xUsername: cleanPolymarketUndefined(row.xUsername)
      };
    })
    .filter((row) => /^0x[a-f0-9]{40}$/.test(row.address));
}

function scoreTrader(trader) {
  const pnlScore = Math.min(Math.max(trader.pnl, 0) / 1_000_000, 3);
  const volumeScore = Math.min(Math.log10(Math.max(trader.volume, 1)) / 8, 1.2);
  const roiPct = trader.roi * 100;
  const roiScore = roiPct > 0.15 && roiPct < 8 ? Math.min(roiPct / 2, 2.5) : 0;
  const rankScore = Math.max(0, (60 - trader.rank) / 60);
  const namedScore = /^0x/i.test(trader.name) ? -0.4 : 0.35;
  return pnlScore + volumeScore + roiScore + rankScore + namedScore;
}

async function getSuggestedTraders() {
  return cachedJson("suggested-traders", LEADERBOARD_CACHE_MS, async () => {
    const html = await fetch("https://polymarket.com/leaderboard/overall/monthly/profit", {
      headers: {
        accept: "text/html",
        "user-agent": "prediction-market-copilot/0.1"
      }
    }).then(async (response) => {
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      return response.text();
    });

    const traders = parseEmbeddedLeaderboard(html);
    return traders
      .filter((trader) => trader.pnl > 0 && trader.volume >= 10_000_000 && trader.roi > 0.001)
      .map((trader) => ({
        ...trader,
        score: scoreTrader(trader),
        profileUrl: `https://polymarket.com/profile/${trader.address}`,
        reason:
          trader.roi >= 0.02
            ? "Positive monthly P/L with stronger return on volume."
            : "High-volume positive monthly P/L; watch sizing carefully."
      }))
      .sort((a, b) => b.score - a.score)
      .slice(0, 6);
  });
}

function json(res, status, payload) {
  res.writeHead(status, { "content-type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(payload));
}

async function handleApi(req, res, url) {
  try {
    if (url.pathname === "/api/markets") {
      const [polymarket, kalshi] = await Promise.allSettled([getPolymarketMarkets(), getKalshiMarkets()]);
      return json(res, 200, {
        polymarket: polymarket.status === "fulfilled" ? polymarket.value : [],
        kalshi: kalshi.status === "fulfilled" ? kalshi.value : [],
        errors: {
          polymarket: polymarket.status === "rejected" ? polymarket.reason.message : null,
          kalshi: kalshi.status === "rejected" ? kalshi.reason.message : null
        },
        refreshedAt: new Date().toISOString()
      });
    }

    if (url.pathname === "/api/arbitrage") {
      const [polymarket, kalshi] = await Promise.all([getPolymarketMarkets(), getKalshiMarkets()]);
      return json(res, 200, {
        opportunities: findArbitrage(polymarket, kalshi),
        refreshedAt: new Date().toISOString()
      });
    }

    if (url.pathname === "/api/trader") {
      return json(res, 200, await getTraderActivity(url.searchParams.get("address")));
    }

    if (url.pathname === "/api/poll-trades") {
      const addresses = parseJsonish(url.searchParams.get("addresses"));
      const since = url.searchParams.get("since") || new Date(Date.now() - 60_000).toISOString();
      const results = [];

      for (const addr of addresses.slice(0, 10)) {
        if (!/^0x[a-fA-F0-9]{40}$/.test(String(addr).trim())) continue;
        try {
          const data = await getTraderActivity(addr.trim());
          const newTrades = (data.trades || []).filter((t) => {
            const tradeTime = t.timestamp || t.createdAt || t.created_at || t.time;
            return tradeTime && new Date(tradeTime) > new Date(since);
          });
          if (newTrades.length > 0) {
            results.push({ address: addr.trim(), trades: newTrades });
          }
        } catch {
          // skip failed lookups
        }
      }

      return json(res, 200, { alerts: results, since, polledAt: new Date().toISOString() });
    }

    if (url.pathname === "/api/smart-signals") {
      const addresses = parseJsonish(url.searchParams.get("addresses"));
      if (addresses.length === 0) {
        return json(res, 200, { signals: [], message: "Add traders to your watchlist first." });
      }

      const traderTrades = [];
      for (const addr of addresses.slice(0, 10)) {
        if (!/^0x[a-fA-F0-9]{40}$/.test(String(addr).trim())) continue;
        try {
          const data = await getTraderActivity(addr.trim());
          for (const trade of (data.trades || []).slice(0, 30)) {
            traderTrades.push({ address: addr.trim(), trade });
          }
        } catch {
          // skip
        }
      }

      const marketMap = new Map();
      for (const { address, trade } of traderTrades) {
        const market = trade.title || trade.question || trade.market || "";
        if (!market) continue;
        const side = String(trade.side || trade.type || "").toLowerCase();
        const isBuy = side.includes("buy");
        const outcome = trade.outcome || (isBuy ? "YES" : "NO");
        const key = market.toLowerCase().trim() + "|" + outcome.toUpperCase();

        if (!marketMap.has(key)) {
          marketMap.set(key, {
            market,
            outcome: outcome.toUpperCase(),
            side: isBuy ? "BUY" : "SELL",
            traders: [],
            totalAmount: 0,
            avgPrice: 0,
            priceSum: 0,
            priceCount: 0,
            slug: trade.slug || trade.market_slug || "",
            latestTime: null
          });
        }

        const entry = marketMap.get(key);
        if (!entry.traders.includes(address)) {
          entry.traders.push(address);
        }
        const amount = Number(trade.amount || trade.size || 0);
        entry.totalAmount += amount;
        const price = Number(trade.price || 0);
        if (price > 0) {
          entry.priceSum += price;
          entry.priceCount++;
        }
        const tradeTime = trade.timestamp || trade.createdAt || trade.created_at || trade.time;
        if (tradeTime && (!entry.latestTime || new Date(tradeTime) > new Date(entry.latestTime))) {
          entry.latestTime = tradeTime;
        }
      }

      const signals = [...marketMap.values()]
        .filter((s) => s.traders.length >= 2)
        .map((s) => ({
          market: s.market,
          outcome: s.outcome,
          side: s.side,
          traderCount: s.traders.length,
          traders: s.traders,
          totalAmount: s.totalAmount,
          avgPrice: s.priceCount > 0 ? s.priceSum / s.priceCount : null,
          slug: s.slug,
          url: s.slug ? `https://polymarket.com/event/${s.slug}` : "https://polymarket.com",
          latestTime: s.latestTime,
          strength: s.traders.length >= 3 ? "strong" : "moderate",
          recommendation: s.traders.length >= 3
            ? "Multiple sharp traders are converging on this position. High-conviction signal."
            : "Two traders on the same side. Worth investigating before committing."
        }))
        .sort((a, b) => b.traderCount - a.traderCount || b.totalAmount - a.totalAmount)
        .slice(0, 10);

      return json(res, 200, { signals, refreshedAt: new Date().toISOString() });
    }

    if (url.pathname === "/api/suggested-traders") {
      return json(res, 200, {
        traders: await getSuggestedTraders(),
        source: "Polymarket monthly profit leaderboard",
        refreshedAt: new Date().toISOString()
      });
    }

    return json(res, 404, { error: "Unknown API route." });
  } catch (error) {
    return json(res, 502, { error: error.message });
  }
}

async function handleStatic(req, res, url) {
  const requested = url.pathname === "/" ? "/index.html" : decodeURIComponent(url.pathname);
  const safePath = normalize(requested).replace(/^(\.\.[/\\])+/, "");
  const filePath = join(publicDir, safePath);

  if (!filePath.startsWith(publicDir)) {
    res.writeHead(403);
    return res.end("Forbidden");
  }

  try {
    const file = await readFile(filePath);
    res.writeHead(200, { "content-type": mimeTypes[extname(filePath)] || "application/octet-stream" });
    res.end(file);
  } catch {
    res.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
    res.end("Not found");
  }
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);
  if (url.pathname.startsWith("/api/")) return handleApi(req, res, url);
  return handleStatic(req, res, url);
});

server.listen(port, () => {
  console.log(`Prediction Market Copilot running at http://localhost:${port}`);
});
