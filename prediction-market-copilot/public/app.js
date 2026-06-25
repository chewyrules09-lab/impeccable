const STORAGE_KEY = "pmc-watchlist";
const RULES_KEY = "pmc-rules";
const SEEN_KEY = "pmc-seen-trades";
const BANKROLL_KEY = "pmc-bankroll";
const ALERT_POLL_MS = 15_000;

let marketsData = { polymarket: [], kalshi: [] };
let arbData = [];
let signalsData = [];
let currentMarketFilter = "all";
let selectedTrader = null;
let alertsEnabled = false;
let alertInterval = null;
let lastPollTime = new Date(Date.now() - 5 * 60_000).toISOString();
let alertsFeed = [];

function loadWatchlist() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
  } catch {
    return [];
  }
}

function saveWatchlist(list) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
}

function loadSeenTrades() {
  try {
    return new Set(JSON.parse(localStorage.getItem(SEEN_KEY)) || []);
  } catch {
    return new Set();
  }
}

function saveSeenTrades(seen) {
  const arr = [...seen].slice(-500);
  localStorage.setItem(SEEN_KEY, JSON.stringify(arr));
}

function loadRules() {
  try {
    return JSON.parse(localStorage.getItem(RULES_KEY)) || {};
  } catch {
    return {};
  }
}

function saveRules() {
  const rules = {
    maxSize: document.getElementById("rule-max-size").value,
    categories: document.getElementById("rule-categories").value,
    approval: document.getElementById("rule-approval").value,
    stopLoss: document.getElementById("rule-stoploss").value
  };
  localStorage.setItem(RULES_KEY, JSON.stringify(rules));
}

function restoreRules() {
  const rules = loadRules();
  if (rules.maxSize) document.getElementById("rule-max-size").value = rules.maxSize;
  if (rules.categories) document.getElementById("rule-categories").value = rules.categories;
  if (rules.approval) document.getElementById("rule-approval").value = rules.approval;
  if (rules.stopLoss) document.getElementById("rule-stoploss").value = rules.stopLoss;
}

function formatPrice(p) {
  if (p === null || p === undefined || !Number.isFinite(p)) return "-";
  return (p * 100).toFixed(1) + "¢";
}

function formatDollars(n) {
  if (n === null || n === undefined || !Number.isFinite(n)) return "-";
  if (n >= 1_000_000) return "$" + (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return "$" + (n / 1_000).toFixed(1) + "K";
  return "$" + n.toFixed(0);
}

function formatPct(n) {
  if (n === null || n === undefined || !Number.isFinite(n)) return "-";
  return (n * 100).toFixed(2) + "%";
}

function formatTime(ts) {
  if (!ts) return "";
  const d = new Date(ts);
  if (isNaN(d.getTime())) return "";
  const now = new Date();
  const diffMs = now - d;
  if (diffMs < 60_000) return "just now";
  if (diffMs < 3600_000) return Math.floor(diffMs / 60_000) + "m ago";
  if (diffMs < 86400_000) return Math.floor(diffMs / 3600_000) + "h ago";
  return d.toLocaleDateString();
}

function shortAddr(addr) {
  if (!addr || addr.length < 12) return addr || "";
  return addr.slice(0, 6) + "..." + addr.slice(-4);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function playAlertSound() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value = 880;
    osc.type = "sine";
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.3);
    setTimeout(() => {
      const osc2 = ctx.createOscillator();
      const gain2 = ctx.createGain();
      osc2.connect(gain2);
      gain2.connect(ctx.destination);
      osc2.frequency.value = 1100;
      osc2.type = "sine";
      gain2.gain.setValueAtTime(0.3, ctx.currentTime);
      gain2.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4);
      osc2.start(ctx.currentTime);
      osc2.stop(ctx.currentTime + 0.4);
    }, 150);
  } catch {
    // no audio support
  }
}

function sendDesktopNotification(title, body, url) {
  if (Notification.permission !== "granted") return;
  const n = new Notification(title, {
    body,
    icon: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📊</text></svg>",
    tag: "pmc-" + Date.now()
  });
  if (url) {
    n.onclick = () => {
      window.focus();
      window.open(url, "_blank");
    };
  }
}

