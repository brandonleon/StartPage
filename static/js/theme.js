const THEME_KEY = "startpage-theme";
const root = document.documentElement;

function applyTheme(theme) {
    root.setAttribute("data-theme", theme);
    localStorage.setItem(THEME_KEY, theme);
    document.querySelectorAll("[data-theme-toggle-label]").forEach((label) => {
        label.textContent = theme === "latte" ? "Dark" : "Light";
    });
}

function initTheme() {
    const storedTheme = localStorage.getItem(THEME_KEY);
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    applyTheme(storedTheme || (prefersDark ? "mocha" : "latte"));

    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
        btn.addEventListener("click", (event) => {
            event.preventDefault();
            const nextTheme = root.getAttribute("data-theme") === "latte" ? "mocha" : "latte";
            applyTheme(nextTheme);
        });
    });
}

function initSearchClear() {
    const searchInput = document.getElementById("search-input");
    const clearBtn = document.querySelector(".search-clear-btn");

    if (searchInput && clearBtn) {
        searchInput.addEventListener("input", () => {
            clearBtn.style.display = searchInput.value ? "block" : "none";
        });
    }
}

document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initSearchClear();
});
