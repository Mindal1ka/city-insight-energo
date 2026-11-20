// Клієнтський кеш відповідей API (stale-while-revalidate) — прозорий для сторінок.
// Працює всередині обгортки window.fetch (api.ts): GET /api/* повертаються з пам'яті миттєво,
// а застарілі — оновлюються у фоні. Однакові одночасні запити об'єднуються в один.
// Ключ — «скоуп» користувача (роль/об'єкт/управління/ПІБ) + URL: зміна користувача очищає все.
// Частина зведених даних зберігається в sessionStorage вкладки, щоб перезавантаження малювало одразу.
// Нічого з цього модуля не потрапляє в localStorage; вихід очищає пам'ять і sessionStorage.

export interface Snap {
	status: number;
	ctype: string;
	etag: string | null;
	body: string;
	at: number; // коли отримано/підтверджено (ms)
}

const MIN = 60_000;

/** TTL «свіжості» за шляхом: у межах TTL — без мережі; далі — з кешу + оновлення у фоні */
const TTL: [RegExp, number][] = [
	[/^\/api\/(live|energy-now|sites|forecast|outages)\b/, 1 * MIN],
	[/^\/api\/(ses|insight|independence|blackout|generators|report|appeals|freshness|uploads)\b/, 5 * MIN],
	[/^\/api\/(departments|budget-real|spending|trend|zones|network)\b/, 5 * MIN],
	[/^\/api\/(map|buildings|defects|summary|solar)\b/, 30 * MIN]
];

/** «Живі» дані: періодично оновлюємо, поки застосунок відкритий */
export const LIVE_RE = /^\/api\/(live|energy-now|sites|forecast)\b/;

export function ttlFor(path: string): number {
	for (const [re, t] of TTL) if (re.test(path)) return t;
	return 1 * MIN;
}

/** Скільки ще можна показувати застаріле, поки оновлюємо у фоні; далі — чекаємо мережу */
export function maxStaleFor(path: string): number {
	return LIVE_RE.test(path) ? 10 * MIN : 12 * 60 * MIN;
}

/** Що не кешуємо зовсім */
export function cacheable(path: string): boolean {
	return path.startsWith('/api/') && !path.startsWith('/api/auth/') && !path.endsWith('.csv');
}

/** Що переживає перезавантаження вкладки (sessionStorage): зведені набори, не детальні по об'єкту */
const PERSIST_RE = /^\/api\/(summary|departments|ses|map|live|budget-real|report|trend|zones|spending|freshness|blackout|generators|independence)(\?|$)/;
const PERSIST_KEY = 'energo.cache.v1';
const PERSIST_MAX = 3_500_000; // символів, з запасом до ліміту sessionStorage (~5 МБ)

let scope = '';
const mem = new Map<string, Snap>();
const inflight = new Map<string, Promise<Snap>>();
const listeners = new Set<(url: string, snap: Snap) => void>();

const k = (url: string) => scope + '\u0001' + url;

export function getScope(): string {
	return scope;
}

/** Встановлює власника кешу; інший користувач/роль → кеш очищається (нічого чужого не показуємо) */
export function setScope(s: string): void {
	if (s === scope) return;
	const had = scope !== '';
	scope = s;
	mem.clear();
	inflight.clear();
	if (had || !s) dropPersisted();
	else hydrate();
}

export function get(url: string): Snap | undefined {
	return scope ? mem.get(k(url)) : undefined;
}

export function age(url: string): number {
	const s = get(url);
	return s ? Date.now() - s.at : Infinity;
}

/** Зберігає відповідь; повертає true, якщо дані змінилися (для підписників) */
export function put(url: string, snap: Snap): boolean {
	if (!scope) return false;
	const prev = mem.get(k(url));
	const changed = !prev || prev.body !== snap.body;
	mem.set(k(url), changed ? snap : { ...prev, at: snap.at, etag: snap.etag ?? prev.etag });
	if (changed) {
		for (const fn of listeners) fn(url, snap);
		persistSoon();
	}
	return changed;
}