function loadBankroll() {
  return Number(localStorage.getItem(BANKROLL_KEY)) || 70;
}

function saveBankroll(val) {
  localStorage.setItem(BANKROLL_KEY, String(val));
}

function promptBankroll() {
  const current = loadBankroll();
  const input = prompt("Enter your current bankroll in dollars:", current);
  if (input === null) return;
  const val = parseFloat(input.replace(/[$,]/g, ""));
  if (!Number.isFinite(val) || val < 0) return;
  saveBankroll(val);
  document.getElementById("stat-bankroll").textContent = formatDollars(val);
}

function suggestSize(bankroll, strength, avgPrice) {
  if (strength === "strong") {
    const pct = 0.30;
    const raw = bankroll * pct;
    return Math.min(Math.max(Math.floor(raw), 5), bankroll);
  }
  const pct = 0.15;
  const raw = bankroll * pct;
  return Math.min(Math.max(Math.floor(raw), 5), bankroll);
}

function potentialPayout(size, avgPrice) {
  if (!avgPrice || avgPrice <= 0 || avgPrice >= 1) return null;
  const contracts = size / avgPrice;
  return contracts;
}

function switchTab(tab) {
  document.querySelectorAll(".tab-bar button").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
  ["signals", "alerts", "arbitrage", "markets", "activity"].forEach((t) => {
    const el = document.getElementById("tab-" + t);
    if (el) el.style.display = t === tab ? "" : "none";
  });
}

function toggleAlerts() {
  alertsEnabled = !alertsEnabled;
  const btn = document.getElementById("alert-toggle");

  if (alertsEnabled) {
    btn.textContent = "Alerts: ON";
    btn.style.background = "var(--accent)";
    btn.style.color = "white";

    if (Notification.permission === "default") {
      Notification.requestPermission();
    }

    lastPollTime = new Date(Date.now() - 60_000).toISOString();
    pollForNewTrades();
    alertInterval = setInterval(pollForNewTrades, ALERT_POLL_MS);
  } else {
    btn.textContent = "Alerts: OFF";
    btn.style.background = "#eef2ef";
    btn.style.color = "var(--ink)";

    if (alertInterval) {
      clearInterval(alertInterval);
      alertInterval = null;
    }
  }
}

async function pollForNewTrades() {
  const watchlist = loadWatchlist();
  if (watchlist.length === 0) return;

  try {
    const params = new URLSearchParams({
      addresses: JSON.stringify(watchlist),
      since: lastPollTime
    });
    const res = await fetch("/api/poll-trades?" + params);
    const data = await res.json();

    lastPollTime = data.polledAt || new Date().toISOString();

    if (!data.alerts || data.alerts.length === 0) return;

    const seen = loadSeenTrades();
    let newCount = 0;

    for (const group of data.alerts) {
      for (const trade of group.trades) {
        const tradeId = group.address + "-" + (trade.id || trade.timestamp || trade.createdAt || JSON.stringify(trade).slice(0, 80));
        if (seen.has(tradeId)) continue;
        seen.add(tradeId);
        newCount++;

        const side = String(trade.side || trade.type || "").toLowerCase();
        const isBuy = side.includes("buy");
        const market = trade.title || trade.question || trade.market || "Unknown market";
        const amount = Number(trade.amount || trade.size || 0);
        const price = Number(trade.price || 0);
        const outcome = trade.outcome || (isBuy ? "YES" : "");
        const slug = trade.slug || trade.market_slug || "";
        const polyUrl = slug ? "https://polymarket.com/event/" + slug : "https://polymarket.com";
        const timestamp = trade.timestamp || trade.createdAt || trade.created_at || trade.time || new Date().toISOString();

        const alert = {
          traderAddr: group.address,
          side: isBuy ? "BUY" : "SELL",
          market,
          amount,
          price,
          outcome,
          polyUrl,
          timestamp,
          isBuy
        };

        alertsFeed.unshift(alert);

        sendDesktopNotification(
          (isBuy ? "BUY" : "SELL") + " Alert: " + shortAddr(group.address),
          market + " | " + formatDollars(amount),
          polyUrl
        );
      }
    }

    if (newCount > 0) {
      playAlertSound();
      saveSeenTrades(seen);
      renderAlertsFeed();

      const alertTab = document.querySelector('[data-tab="alerts"]');
      if (alertTab && !alertTab.classList.contains("active")) {
        alertTab.style.background = "var(--accent)";
        alertTab.style.color = "white";
        setTimeout(() => {
          alertTab.style.background = "";
          alertTab.style.color = "";
        }, 3000);
      }
    }
  } catch (err) {
    console.error("Poll error:", err);
  }
}

