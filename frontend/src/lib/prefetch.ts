// Фонове завантаження даних розділів, які користувач ще не відкривав, і підтримка «живих» даних свіжими.
// • після входу/старту, коли браузер вільний (requestIdleCallback) — по черзі за пріоритетом ролі;
// • «живі» набори (енергія зараз) — кожні 60 с, СЕС/день — кожні 5 хв; у прихованій вкладці — у 5 разів рідше;
//   повернення у вкладку або поява мережі — оновлення одразу;
// • намір: наведення/фокус/дотик до посилання → передзавантаження даних цієї сторінки.
// Усе йде через кеш (store/net.ts), тож відкриття сторінки бере дані з пам'яті без очікування.

import { auth, maybeRefresh, type User } from './auth.svelte.ts';
import { isCityWide, isInternal, canUpload } from './roles.ts';
import { prefetch, learnedFor } from './store/net.ts';
import { LIVE_RE } from './store/cache.ts';
import { untrack } from 'svelte';

/** Дані сторінок за замовчуванням (доповнюються тим, що сторінки реально запитували — learnedFor) */
const ROUTE_DATA: Record<string, string[]> = {
	'/dashboard': ['/api/summary', '/api/departments', '/api/ses', '/api/live'],
	'/': ['/api/map'],
	'/objects': ['/api/ses'],
	'/energy': ['/api/live', '/api/forecast?days=3'],
	'/overview': ['/api/summary', '/api/buildings'],
	'/finance': ['/api/budget-real', '/api/spending'],
	'/report': ['/api/report'],
	'/blackout': ['/api/blackout', '/api/generators', '/api/outages'],
	'/appeals': ['/api/appeals'],
	'/upload': ['/api/freshness', '/api/uploads/history']
};

/** Пріоритет розділів (порядок фонового завантаження) з урахуванням ролі */
function routesFor(user: User): string[] {
	const out = ['/dashboard', '/', '/objects', '/energy', '/finance', '/report', '/overview'];
	if (isCityWide(user)) out.push('/blackout');
	if (isInternal(user)) out.push('/appeals');
	if (canUpload(user)) out.push('/upload');
	return out;
}

/** URL даних сторінки: те, що вона запитувала раніше, + типові */
export function urlsForRoute(pathname: string): string[] {
	const m = pathname.match(/^\/(object|building)\/(\d+)/);
	const extra = m ? (m[1] === 'object' ? [`/api/insight/${m[2]}`] : [`/api/buildings/${m[2]}`]) : [];
	return [...new Set([...learnedFor(pathname), ...(ROUTE_DATA[pathname] ?? []), ...extra])];
}

const idle = (fn: () => void) =>
	typeof requestIdleCallback === 'function' ? requestIdleCallback(fn, { timeout: 2000 }) : setTimeout(fn, 300);

let runId = 0;

/** Черга фонового завантаження за пріоритетом; один запит за раз, у вільний час браузера */
function warmUp(): void {
	const user = untrack(() => auth.user);
	if (!user?.token) return;
	const id = ++runId;
	const queue = [...new Set(routesFor(user).flatMap((r) => urlsForRoute(r)))];
	const step = () => {
		if (id !== runId || !untrack(() => auth.user?.token)) return; // вихід/інший користувач — зупиняємось
		const url = queue.shift();
		if (!url) return;
		prefetch(url).finally(() => idle(step));
	};
	idle(step);
}

// ---- періодичне оновлення ----
const LIVE_MS = 60_000;
const DAY_MS = 5 * 60_000;
const HIDDEN_FACTOR = 5;
let lastLive = 0;
let lastDay = 0;

function tick(force = false): void {
	if (!untrack(() => auth.user?.token)) return;
	const now = Date.now();
	const f = document.hidden ? HIDDEN_FACTOR : 1;
	if (force || now - lastLive >= LIVE_MS * f) {
		lastLive = now;
		const live = [...new Set([...urlsForRoute('/energy'), ...urlsForRoute(location.pathname)])].filter((u) =>
			LIVE_RE.test(u.split('?')[0])
		);
		for (const u of live) void prefetch(u, true);
	}
	if (force || now - lastDay >= DAY_MS * f) {
		lastDay = now;
		void prefetch('/api/ses', true);
		void prefetch('/api/summary');
	}
}

let started = false;

/** Запуск з кореневого layout: один раз; реагує на вхід/вихід через auth.user */
export function startBackgroundData(): void {
	if (started || typeof window === 'undefined') return;
	started = true;
	lastLive = lastDay = Date.now();
	setInterval(() => tick(), 15_000);
	document.addEventListener('visibilitychange', () => {
		if (!document.hidden) tick(true);
	});
	window.addEventListener('online', () => tick(true));
	installIntentPrefetch();
}

/** Викликати, коли з'явився/змінився користувач (вхід, старт застосунку зі збереженою сесією) */
export function onUserReady(): void {
	void maybeRefresh();
	warmUp();
}

// ---- передзавантаження за наміром ----
function installIntentPrefetch(): void {
	const seen = new Map<string, number>();
	const handler = (e: Event) => {
		const a = (e.target as Element | null)?.closest?.('a[href]') as HTMLAnchorElement | null;
		if (!a || a.target === '_blank' || a.hasAttribute('download')) return;
		let u: URL;
		try {
			u = new URL(a.href, location.href);
		} catch {
			return;
		}
		if (u.origin !== location.origin || u.pathname.startsWith('/api/') || u.pathname === location.pathname) return;
		const last = seen.get(u.pathname) ?? 0;
		if (Date.now() - last < 10_000) return;
		seen.set(u.pathname, Date.now());
		for (const url of urlsForRoute(u.pathname)) void prefetch(url);
	};
	document.addEventListener('pointerover', handler, { passive: true });
	document.addEventListener('focusin', handler, { passive: true });
	document.addEventListener('touchstart', handler, { passive: true });
}

/** Ручне передзавантаження даних об'єкта (рядок таблиці/маркер мапи без <a>) */
export function prefetchObject(id: number | string): void {
	for (const url of urlsForRoute(`/object/${id}`)) void prefetch(url);
}
