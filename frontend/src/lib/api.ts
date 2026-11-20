// Клієнт API бекенду (FastAPI). Усі шляхи відносні: у розробці працює проксі Vite, у продакшні — той самий сервер.
// Кожен запит до /api (і через getJSON, і звичайний fetch) отримує `Authorization: Bearer <token>`, якщо є вхід.

import { goto } from '$app/navigation';
import { auth, logout } from './auth.svelte.ts';

export interface YearSummary {
	partial: boolean;
	coverage: number;
	created: string | null;
	heat_gcal: number;
	elec_kwh: number;
	gas_m3: number;
	total_mwh: number;
}

export interface CategorySummary {
	count: number;
	in_rating: number;
	median_kwh_m2: number | null;
}

export interface Source {
	file: string;
	kind: string;
	rows: number;
	created?: string | null;
}

export interface Summary {
	buildings: number;
	in_rating: number;
	base_year: number | null;
	years: Record<string, YearSummary>;
	categories: Record<string, CategorySummary>;
	classes: Record<string, number>;
	defects: number;
	defect_buildings: number;
	sources: Source[];
	coefficients: Record<string, number>;
}

export interface YearData {
	year: number;
	partial: boolean;
	coverage: number;
	heat_gcal: number | null;
	elec_kwh: number | null;
	gas_m3: number | null;
	cold_m3: number | null;
	hot_m3: number | null;
	heat_mwh: number | null;
	elec_mwh: number | null;
	gas_mwh: number | null;
	total_mwh: number | null;
	kwh_m2: number | null;
	elec_kwh_m2: number | null;
}

export interface Defect {
	тип?: string;
	набір: string;
	будівля_id: number | string;
	будівля: string;
	поле: string;
	значення: string | number | null;
	правило: string;
	що_робити: string;
}

export interface Building {
	id: number;
	name: string;
	address: string;
	category?: string;
	category_short: string;
	heating: string;
	year_built: number | null;
	floors: number | null;
	heated_area: number | null;
	heated_volume?: number | null;
	has_coords: boolean;
	years: Record<string, YearData>;
	in_rating: boolean;
	excluded_reason: string | null;
	ratio_to_median: number | null;
	eff_class: string | null;
	rank: number | null;
	rank_of: number | null;
	defects_count?: number;
}

export interface BuildingFull extends Building {
	defects: Defect[];
	median_kwh_m2: number | null;
}

export interface SolarParams {
	tariff_uah_kwh: number;
	capex_uah_per_kw: number;
	kwp_per_m2_roof: number;
	capex_fixed_uah?: number;
	source_notes: string[];
}

export interface SolarItem {
	id: number;
	name: string;
	category_short: string;
	elec_kwh_year: number | null;
	roof_area_m2: number | null;
	kw_max_roof: number | null;
	kw_recommended: number | null;
	gen_kwh_year: number | null;
	self_consumed_kwh_year: number | null;
	coverage_pct: number | null;
	surplus_kwh_year: number | null;
	capex_uah: number | null;
	savings_uah_year: number | null;
	payback_years: number | null;
	/** що обмежує потужність: «споживання» або «дах» (може бути відсутнім) */
	limited_by?: string | null;
	rank: number | null;
}

export interface SolarList {
	params: SolarParams;
	items: SolarItem[];
}

export interface SolarMonth {
	month: number;
	gen_kwh: number;
	cons_kwh: number;
	self_kwh: number;
	surplus_kwh: number;
}

export interface SolarDetail {
	item: SolarItem;
	monthly: SolarMonth[];
	assumptions: string[];
	params?: SolarParams;
}

export type FreshStatus = 'fresh' | 'due' | 'stale';

export interface FreshSource {
	key: string;
	kind: string;
	label: string;
	as_of: string | null;
	age_days: number | null;
	status: FreshStatus;
	demo: boolean;
	how: 'upload' | 'script';
	how_hint: string;
	period: string;
	detail: string;
}

export interface Freshness {
	checked_at: string;
	overall: FreshStatus;
	as_of: string | null;
	counts: Record<FreshStatus, number>;
	sources: FreshSource[];
}

export interface UploadLogItem {
	at: string;
	file: string;
	kind: string;
	kind_label: string;
	year: number | null;
	ok: boolean;
	rows: number | null;
	error: string | null;
	user: string;
	role: string;
	channel: 'upload' | 'script';
	demo: boolean;
}

export interface UploadHistory {
	items: UploadLogItem[];
	real: number;
	demo: number;
}

export interface UploadResult {
	ok: boolean;
	kind: string;
	summary: Summary;
}

