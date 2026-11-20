// Мережевий шар застосунку: обгортка window.fetch для /api/*.
// • токен у кожному запиті; на 401 — одна спроба продовжити сесію (/api/auth/refresh) і повтор, інакше /login?next=
// • GET → кеш stale-while-revalidate (store/cache.ts): свіже — без мережі, застаріле — одразу + оновлення у фоні,
//   однакові одночасні запити — один мережевий; умовні запити з ETag (304 — без тіла)
// • успішний запис (POST/PUT/PATCH/DELETE) → кеш недійсний у цій і в інших вкладках (BroadcastChannel)
// Сторінки нічого не знають про кеш: вони, як і раніше, роблять fetch/getJSON.

import { goto } from '$app/navigation';
import { untrack } from 'svelte';
import { auth, logout, authToken, refreshSession } from '../auth.svelte.ts';
import * as cache from './cache.ts';

/** Запит іде на наш бекенд (/api/…, той самий origin)? */
export function isApiUrl(input: RequestInfo | URL): boolean {
	try {
		const u = urlOf(input);
		return u.origin === location.origin && u.pathname.startsWith('/api/') && !u.pathname.startsWith('/api/auth/login');
	} catch {
		return false;
	}
}

/** Сесія прострочена (бекенд відповів 401 і продовжити не вдалося) → вихід і /login зі збереженням сторінки */
function sessionExpired(): void {
	logout();
	const back = location.pathname + location.search;
	if (location.pathname !== '/login') {
		goto('/login' + (back !== '/' ? `?next=${encodeURIComponent(back)}` : ''), { replace: true, reset: false });
	}
}

/** Скоуп кешу — права і особа користувача: інша роль/об'єкт/людина → порожній кеш */
function scopeOf(): string {
	const u = untrack(() => auth.user);
	return u?.token ? [u.role, u.building_id ?? '', u.department ?? '', u.full_name].join('|') : '';
}

function urlOf(input: RequestInfo | URL): URL {
	const raw = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
	return new URL(raw, location.href);
}

function methodOf(input: RequestInfo | URL, init?: RequestInit): string {
	return (init?.method ?? (input instanceof Request ? input.method : 'GET')).toUpperCase();
}

const nativeFetch: typeof fetch | undefined = typeof window !== 'undefined' ? window.fetch.bind(window) : undefined;

/** Мережевий запит з токеном; на 401 — одна спроба продовжити сесію і повтор */
async function authedFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
	const send = (token: string | null) => {
		let i = init;
		if (token) {
			const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined));
			if (!headers.has('Authorization') || headers.get('Authorization')?.startsWith('Bearer ')) {
				headers.set('Authorization', `Bearer ${token}`);
			}
			i = { ...init, headers };
		}
		return nativeFetch!(input, i);
	};
	const token = authToken();
	const res = await send(token);
	// /api/auth/* (me, refresh) розбираються самі — без рекурсивного продовження
	if (res.status === 401 && token && authToken() === token && !urlOf(input).pathname.startsWith('/api/auth/')) {
		if (await refreshSession()) return send(authToken());
		if (authToken() === token) sessionExpired();
	}
	return res;
}

/** GET у мережу → знімок (тіло текстом), щоб віддати кожному з об'єднаних викликів */
async function fetchSnap(path: string, init?: RequestInit): Promise<cache.Snap> {
	const prev = cache.get(path);
	const headers = new Headers(init?.headers);
	if (prev?.etag && prev.status === 200) headers.set('If-None-Match', prev.etag);
	// cache:'no-cache' — HTTP-кеш браузера лише з перевіркою; свіжість контролюємо тут
	const res = await authedFetch(path, { ...init, signal: undefined, headers, cache: 'no-cache' });
	if (res.status === 304 && prev) {
		cache.touch(path);
		return prev;
	}
	const snap: cache.Snap = {
		status: res.status,
		ctype: res.headers.get('content-type') ?? '',
		etag: res.headers.get('etag'),
		body: await res.text(),
		at: Date.now()
	};
	if (res.status === 200 && snap.ctype.includes('json')) cache.put(path, snap);
	return snap;
}

function revalidate(path: string, init?: RequestInit): Promise<cache.Snap> {
	return cache.dedupe(path, () => fetchSnap(path, init));
}

