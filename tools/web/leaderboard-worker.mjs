import { DurableObject } from "cloudflare:workers";

const PAGE_SIZE = 50;
const HEADERS = { "Cache-Control": "no-store" };
const API_PATH = "/api/leaderboard";

function json(data, status = 200, headers = {}) {
    return Response.json(data, { status, headers: { ...HEADERS, ...headers } });
}

function validResult(entry) {
    return entry && typeof entry.token === "string" &&
        /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(entry.token) &&
        typeof entry.name === "string" && entry.name.length > 0 && entry.name.length <= 24 &&
        entry.name === entry.name.trim() && !/[\p{Cc}\p{Cf}]/u.test(entry.name) &&
        Number.isSafeInteger(entry.score) && entry.score >= 0 &&
        Number.isSafeInteger(entry.rooms) && entry.rooms >= 0;
}

export default {
    fetch(request, env) {
        if (new URL(request.url).pathname === API_PATH) {
            return env.LEADERBOARD.getByName("main").fetch(request);
        }
        return env.ASSETS.fetch(request);
    },
};

export class Leaderboard extends DurableObject {
    constructor(ctx, env) {
        super(ctx, env);
        this.sql = ctx.storage.sql;
        this.sql.exec(`
            CREATE TABLE IF NOT EXISTS players (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                score INTEGER NOT NULL,
                rooms INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS leaderboard_order
                ON players (score DESC, rooms DESC, name COLLATE NOCASE, id);
        `);
    }

    async fetch(request) {
        if (request.method === "GET") {
            const offset = Number(new URL(request.url).searchParams.get("offset") ?? "0");
            if (!Number.isSafeInteger(offset) || offset < 0) {
                return json({ error: "Invalid offset." }, 400);
            }
            const players = this.sql.exec(`
                SELECT name, score, rooms FROM players
                ORDER BY score DESC, rooms DESC, name COLLATE NOCASE, id
                LIMIT ? OFFSET ?
            `, PAGE_SIZE + 1, offset).toArray();
            return json({
                players: players.slice(0, PAGE_SIZE),
                next: players.length > PAGE_SIZE ? offset + PAGE_SIZE : null,
            });
        }
        if (request.method !== "POST") {
            return json({ error: "Method not allowed." }, 405, { Allow: "GET, POST" });
        }
        if (request.headers.get("Content-Type")?.split(";")[0] !== "application/json") {
            return json({ error: "Send a JSON score." }, 415);
        }
        let entry;
        try {
            if (Number(request.headers.get("Content-Length")) > 1024) {
                return json({ error: "Score is too large." }, 413);
            }
            const body = await request.text();
            if (body.length > 1024) return json({ error: "Score is too large." }, 413);
            entry = JSON.parse(body);
        } catch {
            return json({ error: "Invalid score." }, 400);
        }
        if (!validResult(entry)) return json({ error: "Invalid score." }, 400);
        const { token, name, score, rooms } = entry;
        const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(token));
        const id = Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, "0")).join("");
        this.sql.exec(`
            INSERT INTO players (id, name, score, rooms) VALUES (?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET score = excluded.score, rooms = excluded.rooms
            WHERE excluded.score > players.score
               OR (excluded.score = players.score AND excluded.rooms > players.rooms)
        `, id, name, score, rooms);
        return json({ saved: true });
    }
}
