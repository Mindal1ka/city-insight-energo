// Тестовий вхід для демонстрації: користувач живе лише в sessionStorage вкладки.
// Справжня автентифікація (ролі, сесія на бекенді) — наступний крок.

export interface User {
	full_name: string;
	position: string;
}

export const DEFAULT_POSITION = 'Головний фахівець з енергоменеджменту';

const KEY = 'energo.user';

function read(): User | null {
	try {
		const raw = sessionStorage.getItem(KEY);
		if (!raw) return null;
		const u = JSON.parse(raw);
		if (typeof u?.full_name === 'string' && typeof u?.position === 'string') return u;
	} catch {
		/* сховище недоступне — вважаємо, що входу немає */
	}
	return null;
}

export const auth = $state<{ user: User | null }>({ user: read() });

export function login(user: User): void {
	auth.user = user;
	try {
		sessionStorage.setItem(KEY, JSON.stringify(user));
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