// --- Об'єкти з СЕС і телеметрією (ДЕМО-дані) ---

export type SiteStatus = 'surplus' | 'deficit' | 'no_ses';

export interface SiteTotals {
	sites: number;
	with_ses: number;
	generated_today_kwh: number;
	consumed_today_kwh: number;
	surplus_today_kwh: number;
	deficit_sites: number;
	surplus_sites: number;
}

export interface SiteItem {
	id: number;
	name: string;
	address: string;
	city: string;
	category_short: string;
	has_ses: boolean;
	ses_kw: number | null;
	status: SiteStatus;
	balance_kwh_today: number | null;
	generated_today_kwh: number | null;
}

export interface SitesResponse {
	demo: boolean;
	now: string;
	totals: SiteTotals;
	items: SiteItem[];
}

export interface SiteSes {
	panels_count: number;
	panel_w: number;
	total_kw: number;
	inverter_model: string;
	inverter_kw: number;
	battery_kwh: number;
	battery_kw: number;
	connected_kw: number;
	battery_within_connected: boolean;
	launched: string;
	/** «ДЕМО» — змодельовано; «CSV» — з реєстру міста */
	source?: string;
}

export interface SiteHour {
	hour: number;
	gen_kwh: number;
	cons_kwh: number;
	soc_pct: number | null;
	forecast: boolean;
}

export interface SiteDistribution {
	peak_kw: number;
	peak_hour: number;
	battery_kwh_now: number | null;
	battery_soc_pct: number | null;
	solar_kw_now: number | null;
	solar_kwh_rest_of_day: number | null;
	need_kwh_rest_of_day: number;
	available_kwh: number;
	balance_kwh: number;
	enough: boolean;
	reserve_to_grid_kwh: number;
}

export interface SiteDetail {
	demo: boolean;
	now: string;
	building: {
		id: number;
		name: string;
		address: string;
		city: string;
		category_short: string;
		heated_area: number | null;
		floors: number | null;
		elec_kwh_2025: number | null;
	};
	ses: SiteSes | null;
	today: {
		date: string;
		generated_kwh: number;
		consumed_kwh: number;
		self_kwh: number;
		from_grid_kwh: number;
		to_battery_kwh: number;
		surplus_kwh: number;
		peak_kw: number;
		peak_hour: number;
	};
	period: {
		since: string | null;
		days: number;
		generated_kwh: number | null;
		/** Реальне споживання UMUNI з дати consumed_since */
		consumed_kwh: number;
		consumed_since?: string;
		saved_uah: number | null;
	};
	limits: {
		tariff_uah_kwh: number;
		money_month_uah: number;
		money_month_used_uah: number;
		money_month_pct: number | null;
		energy_day_kwh: number;
		energy_day_used_kwh: number;
		energy_day_pct: number | null;
		over_money: boolean;
		over_day: boolean;
	};
	distribution: SiteDistribution;
	hourly: SiteHour[];
	notes: string[];
}

/** Помилка запиту з HTTP-статусом і зрозумілим повідомленням */
export class ApiError extends Error {
	status: number;
	constructor(status: number, message: string) {
		super(message);
		this.status = status;
	}
}

const NO_SERVER = 'Немає зв’язку із сервером. Перевірте, чи запущено бекенд.';

/** Дістає текст помилки з відповіді FastAPI ({detail: "..."}) */
async function errorText(res: Response): Promise<string> {
	try {
		const body = await res.json();
		if (typeof body?.detail === 'string') return body.detail;
	} catch {
		/* не JSON — ігноруємо */
	}
	return `Сервер відповів помилкою ${res.status}`;
}

// ---------- Токен у кожному запиті до /api ----------

/** Запит іде на наш бекенд (/api/…, той самий origin)? */
function isApiUrl(input: RequestInfo | URL): boolean {
	try {
		const raw = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
		const u = new URL(raw, location.href);
		return u.origin === location.origin && u.pathname.startsWith('/api/') && !u.pathname.startsWith('/api/auth/login');
	} catch {
		return false;
	}
}

/** Сесія прострочена (токен був, бекенд відповів 401) → виходимо і ведемо на /login */
function sessionExpired(): void {
	logout();
	const back = location.pathname + location.search;
	if (location.pathname !== '/login') {
		goto('/login' + (back !== '/' ? `?next=${encodeURIComponent(back)}` : ''), { replace: true, reset: false });
	}
}

