// Вхід і поточний користувач. Без входу застосунок недоступний (лише /login).
// Токен бекенду (HMAC) і користувач живуть лише в sessionStorage вкладки.
// Використання: import { auth, currentRole } from '#lib/auth.svelte.ts'; auth.user?.role

import { roleName, type RoleId, type Department } from './roles.ts';

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

/** Роль поточного користувача; без входу — 'public' (лише службове значення) */
export function currentRole(): RoleId {
	return auth.user?.role ?? 'public';
}

/** Токен для заголовка Authorization (або null без входу) */
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