function renderAlertsFeed() {
  const container = document.getElementById("alerts-feed");

  if (alertsFeed.length === 0) {
    container.innerHTML = '<div class="empty">Waiting for new trades from watched traders. Make sure alerts are enabled (top right). Polling every 15 seconds.</div>';
    return;
  }

  container.innerHTML = alertsFeed
    .slice(0, 50)
    .map((a) => `
      <div class="alert-card ${a.isBuy ? "alert-buy" : "alert-sell"}">
        <div class="alert-header">
          <div>
            <span class="alert-side ${a.isBuy ? "side-buy" : "side-sell"}">${a.side}</span>
            <strong>${escapeHtml(a.market)}</strong>
          </div>
          <small>${formatTime(a.timestamp)}</small>
        </div>
        <div class="alert-details">
          <span>Trader: <code>${shortAddr(a.traderAddr)}</code></span>
          ${a.outcome ? `<span>Outcome: <strong>${escapeHtml(a.outcome)}</strong></span>` : ""}
          ${a.price ? `<span>Price: <strong>${formatPrice(a.price)}</strong></span>` : ""}
          ${a.amount ? `<span>Size: <strong>${formatDollars(a.amount)}</strong></span>` : ""}
        </div>
        <div class="alert-actions">
          <a href="${escapeHtml(a.polyUrl)}" target="_blank" rel="noopener" class="alert-trade-btn">
            Open on Polymarket to copy this trade
          </a>
        </div>
      </div>
    `)
    .join("");
}

function clearAlerts() {
  alertsFeed = [];
  renderAlertsFeed();
}

function addTrader() {
  const input = document.getElementById("wallet-input");
  const address = input.value.trim();
  if (!/^0x[a-fA-F0-9]{40}$/.test(address)) {
    input.style.borderColor = "var(--bad)";
    setTimeout(() => (input.style.borderColor = ""), 1500);
    return;
  }

  const list = loadWatchlist();
  if (list.some((t) => t.toLowerCase() === address.toLowerCase())) return;
  list.push(address);
  saveWatchlist(list);
  input.value = "";
  renderWatchlist();
  updateStats();
}

function addTraderFromSuggested(address) {
  const list = loadWatchlist();
  if (list.some((t) => t.toLowerCase() === address.toLowerCase())) return;
  list.push(address);
  saveWatchlist(list);
  renderWatchlist();
  renderSuggestedTraders();
  updateStats();
}

function removeTrader(address) {
  const list = loadWatchlist().filter((t) => t.toLowerCase() !== address.toLowerCase());
  saveWatchlist(list);
  if (selectedTrader && selectedTrader.toLowerCase() === address.toLowerCase()) {
    selectedTrader = null;
    document.getElementById("activity-content").innerHTML =
      '<div class="empty">Add a wallet to your watchlist, then click on it to see recent activity.</div>';
  }
  renderWatchlist();
  updateStats();
}

function renderWatchlist() {
  const list = loadWatchlist();
  const container = document.getElementById("watchlist");

  if (list.length === 0) {
    container.innerHTML = '<div class="empty">No traders watched yet. Paste a wallet address above or pick from suggested traders.</div>';
    return;
  }

  container.innerHTML = list
    .map(
      (addr) => `
    <div class="trader">
      <div class="trader-head">
        <code>${escapeHtml(addr)}</code>
        <div style="display:flex;gap:0.35rem">
          <button onclick="viewTrader('${escapeHtml(addr)}')" title="View activity">&#x1f50d;</button>
          <button onclick="removeTrader('${escapeHtml(addr)}')" title="Remove">&times;</button>
        </div>
      </div>
    </div>
  `
    )
    .join("");
}

