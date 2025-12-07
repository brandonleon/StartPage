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

function initBulkSelection() {
    const form = document.getElementById("bulk-action-form");
    if (!form) {
        return;
    }

    const selectAllBtn = form.querySelector("[data-bulk-select]");
    const bulkDeleteBtn = form.querySelector("[data-bulk-delete]");
    const bulkTagBtn = form.querySelector("[data-bulk-tag]");
    const bulkCount = form.querySelector("[data-bulk-count]");
    const tagInput = form.querySelector("[data-bulk-tags]");

    const getCheckedCount = () => form.querySelectorAll("[data-bulk-checkbox]:checked").length;

    const updateState = () => {
        const allCheckboxes = form.querySelectorAll("[data-bulk-checkbox]");
        const checked = getCheckedCount();
        if (bulkCount) {
            bulkCount.textContent = checked;
        }
        if (bulkDeleteBtn) {
            bulkDeleteBtn.disabled = checked === 0;
        }
        if (bulkTagBtn) {
            const hasTags = tagInput ? tagInput.value.trim().length > 0 : false;
            bulkTagBtn.disabled = checked === 0 || !hasTags;
        }
        if (selectAllBtn) {
            const label = checked === allCheckboxes.length && allCheckboxes.length > 0 ? "Clear all" : "Select all";
            selectAllBtn.textContent = label;
        }
    };

    const bindCheckboxes = () => {
        form.querySelectorAll("[data-bulk-checkbox]").forEach((checkbox) => {
            if (checkbox.dataset.bulkBound === "true") {
                return;
            }
            checkbox.dataset.bulkBound = "true";
            checkbox.addEventListener("change", updateState);
        });
    };

    bindCheckboxes();
    updateState();

    if (tagInput && tagInput.dataset.bulkBound !== "true") {
        tagInput.dataset.bulkBound = "true";
        tagInput.addEventListener("input", updateState);
    }

    if (selectAllBtn && selectAllBtn.dataset.bulkBound !== "true") {
        selectAllBtn.dataset.bulkBound = "true";
        selectAllBtn.addEventListener("click", (event) => {
            event.preventDefault();
            const checkboxes = form.querySelectorAll("[data-bulk-checkbox]");
            if (checkboxes.length === 0) {
                return;
            }
            const shouldSelect = checkboxes.length !== form.querySelectorAll("[data-bulk-checkbox]:checked").length;
            checkboxes.forEach((checkbox) => {
                checkbox.checked = shouldSelect;
            });
            updateState();
        });
    }

    form.querySelectorAll("[data-bulk-action]").forEach((button) => {
        if (button.dataset.bulkActionBound === "true") {
            return;
        }
        button.dataset.bulkActionBound = "true";
        button.addEventListener("click", (event) => {
            const action = button.dataset.bulkAction;
            if (action) {
                form.setAttribute("action", action);
            }
            const requiresSelection = button.dataset.bulkRequiresSelection === "true";
            const requiresTags = button.dataset.bulkRequiresTags === "true";
            if ((requiresSelection && getCheckedCount() === 0) || (requiresTags && (!tagInput || !tagInput.value.trim()))) {
                event.preventDefault();
            }
        });
    });
}

document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initSearchClear();
    initBulkSelection();
});

document.body.addEventListener("htmx:afterSwap", () => {
    initBulkSelection();
});