/** Віддає відповідь, але відпускає виклик, якщо його AbortSignal спрацював (спільний запит триває) */
function withSignal(p: Promise<Response>, signal?: AbortSignal | null): Promise<Response> {
	if (!signal) return p;
	if (signal.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'));
	return new Promise((resolve, reject) => {
		const onAbort = () => reject(new DOMException('Aborted', 'AbortError'));
		signal.addEventListener('abort', onAbort, { once: true });
		p.then(resolve, reject).finally(() => signal.removeEventListener('abort', onAbort));
	});
}

const bc: BroadcastChannel | null =
	typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('energo.cache') : null;
bc?.addEventListener('message', (e) => {
	if (e.data?.type === 'invalidate') cache.invalidate();
});

/** Після успішного запису: кеш недійсний (у цій і в інших вкладках) */
export function invalidateAfterWrite(): void {
	cache.invalidate();
	bc?.postMessage({ type: 'invalidate' });
}

// Встановлюється один раз для всього застосунку — тож і «сирі» fetch('/api/…') з інших модулів
// несуть токен і користуються кешем.
if (nativeFetch && !(window as unknown as { __energoFetch?: boolean }).__energoFetch) {
	(window as unknown as { __energoFetch?: boolean }).__energoFetch = true;
	window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
		if (!isApiUrl(input)) return nativeFetch(input, init);
		const u = urlOf(input);
		const path = u.pathname + u.search;
		const method = methodOf(input, init);
		cache.setScope(scopeOf());
		if (method !== 'GET') {
			const res = await authedFetch(input, init);
			if (res.ok && !u.pathname.startsWith('/api/auth/')) invalidateAfterWrite();
			return res;
		}
		if (
			!cache.getScope() ||
			!cache.cacheable(u.pathname) ||
			input instanceof Request ||
			init?.cache === 'no-store' ||
			init?.cache === 'reload'
		) {
			return authedFetch(input, init);
		}
		learn(path);
		const hit = cache.get(path);
		const age = cache.age(path);
		if (hit && age < cache.ttlFor(u.pathname)) return cache.toResponse(hit, 'HIT');
		if (hit && age < cache.maxStaleFor(u.pathname)) {
			revalidate(path, init).catch(() => {}); // у фоні; сторінка отримує дані одразу
			return cache.toResponse(hit, 'STALE');
		}
		return withSignal(
			revalidate(path, init).then((s) => cache.toResponse(s, 'NET')),
			init?.signal
		);
	};
}

/** Фонове завантаження (не блокує): force — оновити навіть свіже */
export async function prefetch(path: string, force = false): Promise<void> {
	if (!nativeFetch || !authToken()) return;
	cache.setScope(scopeOf());
	const p = new URL(path, location.href).pathname;
	if (!cache.cacheable(p)) return;
	if (!force && cache.age(path) < cache.ttlFor(p)) return;
	try {
		await revalidate(path);
	} catch {
		/* мережа недоступна — спробуємо пізніше */
	}
}

// --- які API-запити робить кожна сторінка (для передзавантаження при наведенні/у фоні) ---
// Зберігаємо лише шаблони URL (без даних), напр. /object/:id → /api/insight/:id
const LEARN_KEY = 'energo.routes.v1';
let learned: Record<string, string[]> = {};
try {
	learned = JSON.parse(localStorage.getItem(LEARN_KEY) || '{}');
} catch {
	learned = {};
}
let learnTimer: ReturnType<typeof setTimeout> | null = null;

function pattern(pathname: string): { pat: string; id: string | null } {
	const m = pathname.match(/^(.*\/)(\d+)(\/.*)?$/);
	return m ? { pat: m[1] + ':id' + (m[3] ?? ''), id: m[2] } : { pat: pathname, id: null };
}

function learn(apiPath: string): void {
	if (typeof location === 'undefined' || location.pathname === '/login') return;
	const { pat, id } = pattern(location.pathname);
	const tpl = id ? apiPath.replace(new RegExp(`/${id}(?=[/?]|$)`), '/:id') : apiPath;
	const list = (learned[pat] ??= []);
	if (list.includes(tpl)) return;
	list.push(tpl);
	if (list.length > 12) list.shift();
	if (!learnTimer)
		learnTimer = setTimeout(() => {
			learnTimer = null;
			try {
				localStorage.setItem(LEARN_KEY, JSON.stringify(learned));
			} catch {
				/* ігноруємо */
			}
		}, 2000);
}

/** API-URL, які сторінка завантажувала раніше (за шаблоном шляху) */
export function learnedFor(pathname: string): string[] {
	const { pat, id } = pattern(pathname);
	return (learned[pat] ?? []).map((t) => (id ? t.replace('/:id', '/' + id) : t)).filter((t) => !t.includes(':id'));
}
