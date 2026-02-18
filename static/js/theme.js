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
    // Check if theme is set via URL parameter
    const urlTheme = root.getAttribute("data-theme");
    const storedTheme = localStorage.getItem(THEME_KEY);
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;

    let themeToApply;

    // Priority: URL parameter > localStorage > system preference
    if (urlTheme === "system") {
        // Use system preference when explicitly set to "system"
        themeToApply = prefersDark ? "mocha" : "latte";
    } else if (urlTheme && (urlTheme === "latte" || urlTheme === "mocha")) {
        // Use URL-specified theme (don't save to localStorage for URL-based themes)
        themeToApply = urlTheme;
        root.setAttribute("data-theme", themeToApply);
        // Update toggle label without saving to localStorage
        document.querySelectorAll("[data-theme-toggle-label]").forEach((label) => {
            label.textContent = themeToApply === "latte" ? "Dark" : "Light";
        });
        return; // Skip localStorage and toggle setup for URL-controlled themes
    } else {
        // Fall back to stored preference or system preference
        themeToApply = storedTheme || (prefersDark ? "mocha" : "latte");
    }

    applyTheme(themeToApply);

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

function initTagSuggestions() {
    document.querySelectorAll("[data-tag-input]").forEach((input) => {
        if (input.dataset.tagSuggestionsBound === "true") {
            return;
        }
        input.dataset.tagSuggestionsBound = "true";
        let suggestions = [];
        try {
            suggestions = JSON.parse(input.dataset.tagSuggestions || "[]");
        } catch {
            suggestions = [];
        }
        if (!Array.isArray(suggestions) || suggestions.length === 0) {
            return;
        }
        const normalizeTag = (value) => {
            if (!value) {
                return "";
            }
            return String(value)
                .toLowerCase()
                .replace(/\s+/g, "-")
                .replace(/[^a-z0-9-]/g, "")
                .replace(/-+/g, "-")
                .replace(/^-+|-+$/g, "");
        };
        suggestions = suggestions
            .map((tag) => normalizeTag(String(tag)))
            .filter((tag, index, list) => tag && list.indexOf(tag) === index);
        if (suggestions.length === 0) {
            return;
        }
        const container = document.createElement("div");
        container.className = "tag-suggestions";
        input.insertAdjacentElement("afterend", container);

        const getState = () => {
            const raw = input.value || "";
            const trailingDelimiter = /,\s*$/.test(raw);
            const parts = raw.split(",");
            if (trailingDelimiter && parts.length > 0) {
                parts.pop();
            }
            let activePart = "";
            if (!trailingDelimiter) {
                activePart = parts.pop() ?? "";
            }
            const committed = parts.map((part) => part.trim()).filter((part) => part.length > 0);
            const normalizedCommitted = committed.map((part) => normalizeTag(part));
            const normalizedActive = normalizeTag(activePart);
            return {
                committed,
                normalizedCommitted,
                active: activePart,
                normalizedActive,
                trailingDelimiter,
            };
        };

        const hideSuggestions = () => {
            container.classList.remove("is-visible");
            container.innerHTML = "";
        };

        const applySuggestion = (tag) => {
            const normalized = normalizeTag(tag);
            if (!normalized) {
                hideSuggestions();
                return;
            }
            const { normalizedCommitted } = getState();
            const tokens = normalizedCommitted.slice();
            if (!tokens.includes(normalized)) {
                tokens.push(normalized);
            }
            const nextValue = `${tokens.join(", ")}, `;
            input.value = nextValue;
            hideSuggestions();
            input.focus();
            if (typeof input.setSelectionRange === "function") {
                input.setSelectionRange(nextValue.length, nextValue.length);
            }
            input.dispatchEvent(new Event("input"));
        };

        const updateSuggestions = () => {
            const { normalizedCommitted, normalizedActive } = getState();
            const committedSet = new Set(normalizedCommitted);
            const query = normalizedActive;
            const matches = suggestions
                .filter((tag) => {
                    if (committedSet.has(tag)) {
                        return false;
                    }
                    if (!query) {
                        return true;
                    }
                    return tag.startsWith(query);
                })
                .slice(0, 6);
            if (matches.length === 0) {
                hideSuggestions();
                return;
            }
            container.innerHTML = "";
            matches.forEach((tag) => {
                const button = document.createElement("button");
                button.type = "button";
                button.textContent = tag;
                button.addEventListener("click", (event) => {
                    event.preventDefault();
                    applySuggestion(tag);
                });
                container.appendChild(button);
            });
            container.classList.add("is-visible");
        };

        input.addEventListener("input", updateSuggestions);
        input.addEventListener("focus", updateSuggestions);
        input.addEventListener("blur", () => {
            setTimeout(() => hideSuggestions(), 120);
        });
        container.addEventListener("mousedown", (event) => event.preventDefault());
        document.addEventListener("click", (event) => {
            if (event.target === input || container.contains(event.target)) {
                return;
            }
            hideSuggestions();
        });
    });
}