// Обгортка fetch, встановлюється один раз для всього застосунку — тож і «сирі» fetch('/api/…')
// з інших модулів несуть токен. На 401 із токеном — вихід і /login; у публічному режимі
// 401 просто повертається сторінці (getJSON кидає ApiError 401) — вона сама вирішує, що показати.
const nativeFetch: typeof fetch | undefined = typeof window !== 'undefined' ? window.fetch.bind(window) : undefined;
if (nativeFetch && !(window as unknown as { __energoFetch?: boolean }).__energoFetch) {
	(window as unknown as { __energoFetch?: boolean }).__energoFetch = true;
	window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
		if (!isApiUrl(input)) return nativeFetch(input, init);
		const token = auth.user?.token ?? null;
		let sent = false;
		if (token) {
			const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined));
			if (!headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`);
			sent = headers.get('Authorization') === `Bearer ${token}`;
			init = { ...init, headers };
		}
		const res = await nativeFetch(input, init);
		if (res.status === 401 && sent && auth.user?.token === token) sessionExpired();
		return res;
	};
}

export async function getJSON<T>(url: string): Promise<T> {
	let res: Response;
	try {
		res = await fetch(url, { headers: { Accept: 'application/json' } });
	} catch {
		throw new ApiError(0, NO_SERVER);
	}
	if (res.status === 401) throw new ApiError(401, 'Доступно після входу');
	if (res.status === 403) throw new ApiError(403, 'Недостатньо прав для цих даних');
	if (!res.ok) throw new ApiError(res.status, await errorText(res));
	const type = res.headers.get('content-type') ?? '';
	// Якщо ендпоінту ще немає, сервер може віддати index.html SPA — вважаємо це як 404
	if (!type.includes('json')) throw new ApiError(404, 'Ендпоінт ще не реалізовано');
	return (await res.json()) as T;
}

/** Будує рядок запиту, пропускаючи порожні значення */
export function qs(params: Record<string, string | number | null | undefined>): string {
	const p = new URLSearchParams();
	for (const [k, v] of Object.entries(params)) {
		if (v !== null && v !== undefined && v !== '') p.set(k, String(v));
	}
	const s = p.toString();
	return s ? `?${s}` : '';
}

/** Момент, на який показуємо телеметрію: зараз або типовий літній день (для демо) */
export type ViewKey = 'now' | 'summer';

export const VIEWS: Record<ViewKey, { label: string; day?: string; hour?: number }> = {
	now: { label: 'Зараз' },
	summer: { label: 'Літній день', day: '2026-06-05', hour: 13 }
};

export function viewQs(view?: ViewKey): string {
	const v = VIEWS[view ?? 'now'];
	return qs({ day: v.day, hour: v.hour });
}

export const api = {
	summary: () => getJSON<Summary>('/api/summary'),
	freshness: () => getJSON<Freshness>('/api/freshness'),
	uploadHistory: (limit = 50) => getJSON<UploadHistory>('/api/uploads/history' + qs({ limit })),
	buildings: (category?: string) => getJSON<Building[]>('/api/buildings' + qs({ category })),
	building: (id: string | number) =>
		getJSON<BuildingFull>(`/api/buildings/${encodeURIComponent(id)}`),
	defects: () => getJSON<Defect[]>('/api/defects'),
	sites: (view?: ViewKey) => getJSON<SitesResponse>('/api/sites' + viewQs(view)),
	site: (id: string | number, view?: ViewKey) =>
		getJSON<SiteDetail>(`/api/sites/${encodeURIComponent(id)}` + viewQs(view)),
	solar: (p: { category?: string; tariff?: number | null; capex?: number | null }) =>
		getJSON<SolarList>('/api/solar' + qs(p)),
	solarOne: (id: string | number, p: { tariff?: number | null; capex?: number | null }) =>
		getJSON<SolarDetail>(`/api/solar/${encodeURIComponent(id)}` + qs(p)),
	async upload(file: File): Promise<UploadResult> {
		const fd = new FormData();
		fd.append('file', file);
		let res: Response;
		try {
			res = await fetch('/api/upload', { method: 'POST', body: fd });
		} catch {
			throw new ApiError(0, NO_SERVER);
		}
		if (res.status >= 500) {
			// Бекенд падає на пошкодженому або «чужому» файлі — пояснюємо людською мовою
			throw new ApiError(
				res.status,
				'Не вдалося прочитати файл. Перевірте, що це справжній XLSX-звіт з UMUNI, збережений без змін.'
			);
		}
		if (!res.ok) throw new ApiError(res.status, await errorText(res));
		return (await res.json()) as UploadResult;
	}
};

/** Текст помилки для показу користувачу */
export function errMessage(e: unknown): string {
	if (e instanceof Error) return e.message;
	return 'Невідома помилка';
}
