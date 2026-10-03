(() => {
    "use strict";

    /* =========================================================
       BASIC HELPERS
    ========================================================= */

    const $ = (selector, root = document) => root.querySelector(selector);
    const $$ = (selector, root = document) => [
        ...root.querySelectorAll(selector)
    ];

    const getJSON = async (url) => {
        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`Request failed: ${response.status}`);
        }

        return response.json();
    };

    const escapeHtml = (value) => {
        return String(value ?? "").replace(/[&<>"']/g, (char) => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#039;"
        }[char]));
    };

    /* =========================================================
       LOCAL STORAGE
    ========================================================= */

    function getStore(key) {
        try {
            const value = localStorage.getItem(key);

            if (!value) {
                return [];
            }

            const parsed = JSON.parse(value);

            return Array.isArray(parsed) ? parsed : [];
        } catch (error) {
            console.warn(`Could not read localStorage key: ${key}`, error);
            return [];
        }
    }

    function setStore(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (error) {
            console.warn(`Could not save localStorage key: ${key}`, error);
        }
    }

    function favoriteIds() {
        return getStore("uniscout_favorites")
            .map(Number)
            .filter(Number.isFinite);
    }

    function compareIds() {
        return getStore("uniscout_compare")
            .map(Number)
            .filter(Number.isFinite);
    }

    /* =========================================================
       COMPARE
    ========================================================= */

    function updateCompareCount() {
        const count = compareIds().length;

        $$(".count").forEach((element) => {
            element.textContent = count;
        });
    }

    function toggleCompare(id) {
        id = Number(id);

        if (!Number.isFinite(id)) {
            return;
        }

        let ids = compareIds();

        if (ids.includes(id)) {
            ids = ids.filter((item) => item !== id);
        } else {
            if (ids.length >= 4) {
                alert("You can compare up to 4 universities.");
                return;
            }

            ids.push(id);
        }

        setStore("uniscout_compare", ids);

        updateCompareCount();
        renderCompareButtons();

        /*
         * If we're already on the comparison page,
         * immediately reload the comparison with the
         * updated university IDs.
         */
        if (window.location.pathname === "/compare") {
            navigateToCompare();
        }
    }

    function navigateToCompare() {
        const ids = compareIds();

        if (ids.length === 0) {
            window.location.href = "/compare";
            return;
        }

        window.location.href = "/compare?ids=" + ids.join(",");
    }

    /*
     * IMPORTANT FIX:
     *
     * If user clicks:
     *
     * Compare 4
     *
     * the navbar goes to /compare.
     *
     * The old code did nothing with localStorage.
     *
     * This automatically converts:
     *
     * /compare
     *
     * into:
     *
     * /compare?ids=1,2,3,4
     */
    function initializeComparePage() {
        if (window.location.pathname !== "/compare") {
            return;
        }

        const urlParams = new URLSearchParams(window.location.search);
        const urlIds = urlParams.get("ids");

        const storedIds = compareIds();

        if (!urlIds && storedIds.length > 0) {
            window.location.replace(
                "/compare?ids=" + storedIds.join(",")
            );

            return;
        }
    }

    function removeFromCompare(id) {
        id = Number(id);

        let ids = compareIds();

        ids = ids.filter((item) => item !== id);

        setStore("uniscout_compare", ids);

        updateCompareCount();

        /*
         * Reload comparison page with remaining IDs.
         */
        if (window.location.pathname === "/compare") {
            if (ids.length === 0) {
                window.location.href = "/compare";
            } else {
                window.location.href =
                    "/compare?ids=" + ids.join(",");
            }
        }
    }

    function clearComparison() {
        setStore("uniscout_compare", []);

        updateCompareCount();

        if (window.location.pathname === "/compare") {
            window.location.href = "/compare";
        }
    }

    function renderCompareButtons() {
        const ids = compareIds();

        $$(".compare-btn").forEach((button) => {
            const id = Number(button.dataset.id);

            const active = ids.includes(id);

            button.textContent = active
                ? "✓ Comparing"
                : "Compare";

            button.classList.toggle("active", active);

            button.setAttribute(
                "aria-pressed",
                active ? "true" : "false"
            );
        });
    }

    /* =========================================================
       FAVORITES
    ========================================================= */

    function toggleFavorite(id) {
        id = Number(id);

        if (!Number.isFinite(id)) {
            return;
        }

        let ids = favoriteIds();

        if (ids.includes(id)) {
            ids = ids.filter((item) => item !== id);
        } else {
            ids.push(id);
        }

        setStore("uniscout_favorites", ids);

        renderFavoriteButtons();

        /*
         * Refresh favorites page after removing a favorite.
         */
        if (window.location.pathname === "/favorites") {
            renderFavorites();
        }
    }

    function renderFavoriteButtons() {
        const ids = favoriteIds();

        $$(".favorite-btn").forEach((button) => {
            const id = Number(button.dataset.id);

            const active = ids.includes(id);

            const isProfileButton =
                Boolean(button.closest(".profile-actions"));

            button.textContent = active
                ? "♥"
                : (isProfileButton ? "♡ Save" : "♡");

            button.classList.toggle("active", active);

            button.setAttribute(
                "aria-pressed",
                active ? "true" : "false"
            );
        });
    }

    /* =========================================================
       GLOBAL CLICK HANDLER
    ========================================================= */

    document.addEventListener("click", (event) => {

        /* Favorite */
        const favoriteButton =
            event.target.closest(".favorite-btn");

        if (favoriteButton) {
            event.preventDefault();
            event.stopPropagation();

            toggleFavorite(favoriteButton.dataset.id);

            return;
        }

        /* Compare */
        const compareButton =
            event.target.closest(".compare-btn");

        if (compareButton) {
            event.preventDefault();
            event.stopPropagation();

            toggleCompare(compareButton.dataset.id);

            return;
        }

        /* Remove comparison */
        const removeButton =
            event.target.closest(".remove-compare");

        if (removeButton) {
            event.preventDefault();

            removeFromCompare(
                removeButton.dataset.id
            );

            return;
        }

        /* Clear comparison */
        if (event.target.closest("#clearCompare")) {
            event.preventDefault();

            clearComparison();

            return;
        }
    });

    /* =========================================================
       SEARCH AUTOCOMPLETE
    ========================================================= */

    function initSuggestions() {
        $$(".search-wrap").forEach((wrapper) => {

            const input = wrapper.querySelector("input");
            const box = wrapper.querySelector(".suggestions");

            if (!input || !box) {
                return;
            }

            let timer = null;

            input.addEventListener("input", () => {

                clearTimeout(timer);

                const query = input.value.trim();

                if (query.length < 2) {
                    box.innerHTML = "";
                    box.classList.remove("show");
                    return;
                }

                box.innerHTML =
                    '<div class="suggest-loading">Searching…</div>';

                box.classList.add("show");

                timer = setTimeout(async () => {

                    try {

                        const data = await getJSON(
                            "/api/suggestions?q=" +
                            encodeURIComponent(query)
                        );

                        if (!data.length) {

                            box.innerHTML =
                                '<div class="suggest-loading">No suggestions</div>';

                            return;
                        }

                        box.innerHTML = data.map((item) => {

                            let icon = "🏫";

                            if (item.type === "city") {
                                icon = "📍";
                            }

                            if (item.type === "country") {
                                icon = "🌎";
                            }

                            if (item.type === "major") {
                                icon = "🎓";
                            }

                            return `
                                <button
                                    type="button"
                                    class="suggestion"
                                    data-value="${escapeHtml(item.value)}"
                                >
                                    <span class="suggest-icon">
                                        ${icon}
                                    </span>

                                    <span>
                                        <strong>
                                            ${escapeHtml(item.label)}
                                        </strong>

                                        <small>
                                            ${escapeHtml(
                                                item.sub || item.type
                                            )}
                                        </small>
                                    </span>
                                </button>
                            `;

                        }).join("");

                    } catch (error) {

                        console.error(error);

                        box.innerHTML =
                            '<div class="suggest-loading">Suggestions unavailable</div>';
                    }

                }, 250);
            });

            box.addEventListener("click", (event) => {

                const suggestion =
                    event.target.closest(".suggestion");

                if (!suggestion) {
                    return;
                }

                event.preventDefault();
                event.stopPropagation();

                /*
                 * Populate the search box only.
                 *
                 * DO NOT submit the form.
                 */
                input.value = suggestion.dataset.value;

                box.classList.remove("show");

                input.focus();
            });

            document.addEventListener("click", (event) => {

                if (!wrapper.contains(event.target)) {
                    box.classList.remove("show");
                }

            });
        });
    }

    /* =========================================================
       COUNTRY → CITY
    ========================================================= */

    function initializeCityFilter() {

        const country = $("#countryFilter");
        const city = $("#cityFilter");

        if (!country || !city) {
            return;
        }

        country.addEventListener("change", async () => {

            const selectedCountry =
                country.value.trim();

            city.innerHTML =
                '<option value="">Loading cities…</option>';

            try {

                const data = await getJSON(
                    "/api/cities?country=" +
                    encodeURIComponent(selectedCountry)
                );

                city.innerHTML =
                    '<option value="">Any city</option>' +
                    data.map((value) => `
                        <option value="${escapeHtml(value)}">
                            ${escapeHtml(value)}
                        </option>
                    `).join("");

            } catch (error) {

                console.error(error);

                city.innerHTML =
                    '<option value="">Unable to load cities</option>';
            }
        });
    }

    /* =========================================================
       FAVORITES PAGE
    ========================================================= */

    async function renderFavorites() {

        const grid = $("#favoritesGrid");
        const empty = $("#favoritesEmpty");

        if (!grid) {
            return;
        }

        const ids = favoriteIds();

        if (!ids.length) {

            grid.innerHTML = "";

            if (empty) {
                empty.style.display = "block";
            }

            return;
        }

        if (empty) {
            empty.style.display = "none";
        }

        grid.innerHTML =
            '<div class="loading">Loading saved universities…</div>';

        try {

            const universities = await Promise.all(
                ids.map((id) =>
                    getJSON("/api/university/" + id)
                        .catch(() => null)
                )
            );

            const valid =
                universities.filter(Boolean);

            if (!valid.length) {

                grid.innerHTML = "";

                if (empty) {
                    empty.style.display = "block";
                }

                return;
            }

            grid.innerHTML =
                valid.map((university) =>
                    favoriteCardHtml(university)
                ).join("");

            renderFavoriteButtons();
            renderCompareButtons();

        } catch (error) {

            console.error(error);

            grid.innerHTML =
                '<div class="empty"><h2>Unable to load favorites</h2></div>';
        }
    }

    function favoriteCardHtml(university) {

        const tuition =
            university.tuition_min &&
            university.tuition_max

                ? `$${Number(
                    university.tuition_min
                ).toLocaleString()}–$${Number(
                    university.tuition_max
                ).toLocaleString()}`

                : "Not available";

        const majors =
            Array.isArray(university.majors_list)
                ? university.majors_list
                : [];

        return `
            <article class="uni-card">

                <div class="card-top">

                    <div class="logo placeholder">
                        🎓
                    </div>

                    <button
                        class="icon-btn favorite-btn active"
                        data-id="${university.id}"
                        aria-label="Remove from favorites"
                    >
                        ♥
                    </button>

                </div>

                <div class="rank">
                    ${
                        university.ranking
                            ? "#" + university.ranking + " ranking"
                            : "Ranking not available"
                    }
                </div>

                <h3>
                    ${escapeHtml(university.name)}
                </h3>

                <p class="location">
                    📍
                    ${escapeHtml(
                        university.city ||
                        "City not available"
                    )},
                    ${escapeHtml(
                        university.country ||
                        "Country not available"
                    )}
                </p>

                <div class="tags">

                    ${majors.slice(0, 2).map((major) => `
                        <span>
                            ${escapeHtml(major)}
                        </span>
                    `).join("")}

                </div>

                <div class="card-info">
                    <span>Tuition</span>
                    <strong>${tuition}</strong>
                </div>

                <div class="card-actions">

                    <button
                        class="btn ghost compare-btn"
                        data-id="${university.id}"
                    >
                        Compare
                    </button>

                    <a
                        class="btn primary"
                        href="/university/${university.id}"
                    >
                        View →
                    </a>

                </div>

            </article>
        `;
    }

    /* =========================================================
       AI CHAT
    ========================================================= */

    const chatForm = $("#chatForm");
    const chat = $("#chat");
    const chatInput = $("#chatInput");

    function addMessage(text, type) {

        if (!chat) {
            return;
        }

        const message = document.createElement("div");

        message.className =
            "message " + type;

        message.textContent = text;

        chat.appendChild(message);

        chat.scrollTop =
            chat.scrollHeight;
    }

    async function sendChat() {

        if (!chatInput || !chat) {
            return;
        }

        const message =
            chatInput.value.trim();

        if (!message) {
            return;
        }

        addMessage(message, "user");

        chatInput.value = "";

        const loading =
            document.createElement("div");

        loading.className =
            "message ai loading-msg";

        loading.textContent =
            "Thinking…";

        chat.appendChild(loading);

        chat.scrollTop =
            chat.scrollHeight;

        try {

            const response =
                await fetch(
                    "/api/ai/chat",
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body: JSON.stringify({
                            message,

                            context: {
                                university_ids:
                                    compareIds()
                            }
                        })
                    }
                );

            const data =
                await response.json();

            loading.remove();

            if (!response.ok) {
                addMessage(
                    data.error ||
                    "UniScout AI is currently unavailable.",
                    "ai"
                );

                return;
            }

            addMessage(
                data.response ||
                "No response received.",
                "ai"
            );

        } catch (error) {

            console.error(error);

            loading.remove();

            addMessage(
                "UniScout AI is currently unavailable. Make sure Ollama is running.",
                "ai"
            );
        }
    }

    /* =========================================================
       CHAT EVENTS
    ========================================================= */

    if (chatForm) {

        chatForm.addEventListener(
            "submit",
            (event) => {
                event.preventDefault();
                sendChat();
            }
        );
    }

    if (chatInput) {

        chatInput.addEventListener(
            "keydown",
            (event) => {

                if (
                    event.key === "Enter" &&
                    !event.shiftKey
                ) {

                    event.preventDefault();

                    sendChat();
                }
            }
        );
    }

    $$(".chat-suggestions button")
        .forEach((button) => {

            button.addEventListener(
                "click",
                () => {

                    if (!chatInput) {
                        return;
                    }

                    chatInput.value =
                        button.textContent.trim();

                    chatInput.focus();
                }
            );

        });

    const clearChat =
        $("#clearChat");

    if (clearChat) {

        clearChat.addEventListener(
            "click",
            () => {

                if (!chat) {
                    return;
                }

                chat.innerHTML = `
                    <div class="message ai">
                        Chat cleared. What would you like to explore?
                    </div>
                `;
            }
        );
    }

    const openAi =
        $("#openAi");

    if (openAi) {

        openAi.addEventListener(
            "click",
            () => {

                const ai =
                    $("#ai");

                if (ai) {
                    ai.scrollIntoView({
                        behavior: "smooth"
                    });
                }
            }
        );
    }

    /* =========================================================
       MOBILE NAVIGATION
    ========================================================= */

    const navToggle =
        $(".nav-toggle");

    if (navToggle) {

        navToggle.addEventListener(
            "click",
            () => {

                const nav =
                    $(".nav nav");

                if (nav) {
                    nav.classList.toggle(
                        "mobile-open"
                    );
                }
            }
        );
    }

    /* =========================================================
       INITIALIZE
    ========================================================= */

    initializeComparePage();

    updateCompareCount();
    renderFavoriteButtons();
    renderCompareButtons();

    initSuggestions();
    initializeCityFilter();
    renderFavorites();

})();