(function () {
  "use strict";

  function getAuthNavLinks() {
    const links = document.querySelectorAll('a[data-auth-link], .nav-menu a[href="login.html"]');
    return Array.from(links);
  }

  function isAccountPage() {
    const path = window.location.pathname.toLowerCase();
    return path.endsWith("/account.html") || path.endsWith("account.html");
  }

  function setLinkContent(link, title) {
    link.textContent = "";
    const titleEl = document.createElement("span");
    titleEl.className = "auth-nav-title";
    titleEl.textContent = title;
    link.appendChild(titleEl);
  }

  function setGuestLinks(links) {
    const onAccountPage = isAccountPage();

    for (const link of links) {
      link.classList.remove("auth-nav-link", "is-account");
      link.removeAttribute("title");
      link.setAttribute("href", "login.html");
      setLinkContent(link, "Sign in");

      if (onAccountPage) {
        link.setAttribute("aria-current", "page");
      } else if (!link.hasAttribute("aria-current") || link.getAttribute("aria-current") !== "page") {
        link.removeAttribute("aria-current");
      }
    }
  }

  function setAccountLinks(links, user) {
    const onAccountPage = isAccountPage();
    const firstName = user && typeof user.first_name === "string" ? user.first_name.trim() : "";
    const lastName = user && typeof user.last_name === "string" ? user.last_name.trim() : "";
    const username = user && typeof user.username === "string" ? user.username.trim() : "";
    const displayName = (firstName + " " + lastName).trim() || username || "Mon compte";

    for (const link of links) {
      link.classList.add("auth-nav-link", "is-account");
      link.setAttribute("href", "account.html");
      if (onAccountPage) {
        link.setAttribute("aria-current", "page");
      } else {
        link.removeAttribute("aria-current");
      }
      setLinkContent(link, "Mon compte");
      link.title = displayName;
    }
  }

  async function syncAuthNav() {
    const links = getAuthNavLinks();
    if (!links.length) {
      return;
    }

    setGuestLinks(links);

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

      setAccountLinks(links, payload.user);
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