async function viewTrader(address) {
  selectedTrader = address;
  switchTab("activity");

  const container = document.getElementById("activity-content");
  container.innerHTML = '<div class="loading"><div class="spinner"></div> Loading trades...</div>';

  try {
    const res = await fetch("/api/trader?address=" + encodeURIComponent(address));
    const data = await res.json();

    if (data.error) {
      container.innerHTML = `<div class="error-msg">${escapeHtml(data.error)}</div>`;
      return;
    }

    if (!data.trades || data.trades.length === 0) {
      container.innerHTML = `<div class="empty">No recent trades found for ${escapeHtml(shortAddr(address))}.</div>`;
      return;
    }

    container.innerHTML = `
      <p style="font-size:0.85rem;color:var(--muted);margin-bottom:0.5rem">
        Recent trades for <strong>${escapeHtml(shortAddr(address))}</strong>
      </p>
      ${data.trades
        .map((trade) => {
          const side = String(trade.side || trade.type || "").toLowerCase();
          const isBuy = side.includes("buy");
          const slug = trade.slug || trade.market_slug || "";
          const polyUrl = slug ? "https://polymarket.com/event/" + slug : "";
          return `
          <div class="trade-row">
            <span>
              ${polyUrl ? `<a href="${escapeHtml(polyUrl)}" target="_blank" rel="noopener">` : ""}
              ${escapeHtml(trade.title || trade.question || trade.market || "Unknown market")}
              ${polyUrl ? "</a>" : ""}
            </span>
            <span class="${isBuy ? "side-buy" : "side-sell"}">${isBuy ? "BUY" : "SELL"}</span>
            <span>${formatDollars(Number(trade.amount || trade.size || 0))}</span>
          </div>`;
        })
        .join("")}
    `;
  } catch (err) {
    container.innerHTML = `<div class="error-msg">Failed to load trader data: ${escapeHtml(err.message)}</div>`;
  }
}

function renderArbitrage(opportunities) {
  const container = document.getElementById("arb-list");

  if (!opportunities || opportunities.length === 0) {
    container.innerHTML = '<div class="empty">No arbitrage opportunities found right now. Markets are checked every 30 seconds.</div>';
    return;
  }

  container.innerHTML = opportunities
    .map((opp) => {
      const edgePct = opp.edge !== null ? (opp.edge * 100).toFixed(1) : null;
      const isNeg = opp.edge !== null && opp.edge < 0;
      return `
      <div class="opportunity">
        <div class="opp-score">${(opp.score * 100).toFixed(0)}%</div>
        <div>
          <div class="opp-head">
            <h2>${escapeHtml(opp.poly.question)}</h2>
            <div>
              ${edgePct !== null ? `<span class="opp-edge ${isNeg ? "negative" : ""}">${isNeg ? "" : "+"}${edgePct}%</span>` : ""}
              <div class="opp-side">${escapeHtml(opp.side)}</div>
            </div>
          </div>
          <div class="markets">
            <a href="${escapeHtml(opp.poly.url)}" target="_blank" rel="noopener">
              <strong>Polymarket</strong><br>
              YES ${formatPrice(opp.poly.yesPrice)} / NO ${formatPrice(opp.poly.noPrice)}
            </a>
            <a href="${escapeHtml(opp.kalshi.url)}" target="_blank" rel="noopener">
              <strong>Kalshi</strong><br>
              YES ${formatPrice(opp.kalshi.yesPrice)} / NO ${formatPrice(opp.kalshi.noPrice)}
            </a>
          </div>
          <p class="warning">${escapeHtml(opp.warning)}</p>
        </div>
      </div>`;
    })
    .join("");
}