/** Підтвердження без змін (304) — лише оновлюємо час */
export function touch(url: string): void {
	const s = mem.get(k(url));
	if (s) s.at = Date.now();
}

/** Об'єднання однакових одночасних запитів */
export function dedupe(url: string, run: () => Promise<Snap>): Promise<Snap> {
	const key = k(url);
	const p = inflight.get(key);
	if (p) return p;
	const q = run().finally(() => {
		if (inflight.get(key) === q) inflight.delete(key);
	});
	inflight.set(key, q);
	return q;
}

/** Недійсність після запису: усе (запис може вплинути на зведення) або за префіксом */
export function invalidate(prefix?: string): void {
	for (const key of [...mem.keys()]) {
		const url = key.slice(key.indexOf('\u0001') + 1);
		if (!prefix || url.startsWith(prefix)) mem.delete(key);
	}
	persistSoon();
}

/** Повне очищення (вихід): пам'ять + sessionStorage */
export function clearAll(): void {
	scope = '';
	mem.clear();
	inflight.clear();
	dropPersisted();
}

/** Підписка на зміну даних (сторінка може оновлюватися на місці): повертає відписку */
export function onData(fn: (url: string, snap: Snap) => void): () => void {
	listeners.add(fn);
	return () => listeners.delete(fn);
}

/** Час останнього оновлення будь-якого з URL (для індикатора свіжості) */
export function lastUpdated(prefix = '/api/'): number | null {
	let best: number | null = null;
	for (const [key, s] of mem) {
		const url = key.slice(key.indexOf('\u0001') + 1);
		if (url.startsWith(prefix) && (best === null || s.at > best)) best = s.at;
	}
	return best;
}

export function toResponse(s: Snap, hit: 'HIT' | 'STALE' | 'NET'): Response {
	const headers = new Headers({ 'Content-Type': s.ctype, 'X-Client-Cache': hit });
	if (s.etag) headers.set('ETag', s.etag);
	return new Response(s.status === 204 || s.status === 304 ? null : s.body, { status: s.status, headers });
}

// ---------- sessionStorage ----------

let persistTimer: ReturnType<typeof setTimeout> | null = null;

function persistSoon(): void {
	if (typeof window === 'undefined' || persistTimer) return;
	persistTimer = setTimeout(() => {
		persistTimer = null;
		persist();
	}, 1500);
}

function persist(): void {
	if (!scope) return;
	const out: Record<string, Snap> = {};
	let size = 0;
	for (const [key, s] of mem) {
		const url = key.slice(key.indexOf('\u0001') + 1);
		if (s.status !== 200 || !PERSIST_RE.test(url)) continue;
		if (size + s.body.length > PERSIST_MAX) continue;
		size += s.body.length;
		out[url] = s;
	}
	try {
		sessionStorage.setItem(PERSIST_KEY, JSON.stringify({ scope, entries: out }));
	} catch {
		/* переповнено/приватний режим — просто без збереження */
	}
}

function hydrate(): void {
	try {
		const raw = sessionStorage.getItem(PERSIST_KEY);
		if (!raw) return;
		const data = JSON.parse(raw) as { scope: string; entries: Record<string, Snap> };
		if (data.scope !== scope) {
			sessionStorage.removeItem(PERSIST_KEY);
			return;
		}
		for (const [url, s] of Object.entries(data.entries)) {
			// після перезавантаження: показуємо одразу, але вважаємо застарілим → оновлення у фоні
			mem.set(k(url), { ...s, at: Math.min(s.at, Date.now() - ttlFor(url.split('?')[0]) - 1) });
		}
	} catch {
		/* пошкоджено — ігноруємо */
	}
}

function dropPersisted(): void {
	if (persistTimer) {
		clearTimeout(persistTimer);
		persistTimer = null;
	}
	try {
		sessionStorage.removeItem(PERSIST_KEY);
	} catch {
		/* ігноруємо */
	}
}
