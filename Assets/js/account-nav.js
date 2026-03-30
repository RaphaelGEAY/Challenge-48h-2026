(function () {
  "use strict";

  function getAuthNavLinks() {
    const links = document.querySelectorAll('a[data-auth-link], .nav-menu a[href="login.html"]');
    return Array.from(links);
  }

  function getNavMenu(links) {
    if (!links.length) {
      return null;
    }
    return links[0].closest(".nav-menu");
  }

  function removeLogoutButton(navMenu) {
    if (!navMenu) {
      return;
    }

    const existing = navMenu.querySelector("button[data-auth-logout]");
    if (existing) {
      existing.remove();
    }
  }

  function createLogoutButton(navMenu, onLogout) {
    if (!navMenu) {
      return;
    }

    removeLogoutButton(navMenu);

    const button = document.createElement("button");
    button.type = "button";
    button.className = "auth-logout-btn";
    button.dataset.authLogout = "true";
    button.textContent = "Se deconnecter";

    button.addEventListener("click", async function () {
      if (button.disabled) {
        return;
      }

      button.disabled = true;
      button.textContent = "Deconnexion...";

      try {
        await fetch("/api/auth/logout", {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
          },
        });
      } catch (_error) {
        // If the request fails, we still refresh the UI as guest.
      }

      onLogout();
    });

    navMenu.appendChild(button);
  }

  function setLinkContent(link, title, meta) {
    link.textContent = "";

    const titleEl = document.createElement("span");
    titleEl.className = "auth-nav-title";
    titleEl.textContent = title;
    link.appendChild(titleEl);

    if (meta) {
      const metaEl = document.createElement("span");
      metaEl.className = "auth-nav-meta";
      metaEl.textContent = meta;
      link.appendChild(metaEl);
    }
  }

  function setGuestLinks(links, navMenu) {
    for (const link of links) {
      link.classList.remove("auth-nav-link", "is-account");
      link.removeAttribute("title");
      link.setAttribute("href", "login.html");
      setLinkContent(link, "Sign in", "");

      if (!link.hasAttribute("aria-current") || link.getAttribute("aria-current") !== "page") {
        link.removeAttribute("aria-current");
      }
    }

    removeLogoutButton(navMenu);
  }

  function setAccountLinks(links, user, navMenu) {
    const username = typeof user.username === "string" && user.username.trim() ? user.username.trim() : "Player";
    const email = typeof user.email === "string" && user.email.trim() ? user.email.trim() : "";

    for (const link of links) {
      link.classList.add("auth-nav-link", "is-account");
      link.setAttribute("href", "dashboard.html");
      link.removeAttribute("aria-current");
      setLinkContent(link, "Mon compte", email ? username + " - " + email : username);
      link.title = email ? username + " (" + email + ")" : username;
    }

    createLogoutButton(navMenu, function () {
      setGuestLinks(links, navMenu);
    });
  }

  async function syncAuthNav() {
    const links = getAuthNavLinks();
    if (!links.length) {
      return;
    }
    const navMenu = getNavMenu(links);

    setGuestLinks(links, navMenu);

    try {
      const response = await fetch("/api/auth/me", {
        method: "GET",
        credentials: "include",
      });

      if (!response.ok) {
        return;
      }

      const payload = await response.json().catch(function () {
        return null;
      });

      if (!payload || !payload.ok || !payload.user) {
        return;
      }

      setAccountLinks(links, payload.user, navMenu);
    } catch (_error) {
      // Ignore if backend is down.
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", syncAuthNav);
  } else {
    syncAuthNav();
  }
})();
