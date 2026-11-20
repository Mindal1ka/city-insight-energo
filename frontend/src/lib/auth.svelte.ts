// Вхід і поточний користувач. Без входу застосунок недоступний (лише /login).
// Сесія: токен бекенду (HMAC, 12 год) і користувач — у localStorage, тож вхід переживає перезавантаження
// і спільний для всіх вкладок. Термін перевіряється локально (exp у токені); коли лишилося <20% —
// ковзне продовження POST /api/auth/refresh (не довше 7 діб від входу). Вихід в одній вкладці —
// вихід у всіх (подія storage) з очищенням кешу даних.
// Використання: import { auth, currentRole } from '#lib/auth.svelte.ts'; auth.user?.role

import { untrack } from 'svelte';
import { roleName, type RoleId, type Department } from './roles.ts';
import { clearAll as clearDataCache } from './store/cache.ts';

export interface User {
	full_name: string;
	position: string;
	role: RoleId;
	role_name: string;
	building_id: number | null;
	department: Department | null;
	token: string | null;
}

export interface LoginInput {
	login: string;
	password: string;
}

const KEY = 'energo.user';

function normalize(u: Record<string, unknown>, token: string | null): User | null {
	if (typeof u?.full_name !== 'string') return null;
	const role = (typeof u.role === 'string' ? u.role : 'energy_manager') as RoleId;
	return {
		full_name: u.full_name,
		position: typeof u.position === 'string' ? u.position : '',
		role,
		role_name: typeof u.role_name === 'string' && u.role_name ? u.role_name : roleName(role),
		building_id: u.building_id === null || u.building_id === undefined || u.building_id === '' ? null : Number(u.building_id),
		department: (u.department as Department) ?? null,
		token
	};
}

const TOKEN_TTL_MS = 12 * 3600_000; // як TOKEN_TTL на бекенді
const REFRESH_AT = 0.2; // продовжуємо, коли лишилося <20% терміну

/** exp (ms) із корисного навантаження токена; підпис перевіряє лише бекенд */
export function tokenExp(token: string | null | undefined): number | null {
	if (!token) return null;
	try {
		const b = token.split('.')[0].replace(/-/g, '+').replace(/_/g, '/');
		const json = new TextDecoder().decode(Uint8Array.from(atob(b + '='.repeat((4 - (b.length % 4)) % 4)), (c) => c.charCodeAt(0)));
		const exp = Number(JSON.parse(json).exp);
		return Number.isFinite(exp) ? exp * 1000 : null;
	} catch {
		return null;
	}
}

function parse(raw: string | null): User | null {
	if (!raw) return null;
	try {
		const u = JSON.parse(raw);
		// Старий формат без токена (тестовий вхід) — більше не дійсний
		if (!u?.token) return null;
		const exp = tokenExp(u.token);
		if (exp !== null && exp <= Date.now()) return null; // прострочений — як без входу
		return normalize(u, u.token);
	} catch {
		return null;
	}
}

function read(): User | null {
	try {
		const u = parse(localStorage.getItem(KEY));
		if (u) return u;
		localStorage.removeItem(KEY);
		// перехід зі старої схеми (sessionStorage вкладки)
		const old = parse(sessionStorage.getItem(KEY));
		sessionStorage.removeItem(KEY);
		if (old) localStorage.setItem(KEY, JSON.stringify(old));
		return old;
	} catch {
		/* сховище недоступне — вважаємо, що входу немає */
	}
	return null;
}

export const auth = $state<{ user: User | null }>({ user: read() });

/** Роль поточного користувача; без входу — 'public' (лише службове значення) */
export function currentRole(): RoleId {
	return auth.user?.role ?? 'public';
}

/** Токен для заголовка Authorization (або null без входу) */
/** Токен для запиту. untrack: ефект сторінки, що робить запит, не повинен залежати від auth.user,
 *  інакше оновлення профілю (verifySession) перезапускає завантаження — дубль кожного API-запиту. */
export function authToken(): string | null {
	return untrack(() => auth.user?.token ?? null);
}

function save(user: User): void {
	const prev = auth.user;
	// інша людина/роль — кеш даних попереднього користувача не показуємо ні миті
	if (prev && (prev.role !== user.role || prev.building_id !== user.building_id || prev.department !== user.department || prev.full_name !== user.full_name)) {
		clearDataCache();
	}
	auth.user = user;
	try {
		localStorage.setItem(KEY, JSON.stringify(user));
	} catch {
		/* приватний режим: вхід діє до перезавантаження */
	}
}

export function logout(): void {
	auth.user = null;
	clearDataCache();
	try {
		localStorage.removeItem(KEY); // подія storage → вихід в інших вкладках
		sessionStorage.removeItem(KEY);
	} catch {
		/* ігноруємо */
	}
}

/** Тихе продовження сесії: true — отримано новий токен. Паралельні виклики об'єднуються. */
let refreshing: Promise<boolean> | null = null;
export function refreshSession(): Promise<boolean> {
	const token = authToken();
	if (!token) return Promise.resolve(false);
	refreshing ??= (async () => {
		try {
			// нативний шлях без кешу; /api/auth/* обгортка не кешує
			const res = await fetch('/api/auth/refresh', {
				method: 'POST',
				headers: { Accept: 'application/json', Authorization: `Bearer ${token}` }
			});
			if (!res.ok) return false;
			const body = (await res.json()) as { token: string; user: Record<string, unknown> };
			if (authToken() !== token) return true; // поки чекали, інша вкладка вже продовжила
			const u = normalize(body.user, body.token);
			if (!u) return false;
			save(u);
			return true;
		} catch {
			return false;
		} finally {
			setTimeout(() => (refreshing = null), 0);
		}
	})();
	return refreshing;
}

