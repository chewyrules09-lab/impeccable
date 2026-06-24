const STORAGE_KEY = "pmc-watchlist";
const RULES_KEY = "pmc-rules";

let marketsData = { polymarket: [], kalshi: [] };
let arbData = [];
let currentMarketFilter = "all";
let selectedTrader = null;

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

function shortAddr(addr) {
  if (!addr || addr.length < 12) return addr || "";
  return addr.slice(0, 6) + "..." + addr.slice(-4);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function switchTab(tab) {
  document.querySelectorAll(".tab-bar button").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
  document.getElementById("tab-arbitrage").style.display = tab === "arbitrage" ? "" : "none";
  document.getElementById("tab-markets").style.display = tab === "markets" ? "" : "none";
  document.getElementById("tab-activity").style.display = tab === "activity" ? "" : "none";
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
          return `
          <div class="trade-row">
            <span>${escapeHtml(trade.title || trade.question || trade.market || "Unknown market")}</span>
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

function updateStats() {
  document.getElementById("stat-poly").textContent = marketsData.polymarket.length || "-";
  document.getElementById("stat-kalshi").textContent = marketsData.kalshi.length || "-";
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
  await Promise.all([loadMarkets(), loadArbitrage(), renderSuggestedTraders()]);
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
updateStats();
refreshAll();

setInterval(refreshAll, 30_000);
