// Вхід і поточний користувач. Без входу застосунок працює в публічному режимі (роль public).
// Токен бекенду (HMAC) і користувач живуть лише в sessionStorage вкладки.
// Використання: import { auth, currentRole } from '#lib/auth.svelte.ts'; auth.user?.role

import { ROLES, roleName, type RoleId, type RoleInfo, type Department } from './roles.ts';

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
	full_name: string;
	position: string;
	role: RoleId;
	building_id?: number | null;
	department?: Department | null;
	password: string;
}

export const DEFAULT_POSITION = 'Головний фахівець з енергоменеджменту';

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

function read(): User | null {
	try {
		const raw = sessionStorage.getItem(KEY);
		if (!raw) return null;
		const u = JSON.parse(raw);
		// Старий формат без токена (тестовий вхід) — більше не дійсний
		if (!u?.token && !u?.mock) return null;
		return normalize(u, u.token ?? null);
	} catch {
		/* сховище недоступне — вважаємо, що входу немає */
	}
	return null;
}

export const auth = $state<{ user: User | null }>({ user: read() });

/** Роль поточного відвідувача; без входу — 'public' */
export function currentRole(): RoleId {
	return auth.user?.role ?? 'public';
}

/** Токен для заголовка Authorization (або null у публічному режимі) */
export function authToken(): string | null {
	return auth.user?.token ?? null;
}

function save(user: User, extra: Record<string, unknown> = {}): void {
	auth.user = user;
	try {
		sessionStorage.setItem(KEY, JSON.stringify({ ...user, ...extra }));
	} catch {
		/* приватний режим: вхід діє до перезавантаження */
	}
}

export function logout(): void {
	auth.user = null;
	try {
		sessionStorage.removeItem(KEY);
	} catch {
		/* ігноруємо */
	}
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

/** Список ролей для форми входу; поки бекенд не готовий — локальний запасний список */
export async function fetchRoles(): Promise<RoleInfo[]> {
	try {
		const res = await fetch('/api/auth/roles', { headers: { Accept: 'application/json' } });
		if (res.ok && !missing(res)) {
			const list = (await res.json()) as RoleInfo[];
			const nonPublic = list.filter((r) => r.id !== 'public');
			if (nonPublic.length) return nonPublic;
		}
	} catch {
		/* сервер недоступний — запасний список */
	}
	return ROLES;
}

/** POST /api/auth/login → токен + користувач. Кидає LoginError з людським текстом. */
export async function login(input: LoginInput): Promise<User> {
	let res: Response;
	try {
		res = await fetch('/api/auth/login', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
			body: JSON.stringify(input)
		});
	} catch {
		throw new LoginError(0, 'Сервер недоступний. Спробуйте ще раз за хвилину.');
	}

	// Режим розробки: бекенд-автентифікації ще немає — локальний вхід без токена
	if (import.meta.env.DEV && missing(res)) {
		console.warn('[auth] /api/auth/login ще не реалізовано — локальний DEV-вхід без токена');
		const u = normalize({ ...input, role_name: roleName(input.role) }, null)!;
		save(u, { mock: true });
		return u;
	}

	if (!res.ok) {
		let detail = '';
		try {
			const body = await res.json();
			if (typeof body?.detail === 'string') detail = body.detail;
		} catch {
			/* не JSON */
		}
		if (res.status === 401 || res.status === 403) throw new LoginError(res.status, detail || 'Невірний пароль');
		if (res.status === 429) throw new LoginError(429, detail || 'Забагато спроб. Зачекайте хвилину.');
		if (res.status === 422 && !detail) throw new LoginError(422, 'Перевірте заповнені поля');
		throw new LoginError(res.status, detail || `Не вдалося увійти (помилка ${res.status})`);
	}
	const body = (await res.json()) as { token: string; user: Record<string, unknown> };
	const u = normalize(body.user, body.token);
	if (!u) throw new LoginError(500, 'Сервер повернув неочікувану відповідь');
	save(u);
	return u;
}

/** Перевіряє збережений токен (GET /api/auth/me); прострочений — тихо виходимо в публічний режим */
export async function verifySession(): Promise<void> {
	const token = authToken();
	if (!token) return;
	try {
		const res = await fetch('/api/auth/me', { headers: { Accept: 'application/json', Authorization: `Bearer ${token}` } });
		if (res.status === 401) logout();
		else if (res.ok && !missing(res)) {
			const u = normalize(await res.json(), token);
			if (u) save(u);
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
