(function () {
  const form = document.getElementById("auth-form");
  if (!form) {
    return;
  }

  const modeLoginButton = document.getElementById("mode-login");
  const modeRegisterButton = document.getElementById("mode-register");
  const switchModeButton = document.getElementById("switch-mode");
  const submitButton = document.getElementById("submit-button");
  const description = document.getElementById("auth-description");
  const status = document.getElementById("auth-status");
  const usernameField = document.getElementById("username-field");
  const usernameInput = document.getElementById("username");
  const emailInput = document.getElementById("email");
  const passwordInput = document.getElementById("password");

  const state = {
    mode: "login",
    loading: false,
  };

  function setStatus(message, kind) {
    if (!message) {
      status.textContent = "";
      status.classList.add("is-hidden");
      status.classList.remove("is-error", "is-success");
      return;
    }

    status.textContent = message;
    status.classList.remove("is-hidden", "is-error", "is-success");

    if (kind === "error") {
      status.classList.add("is-error");
      return;
    }

    if (kind === "success") {
      status.classList.add("is-success");
    }
  }

  function setLoading(loading) {
    state.loading = loading;
    submitButton.disabled = loading;
    switchModeButton.disabled = loading;
    modeLoginButton.disabled = loading;
    modeRegisterButton.disabled = loading;
  }

  function setMode(mode) {
    if (state.loading) {
      return;
    }

    state.mode = mode;

    const isRegister = mode === "register";
    modeLoginButton.classList.toggle("is-active", !isRegister);
    modeRegisterButton.classList.toggle("is-active", isRegister);
    modeLoginButton.setAttribute("aria-selected", String(!isRegister));
    modeRegisterButton.setAttribute("aria-selected", String(isRegister));

    usernameField.classList.toggle("is-hidden", !isRegister);
    usernameInput.required = isRegister;

    submitButton.textContent = isRegister ? "Create account" : "Sign in";
    switchModeButton.textContent = isRegister ? "I already have an account" : "Create account";
    description.textContent = isRegister
      ? "Cree un compte pour sauvegarder ta progression automatiquement."
      : "Connecte-toi pour sauvegarder ta progression et apparaitre dans le leaderboard.";

    setStatus("");
  }

  function buildPayload() {
    const payload = {
      email: emailInput.value.trim(),
      password: passwordInput.value,
      remember: Boolean(form.elements.remember && form.elements.remember.checked),
    };

    if (state.mode === "register") {
      payload.username = usernameInput.value.trim();
    }

    return payload;
  }

  function endpointForMode() {
    return state.mode === "register" ? "/api/auth/register" : "/api/auth/login";
  }

  function parseErrorMessage(result, fallback) {
    if (result && typeof result.error === "string" && result.error.trim()) {
      return result.error;
    }
    return fallback;
  }

  async function submitAuth(event) {
    event.preventDefault();

    const payload = buildPayload();
    if (!payload.email || !payload.password) {
      setStatus("Email et mot de passe obligatoires.", "error");
      return;
    }

    if (state.mode === "register" && !payload.username) {
      setStatus("Le pseudo est obligatoire pour creer un compte.", "error");
      return;
    }

    setLoading(true);
    setStatus("");

    try {
      const response = await fetch(endpointForMode(), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(payload),
      });

      const result = await response.json().catch(function () {
        return {};
      });

      if (!response.ok) {
        throw new Error(parseErrorMessage(result, "Erreur pendant l'authentification."));
      }

      const successMessage =
        typeof result.message === "string" && result.message.trim()
          ? result.message
          : state.mode === "register"
            ? "Inscription reussie."
            : "Connexion reussie.";

      setStatus(successMessage + " Redirection...", "success");

      window.setTimeout(function () {
        window.location.href = "dashboard.html";
      }, 700);
    } catch (error) {
      setStatus(
        error instanceof Error
          ? error.message
          : "Impossible de joindre le backend. Lance d'abord `python Connexion.py`.",
        "error"
      );
    } finally {
      setLoading(false);
    }
  }

  async function restoreSessionIfAny() {
    try {
      const response = await fetch("/api/auth/me", {
        method: "GET",
        credentials: "include",
      });

      if (!response.ok) {
        return;
      }

      const result = await response.json();
      if (!result || !result.user) {
        return;
      }

      const username = typeof result.user.username === "string" ? result.user.username : "";
      setStatus("Session active" + (username ? " pour " + username : "") + ". Redirection...", "success");

      window.setTimeout(function () {
        window.location.href = "dashboard.html";
      }, 700);
    } catch (_error) {
      // Ignore auto-check errors when backend is not running.
    }
  }

  modeLoginButton.addEventListener("click", function () {
    setMode("login");
  });

  modeRegisterButton.addEventListener("click", function () {
    setMode("register");
  });

  switchModeButton.addEventListener("click", function () {
    setMode(state.mode === "login" ? "register" : "login");
  });

  form.addEventListener("submit", submitAuth);

  setMode("login");
  restoreSessionIfAny();
})();
