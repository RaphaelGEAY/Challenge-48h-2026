(function () {
  "use strict";

  const levelSelect = document.getElementById("play-level-select");
  const loadLevelButton = document.getElementById("play-load-level");
  const saveCodeButton = document.getElementById("play-save-code");
  const runButton = document.getElementById("play-run-btn");
  const submitButton = document.getElementById("play-submit-btn");
  const codeEditor = document.getElementById("play-code");
  const mazeRoot = document.getElementById("play-maze");
  const consoleRoot = document.getElementById("play-console");
  const statusPill = document.getElementById("play-status-pill");
  const levelPill = document.getElementById("play-level-pill");
  const runMeta = document.getElementById("play-run-meta");

  if (
    !levelSelect ||
    !loadLevelButton ||
    !saveCodeButton ||
    !runButton ||
    !submitButton ||
    !codeEditor ||
    !mazeRoot ||
    !consoleRoot ||
    !statusPill ||
    !levelPill ||
    !runMeta
  ) {
    return;
  }

  const state = {
    levels: [],
    level: "",
    maze: [],
    startedAt: Date.now(),
    busy: false,
  };

  function sleep(ms) {
    return new Promise(function (resolve) {
      window.setTimeout(resolve, ms);
    });
  }

  function elapsedSeconds() {
    return Math.max(0, Math.floor((Date.now() - state.startedAt) / 1000));
  }

  function setBusy(busy) {
    state.busy = busy;
    levelSelect.disabled = busy;
    loadLevelButton.disabled = busy;
    saveCodeButton.disabled = busy;
    runButton.disabled = busy;
    submitButton.disabled = busy;
  }

  function setConsole(text) {
    consoleRoot.textContent = text;
  }

  function setRunMeta(text) {
    runMeta.innerHTML = '<span class="spinner" aria-hidden="true"></span><span>' + text + "</span>";
  }

  function setStatus(kind, text) {
    statusPill.classList.remove("warn", "good", "bad");
    if (kind === "warn" || kind === "good" || kind === "bad") {
      statusPill.classList.add(kind);
    }
    statusPill.innerHTML = '<span class="icon-dot" aria-hidden="true"></span>' + text;
  }

  function parseJsonSafe(response) {
    return response.json().catch(function () {
      return {};
    });
  }

  async function api(path, options) {
    const response = await fetch(path, {
      method: options && options.method ? options.method : "GET",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
      },
      body: options && options.body ? JSON.stringify(options.body) : undefined,
    });

    const payload = await parseJsonSafe(response);
    if (!response.ok || payload.ok === false) {
      const message =
        typeof payload.error === "string" && payload.error.trim()
          ? payload.error
          : "Request failed";
      throw new Error(message);
    }
    return payload;
  }

  function renderMaze(maze, playerPos) {
    state.maze = Array.isArray(maze) ? maze : [];
    const rows = state.maze.length;
    const cols = rows > 0 && Array.isArray(state.maze[0]) ? state.maze[0].length : 0;

    mazeRoot.innerHTML = "";
    mazeRoot.style.gridTemplateColumns = "repeat(" + Math.max(1, cols) + ", 24px)";

    for (let i = 0; i < rows; i += 1) {
      const row = Array.isArray(state.maze[i]) ? state.maze[i] : [];
      for (let j = 0; j < cols; j += 1) {
        const cell = document.createElement("div");
        cell.className = "maze-cell";
        const value = typeof row[j] === "string" ? row[j] : " ";

        if (playerPos && playerPos[0] === i && playerPos[1] === j) {
          cell.classList.add("maze-player");
          cell.textContent = "P";
        } else if (value === "#") {
          cell.classList.add("maze-wall");
        } else if (value === "S" || value === "P") {
          cell.classList.add("maze-start");
          cell.textContent = "S";
        } else if (value === "O") {
          cell.classList.add("maze-goal");
          cell.textContent = "O";
        } else {
          cell.classList.add("maze-space");
        }

        mazeRoot.appendChild(cell);
      }
    }
  }

  function readSelectedLevel() {
    const raw = String(levelSelect.value || "").trim();
    return raw || state.level || "maze1";
  }

  async function loadLevel(levelKey) {
    const key = levelKey || readSelectedLevel();
    setBusy(true);
    setStatus("warn", "Loading...");
    setRunMeta("Loading maze and code...");

    try {
      const [mazePayload, codePayload] = await Promise.all([
        api("/api/game/maze?level=" + encodeURIComponent(key)),
        api("/api/game/code?level=" + encodeURIComponent(key)),
      ]);

      const resolvedLevel = typeof mazePayload.level === "string" ? mazePayload.level : key;
      state.level = resolvedLevel;
      levelSelect.value = resolvedLevel;
      levelPill.innerHTML = '<span class="icon-dot" aria-hidden="true"></span>Level: ' + resolvedLevel;

      renderMaze(mazePayload.maze || [], null);
      codeEditor.value = typeof codePayload.content === "string" ? codePayload.content : "";
      state.startedAt = Date.now();

      setStatus("warn", "Ready");
      setRunMeta("Ready to run");
      setConsole("Level loaded: " + resolvedLevel);
    } catch (error) {
      setStatus("bad", "Load failed");
      setRunMeta("Unable to load level");
      setConsole(error instanceof Error ? error.message : "Unable to load level.");
    } finally {
      setBusy(false);
    }
  }

  async function loadLevels() {
    setBusy(true);
    setRunMeta("Loading levels...");

    try {
      const payload = await api("/api/game/levels");
      const levels = Array.isArray(payload.levels) ? payload.levels : [];
      state.levels = levels;
      levelSelect.innerHTML = "";

      for (const level of levels) {
        const key = typeof level.key === "string" ? level.key : "";
        if (!key) {
          continue;
        }
        const option = document.createElement("option");
        option.value = key;
        option.textContent = level.name ? String(level.name) : key;
        levelSelect.appendChild(option);
      }

      const firstLevel =
        (typeof payload.default_level === "string" && payload.default_level) ||
        (levels[0] && typeof levels[0].key === "string" ? levels[0].key : "maze1");
      await loadLevel(firstLevel);
    } catch (error) {
      setStatus("bad", "Setup failed");
      setRunMeta("No levels available");
      setConsole(error instanceof Error ? error.message : "Unable to load levels.");
      setBusy(false);
    }
  }

  async function saveCode() {
    if (state.busy) {
      return;
    }

    const content = codeEditor.value;
    const level = readSelectedLevel();
    if (!content.trim()) {
      setConsole("Code editor is empty.");
      return;
    }

    setBusy(true);
    setRunMeta("Saving code...");

    try {
      await api("/api/game/code/save", {
        method: "POST",
        body: {
          level: level,
          content: content,
        },
      });
      setStatus("good", "Saved");
      setRunMeta("Code saved");
      setConsole("Code saved for " + level + ".");
    } catch (error) {
      setStatus("bad", "Save failed");
      setRunMeta("Unable to save");
      setConsole(
        error instanceof Error
          ? error.message
          : "Save failed. Sign in is required."
      );
    } finally {
      setBusy(false);
    }
  }

  async function animatePath(history) {
    if (!Array.isArray(history) || !history.length) {
      return;
    }

    const maxFrames = 220;
    const delay = 45;
    const frames =
      history.length <= maxFrames
        ? history
        : history.filter(function (_item, index) {
            return index % Math.ceil(history.length / maxFrames) === 0;
          });

    for (const position of frames) {
      if (!Array.isArray(position) || position.length !== 2) {
        continue;
      }
      renderMaze(state.maze, position);
      await sleep(delay);
    }
  }

  async function runOrSubmit(kind) {
    if (state.busy) {
      return;
    }

    const level = readSelectedLevel();
    const content = codeEditor.value;
    if (!content.trim()) {
      setConsole("Write code before running.");
      return;
    }

    setBusy(true);
    setStatus("warn", kind === "submit" ? "Submitting..." : "Running...");
    setRunMeta(kind === "submit" ? "Submitting attempt..." : "Executing code...");

    try {
      const payload = await api(kind === "submit" ? "/api/game/submit" : "/api/game/run", {
        method: "POST",
        body: {
          level: level,
          content: content,
          time_seconds: elapsedSeconds(),
        },
      });

      const run = payload.run || {};
      const status = String(run.status || "failed").toLowerCase();
      const passed = status === "passed";

      await animatePath(Array.isArray(run.history) ? run.history : []);
      if (Array.isArray(run.current) && run.current.length === 2) {
        renderMaze(state.maze, run.current);
      }

      if (passed) {
        setStatus("good", "Passed");
      } else {
        setStatus("bad", "Failed");
      }

      const lines = [];
      lines.push("Level: " + level);
      lines.push("Status: " + status);
      lines.push("Steps: " + String(run.steps || 0));
      if (typeof run.message === "string" && run.message.trim()) {
        lines.push("Message: " + run.message);
      }
      if (typeof run.error === "string" && run.error.trim()) {
        lines.push("Error: " + run.error);
      }

      if (kind === "submit" && payload.attempt) {
        lines.push("XP: " + String(payload.attempt.xp_delta));
        lines.push("Recorded attempt #" + String(payload.attempt.id || "n/a"));
      }

      setConsole(lines.join("\n"));
      setRunMeta(kind === "submit" ? "Submission completed" : "Run completed");
    } catch (error) {
      setStatus("bad", "Error");
      setRunMeta("Execution failed");
      setConsole(error instanceof Error ? error.message : "Unexpected execution error.");
    } finally {
      setBusy(false);
    }
  }

  function bindEvents() {
    levelSelect.addEventListener("change", function () {
      loadLevel(readSelectedLevel());
    });

    loadLevelButton.addEventListener("click", function () {
      loadLevel(readSelectedLevel());
    });

    saveCodeButton.addEventListener("click", function () {
      saveCode();
    });

    runButton.addEventListener("click", function () {
      runOrSubmit("run");
    });

    submitButton.addEventListener("click", function () {
      runOrSubmit("submit");
    });
  }

  bindEvents();
  loadLevels();
})();