/** Продовжити, якщо лишилося <20% терміну (викликається таймером і при поверненні у вкладку) */
export async function maybeRefresh(): Promise<void> {
	const exp = tokenExp(authToken());
	if (exp === null) return;
	const left = exp - Date.now();
	if (left <= 0) {
		logout();
		return;
	}
	if (left < TOKEN_TTL_MS * REFRESH_AT) await refreshSession();
}

// Синхронізація між вкладками: вхід/продовження/вихід в одній — одразу в усіх
if (typeof window !== 'undefined') {
	window.addEventListener('storage', (e) => {
		if (e.key !== KEY && e.key !== null) return;
		const u = parse(e.newValue);
		if (!u) {
			if (auth.user) {
				auth.user = null;
				clearDataCache();
			}
			return;
		}
		if (!auth.user || auth.user.token !== u.token) {
			if (auth.user && (auth.user.role !== u.role || auth.user.building_id !== u.building_id || auth.user.full_name !== u.full_name)) {
				clearDataCache();
			}
			auth.user = u;
		}
	});
	setInterval(() => void maybeRefresh(), 5 * 60_000);
	document.addEventListener('visibilitychange', () => {
		if (!document.hidden) void maybeRefresh();
	});
}

export class LoginError extends Error {
	constructor(
		public status: number,
		message: string
	) {
		super(message);
	}
}

/** Бекенд ще без /api/auth/* (404 або index.html замість JSON) */
function missing(res: Response): boolean {
	return res.status === 404 || res.status === 405 || !(res.headers.get('content-type') ?? '').includes('json');
}

/** POST /api/auth/login → токен + користувач. Кидає LoginError з людським текстом. */
export async function login(input: LoginInput): Promise<User> {
	let res: Response;
	try {
		res = await fetch('/api/auth/login', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
			body: JSON.stringify({ login: input.login, password: input.password })
		});
	} catch {
		throw new LoginError(0, 'Сервер недоступний. Спробуйте ще раз за хвилину.');
	}

	if (!res.ok) {
		let detail = '';
		try {
			const body = await res.json();
			if (typeof body?.detail === 'string') detail = body.detail;
		} catch {
			/* не JSON */
		}
		if (res.status === 401 || res.status === 403) throw new LoginError(res.status, detail || 'Невірний логін або пароль');
		if (res.status === 429) throw new LoginError(429, detail || 'Забагато спроб. Зачекайте хвилину.');
		if (res.status === 422 && !detail) throw new LoginError(422, 'Введіть логін і пароль');
		throw new LoginError(res.status, detail || `Не вдалося увійти (помилка ${res.status})`);
	}
	const body = (await res.json()) as { token: string; user: Record<string, unknown> };
	const u = normalize(body.user, body.token);
	if (!u) throw new LoginError(500, 'Сервер повернув неочікувану відповідь');
	save(u);
	return u;
}

/** Перевіряє збережений токен (GET /api/auth/me); прострочений — вихід (шлюз у layout веде на /login) */
function sameUser(a: object | null | undefined, b: object | null | undefined): boolean {
	if (!a || !b) return a === b;
	const norm = (o: object) => JSON.stringify(Object.entries(o).filter(([, v]) => v !== undefined).sort(([x], [y]) => (x < y ? -1 : 1)));
	return norm(a) === norm(b);
}

export async function verifySession(): Promise<void> {
	const token = authToken();
	if (!token) return;
	try {
		const res = await fetch('/api/auth/me', { headers: { Accept: 'application/json', Authorization: `Bearer ${token}` } });
		if (res.status === 401) logout();
		else if (res.ok && !missing(res)) {
			const u = normalize(await res.json(), token);
			// Зберігаємо лише якщо щось змінилося: нова посилання на auth.user перезапускала б усі
			// ефекти сторінок, що читають токен, — і кожен API-запит при відкритті йшов двічі
			if (u && !sameUser(u, auth.user)) save(u);
		}
	} catch {
		/* сервер недоступний — лишаємо як є */
	}
}

/** Куди повернутися після входу: лише внутрішні сторінки (?next=/object/1) */
export function safeNext(url: { searchParams: { get(name: string): string | null } }): string {
	const n = url.searchParams.get('next');
	return n && n.startsWith('/') && !n.startsWith('//') && !n.startsWith('/login') ? n : '/';
}

/** «Прізвище Ім'я По батькові» → «Ім'я По батькові» для привітання */
export function greetingName(full: string): string {
	const parts = full.trim().split(/\s+/);
	return parts.length >= 2 ? parts.slice(1).join(' ') : full.trim();
}

/** Ініціали для аватарки */
export function initials(full: string): string {
	return full
		.trim()
		.split(/\s+/)
		.slice(0, 2)
		.map((p) => p[0]?.toUpperCase() ?? '')
		.join('');
}
