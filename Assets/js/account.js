(function () {
  "use strict";

  const lockedSection = document.getElementById("account-locked");
  const editorSection = document.getElementById("account-editor");
  const logoutWrap = document.getElementById("account-logout-wrap");
  const form = document.getElementById("account-form");
  const status = document.getElementById("account-status");
  const firstNameInput = document.getElementById("account-first-name");
  const lastNameInput = document.getElementById("account-last-name");
  const usernameInput = document.getElementById("account-username");
  const emailInput = document.getElementById("account-email");
  const currentPasswordInput = document.getElementById("account-current-password");
  const newPasswordInput = document.getElementById("account-new-password");
  const saveButton = document.getElementById("account-save-btn");
  const logoutButton = document.getElementById("account-logout-btn");

  if (
    !lockedSection ||
    !editorSection ||
    !logoutWrap ||
    !form ||
    !status ||
    !firstNameInput ||
    !lastNameInput ||
    !usernameInput ||
    !emailInput ||
    !currentPasswordInput ||
    !newPasswordInput ||
    !saveButton ||
    !logoutButton
  ) {
    return;
  }

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
    } else if (kind === "success") {
      status.classList.add("is-success");
    }
  }

  function showLocked() {
    lockedSection.classList.remove("is-hidden");
    editorSection.classList.add("is-hidden");
    logoutWrap.classList.add("is-hidden");
  }

  function showEditor() {
    lockedSection.classList.add("is-hidden");
    editorSection.classList.remove("is-hidden");
    logoutWrap.classList.remove("is-hidden");
  }

  function setLoading(loading) {
    saveButton.disabled = loading;
    logoutButton.disabled = loading;
  }

  async function safeJson(response) {
    try {
      return await response.json();
    } catch (_error) {
      return {};
    }
  }

  function parseError(payload, fallback) {
    if (payload && typeof payload.error === "string" && payload.error.trim()) {
      return payload.error;
    }
    return fallback;
  }

  async function loadProfile() {
    try {
      const response = await fetch("/api/auth/me", {
        method: "GET",
        credentials: "include",
      });

      if (!response.ok) {
        showLocked();
        return;
      }

      const payload = await safeJson(response);
      if (!payload || !payload.ok || !payload.user) {
        showLocked();
        return;
      }

      firstNameInput.value = payload.user.first_name || "";
      lastNameInput.value = payload.user.last_name || "";
      usernameInput.value = payload.user.username || "";
      emailInput.value = payload.user.email || "";
      currentPasswordInput.value = "";
      newPasswordInput.value = "";
      showEditor();
    } catch (_error) {
      showLocked();
    }
  }

  async function saveProfile(event) {
    event.preventDefault();

    const firstName = firstNameInput.value.trim();
    const lastName = lastNameInput.value.trim();
    const username = usernameInput.value.trim();
    const email = emailInput.value.trim();
    const currentPassword = currentPasswordInput.value;
    const newPassword = newPasswordInput.value;

    if (!firstName || !lastName || !username || !email) {
      setStatus("Prenom, nom, username et email sont obligatoires.", "error");
      return;
    }

    setLoading(true);
    setStatus("");

    try {
      const response = await fetch("/api/account/update", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({
          first_name: firstName,
          last_name: lastName,
          username: username,
          email: email,
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });

      const payload = await safeJson(response);
      if (!response.ok) {
        throw new Error(parseError(payload, "Impossible de mettre a jour le compte."));
      }

      if (payload && payload.user) {
        firstNameInput.value = payload.user.first_name || firstName;
        lastNameInput.value = payload.user.last_name || lastName;
        usernameInput.value = payload.user.username || username;
        emailInput.value = payload.user.email || email;
      }

      currentPasswordInput.value = "";
      newPasswordInput.value = "";
      setStatus(payload.message || "Parametres mis a jour.", "success");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Erreur de mise a jour.", "error");
    } finally {
      setLoading(false);
    }
  }

  async function logout() {
    if (logoutButton.disabled) {
      return;
    }

    setLoading(true);
    setStatus("");

    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
      });
    } catch (_error) {
      // Ignore network error and proceed to login page.
    }

    window.location.href = "login.html";
  }

  form.addEventListener("submit", saveProfile);
  logoutButton.addEventListener("click", logout);
  loadProfile();
})();