function renderMarkets() {
  const container = document.getElementById("market-list");
  let markets = [];

  if (currentMarketFilter === "all" || currentMarketFilter === "poly") {
    markets = markets.concat(marketsData.polymarket);
  }
  if (currentMarketFilter === "all" || currentMarketFilter === "kalshi") {
    markets = markets.concat(marketsData.kalshi);
  }

  markets.sort((a, b) => (b.volume || 0) - (a.volume || 0));
  markets = markets.slice(0, 50);

  if (markets.length === 0) {
    container.innerHTML = '<div class="empty">No markets loaded yet.</div>';
    return;
  }

  container.innerHTML = markets
    .map(
      (m) => `
    <div class="opportunity" style="grid-template-columns:1fr">
      <div>
        <div class="opp-head">
          <h2><a href="${escapeHtml(m.url)}" target="_blank" rel="noopener">${escapeHtml(m.question)}</a></h2>
          <span class="pill">${escapeHtml(m.platform)}</span>
        </div>
        <div class="metrics" style="margin-top:0.5rem">
          <span>YES<strong>${formatPrice(m.yesPrice)}</strong></span>
          <span>NO<strong>${formatPrice(m.noPrice)}</strong></span>
          <span>Volume<strong>${formatDollars(m.volume)}</strong></span>
        </div>
      </div>
    </div>
  `
    )
    .join("");
}

function filterMarkets(filter) {
  currentMarketFilter = filter;
  document.querySelectorAll("[data-platform]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.platform === filter);
  });
  renderMarkets();
}

async function renderSuggestedTraders() {
  const container = document.getElementById("suggested-traders");
  try {
    const res = await fetch("/api/suggested-traders");
    const data = await res.json();

    if (!data.traders || data.traders.length === 0) {
      container.innerHTML = '<div class="empty">Could not load leaderboard data. Try refreshing.</div>';
      return;
    }

    const watchlist = loadWatchlist().map((a) => a.toLowerCase());

    container.innerHTML = data.traders
      .map((t) => {
        const isWatched = watchlist.includes(t.address);
        const avatarContent = t.profileImage
          ? `<img src="${escapeHtml(t.profileImage)}" alt="">`
          : `#${t.rank}`;
        return `
        <div class="suggested-trader">
          <div class="suggested-head">
            <div class="avatar">${avatarContent}</div>
            <div>
              <h3>${escapeHtml(t.name)}</h3>
              ${t.xUsername ? `<small>@${escapeHtml(t.xUsername)}</small>` : ""}
            </div>
          </div>
          <div class="metrics">
            <span>P/L<strong style="color:${t.pnl >= 0 ? "var(--good)" : "var(--bad)"}">${formatDollars(t.pnl)}</strong></span>
            <span>Volume<strong>${formatDollars(t.volume)}</strong></span>
            <span>ROI<strong>${formatPct(t.roi)}</strong></span>
          </div>
          <p style="font-size:0.8rem;color:var(--muted);margin:0">${escapeHtml(t.reason)}</p>
          <div class="suggested-actions">
            <button onclick="addTraderFromSuggested('${escapeHtml(t.address)}')" ${isWatched ? "disabled style=\"opacity:0.5\"" : ""}>
              ${isWatched ? "Watching" : "Watch"}
            </button>
            <a href="${escapeHtml(t.profileUrl)}" target="_blank" rel="noopener">Profile</a>
          </div>
        </div>`;
      })
      .join("");
  } catch (err) {
    container.innerHTML = `<div class="error-msg">Failed to load suggested traders: ${escapeHtml(err.message)}</div>`;
  }
}

async function loadSmartSignals() {
  const watchlist = loadWatchlist();
  const container = document.getElementById("signals-list");

  if (watchlist.length < 2) {
    container.innerHTML = '<div class="empty">Watch at least 2 traders to see convergence signals. The more traders you follow, the stronger the signals.</div>';
    document.getElementById("stat-signals").textContent = "-";
    return;
  }

  container.innerHTML = '<div class="loading"><div class="spinner"></div> Scanning for convergence signals...</div>';

  try {
    const params = new URLSearchParams({ addresses: JSON.stringify(watchlist) });
    const res = await fetch("/api/smart-signals?" + params);
    const data = await res.json();
    signalsData = data.signals || [];
    renderSmartSignals();
  } catch (err) {
    container.innerHTML = `<div class="error-msg">Failed to load signals: ${escapeHtml(err.message)}</div>`;
  }
}

