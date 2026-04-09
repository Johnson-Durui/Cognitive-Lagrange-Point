(function () {
  const storageKeys = {
    favorite: "ai-digest:favorites",
    read: "ai-digest:reads",
  };

  const bootstrap = window.AI_DIGEST_BOOTSTRAP || {};

  function loadSet(name) {
    try {
      const raw = localStorage.getItem(storageKeys[name]);
      return new Set(raw ? JSON.parse(raw) : []);
    } catch (error) {
      return new Set();
    }
  }

  function saveSet(name, values) {
    try {
      localStorage.setItem(storageKeys[name], JSON.stringify(Array.from(values)));
    } catch (error) {
      console.warn("localStorage unavailable:", error);
    }
  }

  function detailPath(item) {
    return item.detail_path || `items/${slugify(item.source + "-" + (item.full_name || item.title || item.id))}.html`;
  }

  function slugify(value) {
    return value
      .toLowerCase()
      .replace(/[^a-z0-9-_]+/g, "-")
      .replace(/--+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 96);
  }

  function formatDate(value) {
    if (!value) return "未知";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString("zh-CN", { hour12: false });
  }

  function createCard(item, favorites, reads) {
    const favorite = favorites.has(item.id);
    const read = reads.has(item.id);
    const container = document.createElement("article");
    container.className = "digest-card";
    container.dataset.itemId = item.id;
    container.dataset.source = item.source || "";
    container.dataset.kind = item.kind || "";
    container.innerHTML = `
      <div class="card-topline">
        <span class="badge">${(item.source || "").toUpperCase()}</span>
        <span class="badge badge-soft">${item.kind || "item"}</span>
        <span class="score">${item.relevance_score || 0}/10</span>
      </div>
      <h3>${item.title || item.full_name || item.name || "未命名条目"}</h3>
      <p class="card-summary">${item.summary || item.description || ""}</p>
      ${item.selection_reason ? `<p class="card-selection">${item.selection_reason}</p>` : ""}
      <div class="tag-list">
        ${(item.tags || item.topics || item.categories || [])
          .slice(0, 6)
          .map((tag) => `<span class="tag-chip">${tag}</span>`)
          .join("")}
      </div>
      <div class="meta-grid compact">
        ${item.language ? `<span>语言：${item.language}</span>` : ""}
        ${typeof item.stars === "number" ? `<span>Stars：${item.stars}</span>` : ""}
        ${item.stars_today ? `<span>今日热度：+${item.stars_today}</span>` : ""}
        ${item.published_at ? `<span>发布时间：${formatDate(item.published_at)}</span>` : ""}
        ${item.last_notified_at ? `<span>收录：${formatDate(item.last_notified_at)}</span>` : ""}
      </div>
      <div class="card-actions">
        <button class="toggle-button ${favorite ? "active" : ""}" data-action="favorite" data-item-key="${item.id}">
          ${favorite ? "已收藏" : "收藏"}
        </button>
        <button class="toggle-button ${read ? "active" : ""}" data-action="read" data-item-key="${item.id}">
          ${read ? "已读" : "标记已读"}
        </button>
        <a class="primary-link" href="${detailPath(item)}">查看详情</a>
        <a class="secondary-link" href="${item.html_url}" target="_blank" rel="noreferrer">原文</a>
      </div>
    `;
    return container;
  }

  function renderSidebarBlocks(items) {
    const mustWatchRoot = document.getElementById("must-watch-list");
    const themeRoot = document.getElementById("theme-clusters");
    const reportRoot = document.getElementById("report-links");
    const sectionRoot = document.getElementById("section-strip");

    if (mustWatchRoot) {
      const mustWatch = (bootstrap.sections && bootstrap.sections.must_watch) || [];
      mustWatchRoot.innerHTML = mustWatch
        .map(
          (item) => `
            <a class="mini-card" href="${detailPath(item)}">
              <strong>${item.title || item.full_name || item.name}</strong>
              <span>${item.selection_reason || item.why_it_matters || item.summary || ""}</span>
            </a>
          `
        )
        .join("");
    }

    if (themeRoot) {
      const clusters = bootstrap.themeClusters || [];
      themeRoot.innerHTML = clusters
        .map(
          (cluster) => `
            <div class="mini-card static">
              <strong>${cluster.theme}</strong>
              <span>${cluster.count} 条，代表项：${(cluster.leaders || []).slice(0, 2).join("、")}</span>
            </div>
          `
        )
        .join("");
    }

    if (reportRoot) {
      const reports = bootstrap.reports || {};
      reportRoot.innerHTML = Object.entries(reports)
        .map(
          ([key, report]) => `
            <a class="mini-card" href="${bootstrap.mode === "archive" ? "../" : ""}reports/${key}.html">
              <strong>${report.label}</strong>
              <span>${report.summary || ""}</span>
            </a>
          `
        )
        .join("");
    }

    if (sectionRoot) {
      const sectionCards = [];
      const mustWatch = (bootstrap.sections && bootstrap.sections.must_watch) || [];
      const worthScan = (bootstrap.sections && bootstrap.sections.worth_scan) || [];
      const paperSpotlight = (bootstrap.sections && bootstrap.sections.paper_spotlight) || [];
      if (mustWatch.length) sectionCards.push(`<div class="section-chip"><strong>必看</strong><span>${mustWatch.length} 条</span></div>`);
      if (worthScan.length) sectionCards.push(`<div class="section-chip"><strong>值得扫一眼</strong><span>${worthScan.length} 条</span></div>`);
      if (paperSpotlight.length) sectionCards.push(`<div class="section-chip"><strong>论文观察</strong><span>${paperSpotlight.length} 条</span></div>`);
      sectionRoot.innerHTML = sectionCards.join("");
    }
  }

  function wireToggleButtons(root, favorites, reads) {
    root.querySelectorAll("[data-action]").forEach((button) => {
      button.addEventListener("click", () => {
        const action = button.dataset.action;
        const itemKey = button.dataset.itemKey;
        const targetSet = action === "favorite" ? favorites : reads;
        if (targetSet.has(itemKey)) {
          targetSet.delete(itemKey);
        } else {
          targetSet.add(itemKey);
        }
        saveSet(action, targetSet);
        updateActionLabels(document, favorites, reads);
      });
    });
  }

  function updateActionLabels(root, favorites, reads) {
    root.querySelectorAll('[data-action="favorite"]').forEach((button) => {
      const active = favorites.has(button.dataset.itemKey);
      button.classList.toggle("active", active);
      button.textContent = active ? "已收藏" : "收藏";
    });

    root.querySelectorAll('[data-action="read"]').forEach((button) => {
      const active = reads.has(button.dataset.itemKey);
      button.classList.toggle("active", active);
      button.textContent = active ? "已读" : "标记已读";
    });
  }

  function fillSelect(select, values) {
    values
      .filter(Boolean)
      .sort((left, right) => left.localeCompare(right))
      .forEach((value) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
      });
  }

  function withinDays(item, maxDays) {
    if (maxDays === "all") return true;
    const value = item.last_notified_at || item.published_at || item.created_at || item.updated_at;
    if (!value) return false;
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return false;
    const diffMs = Date.now() - date.getTime();
    return diffMs <= Number(maxDays) * 24 * 60 * 60 * 1000;
  }

  function matchesFilters(item, state) {
    const searchHaystack = [
      item.title,
      item.full_name,
      item.summary,
      item.description,
      ...(item.tags || []),
      ...(item.topics || []),
      ...(item.categories || []),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    if (state.query && !searchHaystack.includes(state.query)) return false;
    if (state.source && item.source !== state.source) return false;
    if (state.tag) {
      const tags = [...(item.tags || []), ...(item.topics || []), ...(item.categories || [])];
      if (!tags.includes(state.tag)) return false;
    }
    if (!withinDays(item, state.days)) return false;
    return true;
  }

  function renderList(items) {
    const pageTitle = document.getElementById("page-title");
    const pageSubtitle = document.getElementById("page-subtitle");
    const cardList = document.getElementById("card-list");
    const meta = document.getElementById("results-meta");
    const emptyState = document.getElementById("empty-state");
    if (!cardList) return;

    pageTitle.textContent = bootstrap.title || "AI Daily Digest";
    pageSubtitle.textContent = bootstrap.subtitle || "";
    renderSidebarBlocks(items);

    const favorites = loadSet("favorite");
    const reads = loadSet("read");

    const sourceFilter = document.getElementById("source-filter");
    const tagFilter = document.getElementById("tag-filter");
    if (sourceFilter && sourceFilter.options.length === 1) {
      fillSelect(sourceFilter, [...new Set(items.map((item) => item.source).filter(Boolean))]);
    }
    if (tagFilter && tagFilter.options.length === 1) {
      fillSelect(
        tagFilter,
        [
          ...new Set(
            items.flatMap((item) => [...(item.tags || []), ...(item.topics || []), ...(item.categories || [])]).filter(Boolean)
          ),
        ]
      );
    }

    function update() {
      const state = {
        query: (document.getElementById("search-input")?.value || "").trim().toLowerCase(),
        source: document.getElementById("source-filter")?.value || "",
        tag: document.getElementById("tag-filter")?.value || "",
        days: document.getElementById("date-filter")?.value || "all",
      };

      const visible = items.filter((item) => matchesFilters(item, state));
      cardList.innerHTML = "";
      visible.forEach((item) => cardList.appendChild(createCard(item, favorites, reads)));
      wireToggleButtons(cardList, favorites, reads);
      updateActionLabels(cardList, favorites, reads);
      meta.textContent = `当前显示 ${visible.length} / ${items.length} 条`;
      emptyState.hidden = visible.length > 0;
    }

    ["search-input", "source-filter", "tag-filter", "date-filter"].forEach((id) => {
      const element = document.getElementById(id);
      if (element) {
        element.addEventListener("input", update);
        element.addEventListener("change", update);
      }
    });

    update();
  }

  function initDetailPage() {
    if (bootstrap.mode !== "detail" || !bootstrap.item) return;
    const favorites = loadSet("favorite");
    const reads = loadSet("read");
    reads.add(bootstrap.item.id);
    saveSet("read", reads);
    wireToggleButtons(document, favorites, reads);
    updateActionLabels(document, favorites, reads);
  }

  async function initListPage() {
    if (bootstrap.mode === "detail") return;
    let items = bootstrap.items || [];
    if (bootstrap.mode === "archive" && bootstrap.searchIndexUrl) {
      try {
        const response = await fetch(bootstrap.searchIndexUrl);
        if (response.ok) {
          const payload = await response.json();
          items = payload.items || items;
        }
      } catch (error) {
        console.warn("Failed to load archive index:", error);
      }
    }
    renderList(items);
  }

  document.addEventListener("DOMContentLoaded", async () => {
    await initListPage();
    initDetailPage();
  });
})();