function initTagChoices() {
    const normalizeTag = (value) => {
        if (!value) {
            return "";
        }
        return String(value)
            .toLowerCase()
            .replace(/\s+/g, "-")
            .replace(/[^a-z0-9-]/g, "")
            .replace(/-+/g, "-")
            .replace(/^-+|-+$/g, "");
    };

    document.querySelectorAll("[data-tag-choice]").forEach((button) => {
        if (button.dataset.tagChoiceBound === "true") {
            return;
        }
        button.dataset.tagChoiceBound = "true";

        button.addEventListener("click", (event) => {
            event.preventDefault();
            const targetId = button.dataset.tagTarget;
            if (!targetId) {
                return;
            }
            const input = document.getElementById(targetId);
            if (!input) {
                return;
            }

            const picked = normalizeTag(button.dataset.tagChoice || "");
            if (!picked) {
                return;
            }

            const committed = (input.value || "")
                .split(",")
                .map((part) => normalizeTag(part))
                .filter((part) => part.length > 0);
            const tags = [...new Set(committed)];
            if (!tags.includes(picked)) {
                tags.push(picked);
            }

            const nextValue = `${tags.join(", ")}, `;
            input.value = nextValue;
            input.focus();
            if (typeof input.setSelectionRange === "function") {
                input.setSelectionRange(nextValue.length, nextValue.length);
            }
            input.dispatchEvent(new Event("input"));
        });
    });
}

function initTagRenameControls() {
    document.querySelectorAll("[data-tag-rename-toggle]").forEach((button) => {
        if (button.dataset.tagRenameBound === "true") {
            return;
        }
        button.dataset.tagRenameBound = "true";
        button.addEventListener("click", (event) => {
            event.preventDefault();
            const card = button.closest("[data-tag-card]");
            if (!card) {
                return;
            }
            const form = card.querySelector("[data-tag-rename-form]");
            const actions = card.querySelector("[data-tag-actions]");
            if (!form) {
                return;
            }
            const shouldShow = form.classList.contains("d-none");
            document.querySelectorAll("[data-tag-rename-form]").forEach((otherForm) => {
                if (otherForm === form) {
                    return;
                }
                otherForm.classList.add("d-none");
                const otherCard = otherForm.closest("[data-tag-card]");
                otherCard?.querySelector("[data-tag-actions]")?.classList.remove("d-none");
                otherCard?.querySelector("[data-tag-rename-toggle]")?.setAttribute("aria-expanded", "false");
            });
            if (shouldShow) {
                form.classList.remove("d-none");
                actions?.classList.add("d-none");
                const input = form.querySelector("input[name='new_name']");
                if (input) {
                    input.focus();
                    input.select();
                }
                button.setAttribute("aria-expanded", "true");
            } else {
                form.classList.add("d-none");
                actions?.classList.remove("d-none");
                button.setAttribute("aria-expanded", "false");
            }
        });
    });

    document.querySelectorAll("[data-tag-rename-cancel]").forEach((button) => {
        if (button.dataset.tagRenameCancelBound === "true") {
            return;
        }
        button.dataset.tagRenameCancelBound = "true";
        button.addEventListener("click", (event) => {
            event.preventDefault();
            const form = button.closest("[data-tag-rename-form]");
            const card = button.closest("[data-tag-card]");
            form?.classList.add("d-none");
            card?.querySelector("[data-tag-actions]")?.classList.remove("d-none");
            card?.querySelector("[data-tag-rename-toggle]")?.setAttribute("aria-expanded", "false");
        });
    });
}

function initTemporaryLinkControls() {
    document.querySelectorAll("[data-temp-link-section]").forEach((section) => {
        if (section.dataset.tempBound === "true") {
            return;
        }
        section.dataset.tempBound = "true";
        const toggle = section.querySelector("[data-temp-toggle]");
        const preset = section.querySelector("[data-temp-preset]");
        const customContainer = section.querySelector("[data-temp-custom]");
        const customInput = section.querySelector("[data-temp-custom-input]");

        const updateState = () => {
            const enabled = Boolean(toggle?.checked);
            if (preset) {
                preset.disabled = !enabled;
            }
            const shouldShowCustom = enabled && preset && preset.value === "custom";
            if (customContainer) {
                customContainer.hidden = !shouldShowCustom;
            }
            if (customInput) {
                customInput.disabled = !shouldShowCustom;
            }
        };

        toggle?.addEventListener("change", updateState);
        preset?.addEventListener("change", updateState);
        updateState();
    });
}

