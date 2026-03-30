(function () {
  "use strict";

  function qs(sel) {
    return document.querySelector(sel);
  }

  function setText(el, value) {
    if (!el) return;
    el.textContent = value;
  }

  function clamp(n, min, max) {
    return Math.max(min, Math.min(max, n));
  }

  function toPct(value) {
    const num = typeof value === "number" ? value : Number(value);
    if (!Number.isFinite(num)) return null;
    return `${Math.round(num)}%`;
  }

  function formatSeconds(seconds) {
    const sec = Number(seconds);
    if (!Number.isFinite(sec) || sec < 0) return "—";
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    const mm = String(m).padStart(2, "0");
    const ss = String(s).padStart(2, "0");
    return `${mm}:${ss}`;
  }

  function statusToTag(status) {
    const s = String(status || "").toLowerCase();
    if (s === "passed" || s === "pass" || s === "success" || s === "complete" || s === "completed") {
      return { label: "Passed", cls: "good" };
    }
    if (
      s === "partial" ||
      s === "in_progress" ||
      s === "progress" ||
      s === "almost" ||
      s === "partial_success"
    ) {
      return { label: "Partial", cls: "warn" };
    }
    if (s === "failed" || s === "fail" || s === "error") {
      return { label: "Failed", cls: "bad" };
    }
    return { label: "Failed", cls: "bad" };
  }

  function safeJson(response) {
    return response
      .json()
      .catch(function () {
        return null;
      });
  }

  async function fetchJsonTryUrls(urls, options) {
    for (const url of urls) {
      try {
        const res = await fetch(url, options);
        if (!res.ok) continue;
        const data = await safeJson(res);
        return data;
      } catch (_e) {
      }
    }
    return null;
  }

  function computeAccuracyFromAttempts(attempts) {
    let passed = 0;
    let total = 0;
    for (const a of attempts || []) {
      const tp = Number(a.testsPassed ?? a.passedTests ?? a.tests?.passed ?? a.passed ?? 0);
      const tt = Number(a.testsTotal ?? a.totalTests ?? a.tests?.total ?? a.total ?? 0);
      if (!Number.isFinite(tp) || !Number.isFinite(tt)) continue;
      passed += clamp(tp, 0, 1e12);
      total += clamp(tt, 0, 1e12);
    }
    if (total <= 0) return null;
    return (passed / total) * 100;
  }

  function computeXpFromAttempts(attempts) {
    let sum = 0;
    for (const a of attempts || []) {
      const xp = Number(a.xp ?? a.xpDelta ?? a.xpGained ?? a.scoreDelta ?? 0);
      if (!Number.isFinite(xp)) continue;
      sum += xp;
    }
    return sum;
  }

  function renderAttempt(attempt) {
    const status = statusToTag(attempt.status ?? attempt.result);
    const challengeTitle =
      attempt.challengeTitle ||
      attempt.title ||
      attempt.challenge ||
      attempt.challengeName ||
      (attempt.challengeId ? `Challenge #${attempt.challengeId}` : "Challenge");

    const testsPassed =
      attempt.testsPassed ??
      attempt.passedTests ??
      attempt.tests?.passed ??
      attempt.passed ??
      null;
    const testsTotal =
      attempt.testsTotal ??
      attempt.totalTests ??
      attempt.tests?.total ??
      attempt.total ??
      null;

    const timeSeconds =
      attempt.timeSeconds ??
      attempt.timeSec ??
      attempt.durationSeconds ??
      attempt.time ??
      null;

    const xp = Number(attempt.xp ?? attempt.xpDelta ?? attempt.xpGained ?? 0);
    const xpText = Number.isFinite(xp) ? (xp >= 0 ? `+${xp}` : String(xp)) : "—";

    const attemptEl = document.createElement("div");
    attemptEl.className = "attempt";

    attemptEl.innerHTML = `
      <div class="top">
        <strong>${String(challengeTitle)}</strong>
        <span class="tag ${status.cls}">${status.label}</span>
      </div>
      <div class="meta">
        <span>Time: <span class="mono">${formatSeconds(timeSeconds)}</span></span>
        <span>Tests: <span class="mono">${testsPassed == null || testsTotal == null ? "—" : `${testsPassed}/${testsTotal}`}</span></span>
        <span>XP: <span class="mono">${xpText}</span></span>
      </div>
    `;

    return attemptEl;
  }

  function updateProgress(progress) {
    if (!progress) return;

    const getPercent = function (key) {
      if (typeof progress[key] !== "undefined") return progress[key];
      if (Array.isArray(progress.categories)) {
        const item = progress.categories.find((c) => String(c.key || c.id || "").toLowerCase() === String(key).toLowerCase());
        if (!item) return null;
        return item.percent ?? item.value ?? item.pct ?? null;
      }
      return null;
    };

    const arraysPct = getPercent("arrays") ?? getPercent("arraysAndLoops") ?? getPercent("array");
    const stringsPct = getPercent("strings") ?? getPercent("string");
    const condPct = getPercent("conditionals") ?? getPercent("conditionalsAndLogic") ?? getPercent("conditionalsControl");

    const arraysElPct = qs("#dash-progress-arrays-pct");
    const arraysElBar = qs("#dash-progress-arrays-bar");
    const stringsElPct = qs("#dash-progress-strings-pct");
    const stringsElBar = qs("#dash-progress-strings-bar");
    const condElPct = qs("#dash-progress-conditionals-pct");
    const condElBar = qs("#dash-progress-conditionals-bar");

    const arraysLabel = qs("#dash-progress-arrays-label");
    const stringsLabel = qs("#dash-progress-strings-label");
    const condLabel = qs("#dash-progress-conditionals-label");

    const arraysText = toPct(arraysPct);
    const stringsText = toPct(stringsPct);
    const condText = toPct(condPct);

    if (arraysText) setText(arraysElPct, arraysText);
    if (stringsText) setText(stringsElPct, stringsText);
    if (condText) setText(condElPct, condText);

    if (arraysElBar && arraysPct != null) arraysElBar.style.setProperty("--w", `${clamp(Number(arraysPct), 0, 100)}%`);
    if (stringsElBar && stringsPct != null) stringsElBar.style.setProperty("--w", `${clamp(Number(stringsPct), 0, 100)}%`);
    if (condElBar && condPct != null) condElBar.style.setProperty("--w", `${clamp(Number(condPct), 0, 100)}%`);

    if (arraysLabel && typeof progress.arraysLabel === "string") arraysLabel.textContent = progress.arraysLabel;
    if (stringsLabel && typeof progress.stringsLabel === "string") stringsLabel.textContent = progress.stringsLabel;
    if (condLabel && typeof progress.conditionalsLabel === "string") condLabel.textContent = progress.conditionalsLabel;
  }

  async function boot() {
    const subtitleEl = qs("#dash-user-subtitle");
    const attemptsEl = qs("#dash-attempts");

    const fallback = {
      rank: 128,
      streak: 6,
      xpToday: 340,
      accuracy: 92,
      progress: { arrays: 72, strings: 58, conditionals: 81 },
      attempts: [
        { challengeId: 19, status: "passed", timeSeconds: 42, testsPassed: 12, testsTotal: 12, xp: 80 },
        { challengeId: 20, status: "partial", timeSeconds: 70, testsPassed: 9, testsTotal: 12, xp: 35 },
        { challengeId: 18, status: "failed", timeSeconds: 27, testsPassed: 2, testsTotal: 12, xp: 10 },
      ],
    };

    const dashboard = await fetchJsonTryUrls(["/api/dashboard/me"], {
      method: "GET",
      credentials: "include",
    });

    if (!dashboard || dashboard.ok !== true) {
      setText(subtitleEl, "Guest mode: sign in to see your live stats.");
      return;
    }

    const user = dashboard.user || null;
    const stats = dashboard.stats || {};
    const attempts = Array.isArray(dashboard.attempts) ? dashboard.attempts : [];
    const progress = dashboard.progress || null;

    setText(subtitleEl, `Signed in as ${(user && user.username) || "player"}.`);

    const accuracy = stats.accuracy ?? computeAccuracyFromAttempts(attempts) ?? fallback.accuracy;
    const xpTotal = stats.xpTotal ?? computeXpFromAttempts(attempts) ?? fallback.xpToday;

    setText(qs("#dash-rank-value"), stats.rank ?? fallback.rank);
    setText(qs("#dash-streak-value"), stats.streak ?? fallback.streak);
    setText(qs("#dash-streak-label"), `${stats.streak ?? fallback.streak} days`);

    setText(qs("#dash-xp-label"), "Total");
    setText(qs("#dash-xp-value"), xpTotal);

    setText(qs("#dash-accuracy-value"), `${Math.round(Number(accuracy))}%`);
    setText(qs("#dash-accuracy-label"), `${Math.round(Number(accuracy))}%`);

    updateProgress(progress || fallback.progress);

    if (attemptsEl) {
      attemptsEl.innerHTML = "";
      const slice = attempts.slice(0, 6);
      const list = slice.length ? slice : fallback.attempts;
      for (const a of list) attemptsEl.appendChild(renderAttempt(a));
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();

