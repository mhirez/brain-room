(() => {
    const title = document.querySelector("#game-title");
    const canvas = document.querySelector("#canvas");
    const form = document.querySelector("#start-form");
    const input = document.querySelector("#player-name");
    const rows = document.querySelector("#leaderboard-rows");
    const status = document.querySelector("#leaderboard-status");
    const more = document.querySelector("#leaderboard-more");
    const api = new URL("api/leaderboard", location.href);
    const playerPrefix = "brain-room.player.";
    const lastNameKey = "brain-room.last-player";
    const memory = new Map();
    const inFlight = new Set();
    const number = new Intl.NumberFormat();
    let activeKey;
    let start = "";
    let daily = false;
    let nextPage = null;
    let requestVersion = 0;
    let syncTimer;

    function load(key) {
        if (memory.has(key)) return memory.get(key);
        try {
            const stored = localStorage.getItem(key);
            if (stored !== null) return JSON.parse(stored);
        } catch {
        }
    }

    function save(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
            memory.delete(key);
        } catch {
            memory.set(key, value);
        }
    }

    function localPlayers() {
        const keys = new Set(memory.keys());
        try {
            for (let index = 0; index < localStorage.length; index++) {
                keys.add(localStorage.key(index));
            }
        } catch {
        }
        return [...keys]
            .filter(key => key?.startsWith(playerPrefix))
            .map(load)
            .filter(player => player?.token && typeof player.name === "string");
    }

    function isBetter(score, rooms, player) {
        return score > player.score || (score === player.score && rooms > player.rooms);
    }

    function addRows(players) {
        for (const player of players) {
            const row = rows.insertRow();
            for (const value of [player.name, number.format(player.score), number.format(player.rooms)]) {
                row.insertCell().textContent = value;
            }
        }
    }

    async function showScores(offset = 0) {
        const version = ++requestVersion;
        more.disabled = true;
        if (offset === 0) {
            rows.replaceChildren();
            more.hidden = true;
            status.textContent = "Loading scores…";
        }
        try {
            const url = new URL(api);
            url.searchParams.set("offset", String(offset));
            const response = await fetch(url, { signal: AbortSignal.timeout(5000) });
            if (!response.ok) throw new Error("Leaderboard unavailable");
            const board = await response.json();
            if (version !== requestVersion) return;
            addRows(board.players);
            nextPage = board.next;
            status.textContent = rows.rows.length ? "" : "No players yet.";
            more.hidden = nextPage === null;
        } catch {
            if (version !== requestVersion) return;
            if (offset === 0) {
                addRows(localPlayers().sort((a, b) => b.score - a.score || b.rooms - a.rooms || a.name.localeCompare(b.name)));
                status.textContent = "Shared scores unavailable. Showing scores saved in this browser.";
            } else {
                status.textContent = "Could not load more scores. Try again.";
            }
        } finally {
            if (version === requestVersion) more.disabled = false;
        }
    }

    function queueSync() {
        clearTimeout(syncTimer);
        syncTimer = setTimeout(sync, 350);
    }

    async function push(player) {
        inFlight.add(player.token);
        const key = playerPrefix + player.name.toLowerCase();
        try {
            const { token, name, score, rooms } = player;
            const response = await fetch(api, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token, name, score, rooms }),
                signal: AbortSignal.timeout(10000),
                keepalive: true,
            });
            if (!response.ok) return false;
            const current = load(key);
            if (current && isBetter(current.score, current.rooms, player)) {
                queueSync();
            } else if (current) {
                save(key, { ...current, pending: false });
            }
            return true;
        } catch {
            return false;
        } finally {
            inFlight.delete(player.token);
        }
    }

    async function sync() {
        const pending = localPlayers().filter(player => player.pending && !inFlight.has(player.token));
        const results = await Promise.all(pending.map(push));
        if (!title.hidden && results.some(Boolean)) showScores();
    }

    input.addEventListener("input", () => input.setCustomValidity(""));
    form.addEventListener("submit", event => {
        event.preventDefault();
        const name = input.value.trim().replace(/\s+/gu, " ");
        if (!name || name.length > 24 || /[\p{Cc}\p{Cf}]/u.test(name)) {
            input.setCustomValidity("Enter a nickname of 1 to 24 characters.");
            input.reportValidity();
            return;
        }
        if (start) return;
        activeKey = playerPrefix + name.toLowerCase();
        const saved = load(activeKey);
        if (!saved) save(activeKey, { token: crypto.randomUUID(), name, score: 0, rooms: 0, pending: true });
        save(lastNameKey, saved?.name ?? name);
        start = daily ? "daily" : "regular";
        daily = false;
        sync();
    });
    more.addEventListener("click", () => {
        if (nextPage !== null) showScores(nextPage);
    });

    for (const eventType of ["keydown", "keypress", "keyup"]) {
        window.addEventListener(eventType, event => {
            if (!title.hidden && title.contains(event.target)) event.stopImmediatePropagation();
        }, true);
    }
    window.addEventListener("online", sync);
    window.addEventListener("pagehide", sync);

    window.brainRoomTitle = {
        show() {
            title.hidden = false;
            input.value = load(lastNameKey) ?? "";
            input.setCustomValidity("");
            (input.value ? canvas : input).focus();
            showScores();
            sync();
        },
        hide() {
            title.hidden = true;
            canvas.focus();
        },
        requestStart(isDaily) {
            daily = isDaily;
            form.requestSubmit();
            daily = false;
        },
        takeStart() {
            const request = start;
            start = "";
            return request;
        },
        record(score, rooms) {
            const player = load(activeKey);
            if (!player || !isBetter(score, rooms, player)) return;
            save(activeKey, { ...player, score, rooms, pending: true });
            queueSync();
        },
    };
})();