function initFilterResetBehavior() {
    const resetEnabled = document.body.dataset.resetFilterOnClick === "true";
    if (!resetEnabled) return;

    const isFiltered = document.body.dataset.isFiltered === "true";
    const searchInput = document.getElementById("search-input");
    const links = document.querySelectorAll('a[href^="/redirect/"]');

    links.forEach((anchor) => {
        if (anchor.dataset.filterResetBound) return;
        anchor.dataset.filterResetBound = "true";

        anchor.addEventListener("click", () => {
            const hasSearchActive = searchInput?.value.trim().length > 0;

            // No filters active - nothing to do
            if (!isFiltered && !hasSearchActive) return;

            // Let target="_blank" open the link naturally
            // Just reset the filter in this tab
            if (hasSearchActive) {
                searchInput.value = "";
                const clearBtn = document.querySelector(".search-clear-btn");
                if (clearBtn) clearBtn.style.display = "none";
                htmx.trigger(searchInput.parentElement, "search");
            } else if (isFiltered) {
                // Delay navigation slightly to let the browser open the link first
                setTimeout(() => window.location.href = "/", 100);
            }
        });
    });
}

function initCustomHtmxConfirm() {
    if (!window.htmx || document.body.dataset.customConfirmBound === "true") {
        return;
    }
    document.body.dataset.customConfirmBound = "true";

    const backdrop = document.createElement("div");
    backdrop.className = "custom-confirm-backdrop";
    backdrop.setAttribute("hidden", "hidden");
    backdrop.innerHTML = `
        <div class="glass-panel custom-confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="custom-confirm-title">
            <p class="text-uppercase text-muted small mb-2">Confirm action</p>
            <h2 class="h5 mb-2" id="custom-confirm-title">Are you sure?</h2>
            <p class="mb-0" data-custom-confirm-message></p>
            <div class="d-flex justify-content-end gap-2 mt-4">
                <button type="button" class="btn btn-outline-secondary" data-custom-confirm-cancel>Cancel</button>
                <button type="button" class="btn btn-primary" data-custom-confirm-accept>Confirm</button>
            </div>
        </div>
    `;
    document.body.appendChild(backdrop);

    const messageEl = backdrop.querySelector("[data-custom-confirm-message]");
    const cancelBtn = backdrop.querySelector("[data-custom-confirm-cancel]");
    const acceptBtn = backdrop.querySelector("[data-custom-confirm-accept]");

    let pendingAction = null;
    let restoreFocusEl = null;

    const closeModal = () => {
        backdrop.classList.remove("is-visible");
        document.body.classList.remove("custom-confirm-open");
        pendingAction = null;
        window.setTimeout(() => {
            backdrop.setAttribute("hidden", "hidden");
            restoreFocusEl?.focus?.();
            restoreFocusEl = null;
        }, 120);
    };

    const openModal = ({ message, destructive, onConfirm }) => {
        pendingAction = onConfirm;
        restoreFocusEl = document.activeElement instanceof HTMLElement ? document.activeElement : null;
        messageEl.textContent = message || "Do you want to continue?";
        if (destructive) {
            acceptBtn.classList.remove("btn-primary");
            acceptBtn.classList.add("btn-danger");
            acceptBtn.textContent = "Delete";
        } else {
            acceptBtn.classList.remove("btn-danger");
            acceptBtn.classList.add("btn-primary");
            acceptBtn.textContent = "Confirm";
        }
        backdrop.removeAttribute("hidden");
        document.body.classList.add("custom-confirm-open");
        window.requestAnimationFrame(() => {
            backdrop.classList.add("is-visible");
            cancelBtn.focus();
        });
    };

    acceptBtn.addEventListener("click", () => {
        const action = pendingAction;
        closeModal();
        action?.();
    });

    cancelBtn.addEventListener("click", closeModal);

    backdrop.addEventListener("click", (event) => {
        if (event.target === backdrop) {
            closeModal();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && backdrop.classList.contains("is-visible")) {
            closeModal();
        }
    });

    document.body.addEventListener("htmx:confirm", (event) => {
        const detail = event.detail || {};
        if (!detail.question || typeof detail.issueRequest !== "function") {
            return;
        }
        event.preventDefault();
        const sourceEl = detail.elt instanceof Element ? detail.elt : null;
        const destructive = Boolean(sourceEl?.matches("[hx-delete], .btn-danger, [data-confirm-destructive='true']"));
        openModal({
            message: detail.question,
            destructive,
            onConfirm: () => detail.issueRequest(true),
        });
    });
}

document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initSearchClear();
    initBulkSelection();
    initTagSuggestions();
    initTagChoices();
    initTagRenameControls();
    initTemporaryLinkControls();
    initFilterResetBehavior();
    initCustomHtmxConfirm();
});

document.body.addEventListener("htmx:afterSwap", () => {
    initBulkSelection();
    initTagSuggestions();
    initTagChoices();
    initTagRenameControls();
    initTemporaryLinkControls();
    initFilterResetBehavior();
    initCustomHtmxConfirm();
});