function renderSmartSignals() {
  const container = document.getElementById("signals-list");
  const bankroll = loadBankroll();

  document.getElementById("stat-signals").textContent = signalsData.length || "0";

  if (signalsData.length === 0) {
    container.innerHTML = '<div class="empty">No convergence signals right now. This means your watched traders are not clustering on the same markets. Check back after they make new trades.</div>';
    return;
  }

  container.innerHTML = signalsData
    .map((s) => {
      const size = suggestSize(bankroll, s.strength, s.avgPrice);
      const payout = potentialPayout(size, s.avgPrice);
      const isStrong = s.strength === "strong";

      return `
      <div class="signal-card ${isStrong ? "signal-strong" : "signal-moderate"}">
        <div class="signal-strength">
          <span class="signal-badge ${isStrong ? "badge-strong" : "badge-moderate"}">
            ${isStrong ? "STRONG" : "MODERATE"}
          </span>
          <span style="font-size:0.82rem;color:var(--muted)">${s.traderCount} traders converging</span>
        </div>
        <h2 style="margin:0.5rem 0 0.25rem;font-size:1rem">${escapeHtml(s.market)}</h2>
        <div class="signal-details">
          <div class="signal-detail">
            <span>Side</span>
            <strong class="${s.side === "BUY" ? "side-buy" : "side-sell"}">${s.side} ${escapeHtml(s.outcome)}</strong>
          </div>
          ${s.avgPrice ? `
          <div class="signal-detail">
            <span>Avg Price</span>
            <strong>${formatPrice(s.avgPrice)}</strong>
          </div>` : ""}
          <div class="signal-detail">
            <span>Total Traded</span>
            <strong>${formatDollars(s.totalAmount)}</strong>
          </div>
          <div class="signal-detail">
            <span>Suggested Size</span>
            <strong style="color:var(--accent)">$${size}</strong>
          </div>
          ${payout ? `
          <div class="signal-detail">
            <span>Potential Payout</span>
            <strong style="color:var(--good)">$${Math.floor(payout)}</strong>
          </div>` : ""}
        </div>
        <div class="signal-traders">
          ${s.traders.map((t) => `<code>${shortAddr(t)}</code>`).join(" ")}
        </div>
        <p style="font-size:0.82rem;color:var(--muted);margin:0.5rem 0 0">${escapeHtml(s.recommendation)}</p>
        <div class="alert-actions">
          <a href="${escapeHtml(s.url)}" target="_blank" rel="noopener" class="alert-trade-btn">
            Open on Polymarket
          </a>
        </div>
      </div>`;
    })
    .join("");
}

function updateStats() {
  document.getElementById("stat-bankroll").textContent = formatDollars(loadBankroll());
  document.getElementById("stat-signals").textContent = signalsData.length || "0";
  document.getElementById("stat-arb").textContent = arbData.length || "-";
  document.getElementById("stat-traders").textContent = loadWatchlist().length || "0";
}

async function loadMarkets() {
  try {
    const res = await fetch("/api/markets");
    const data = await res.json();
    marketsData.polymarket = data.polymarket || [];
    marketsData.kalshi = data.kalshi || [];
    renderMarkets();
    updateStats();
  } catch (err) {
    console.error("Failed to load markets:", err);
  }
}

async function loadArbitrage() {
  try {
    const res = await fetch("/api/arbitrage");
    const data = await res.json();
    arbData = data.opportunities || [];
    renderArbitrage(arbData);
    updateStats();
  } catch (err) {
    console.error("Failed to load arbitrage:", err);
    document.getElementById("arb-list").innerHTML =
      `<div class="error-msg">Failed to load arbitrage data: ${escapeHtml(err.message)}</div>`;
  }
}

async function refreshAll() {
  await Promise.all([loadMarkets(), loadArbitrage(), renderSuggestedTraders(), loadSmartSignals()]);
}

document.querySelectorAll("#rule-max-size, #rule-categories, #rule-approval, #rule-stoploss").forEach((el) => {
  el.addEventListener("change", saveRules);
  el.addEventListener("input", saveRules);
});

document.getElementById("wallet-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") addTrader();
});

restoreRules();
renderWatchlist();
renderAlertsFeed();
updateStats();
refreshAll();

setInterval(refreshAll, 30_000);
