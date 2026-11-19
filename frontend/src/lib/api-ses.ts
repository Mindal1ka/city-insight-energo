// Ефективність СЕС: типи + запити до /api/ses і /api/ses/{id} (контракт — docs/PLAN_v3.md).
// K = згенеровано ÷ спожито. Класи: < 0,8 «Не вистачає», 0,8…1,2 «Ефективно», > 1,2 «Надлишок».
// Спільний модуль для мапи, списку, дашборду й картки об'єкта.

import { ApiError, qs } from '#lib/api.ts';
import { authToken, currentRole } from '#lib/auth.svelte.ts';

export type Period = 'day' | 'month' | 'year';
export type KClass = 'Ефективно' | 'Не вистачає' | 'Надлишок' | 'Без СЕС' | 'Немає даних';

export const PERIODS: { id: Period; label: string }[] = [
	{ id: 'day', label: 'День' },
	{ id: 'month', label: 'Місяць' },
	{ id: 'year', label: 'Рік' }
];

/** Пороги за замовчуванням (бекенд віддає свої у `thresholds`) */
export const THRESHOLDS = { low: 0.8, high: 1.2 } as const;

export interface KClassMeta {
	id: KClass;
	/** Коротке слово для бейджа */
	short: string;
	color: string;
	soft: string;
	/** Колір тексту на `color` */
	ink: string;
	/** Символ-дубль кольору (колір — ніколи не єдиний сигнал) */
	icon: string;
	/** SVG-шлях форми маркера в полі 10×10 */
	glyph: string;
	shape: string;
}

export const K_CLASSES: KClassMeta[] = [
	{ id: 'Ефективно', short: 'Ефективно', color: '#1f8a4c', soft: '#e3f4ea', ink: '#fff', icon: '✓', glyph: 'M5 .9a4.1 4.1 0 1 1 0 8.2 4.1 4.1 0 0 1 0-8.2z', shape: 'коло' },
	{ id: 'Не вистачає', short: 'Не вистачає', color: '#d9680f', soft: '#fdeedf', ink: '#fff', icon: '↓', glyph: 'M.8 1.6h8.4L5 9.2z', shape: 'трикутник вниз' },
	{ id: 'Надлишок', short: 'Надлишок', color: '#1f6fd1', soft: '#e3eefb', ink: '#fff', icon: '↑', glyph: 'M5 .8 9.2 8.4H.8z', shape: 'трикутник вгору' },
	{ id: 'Без СЕС', short: 'Без СЕС', color: '#7a8594', soft: '#eef0f3', ink: '#fff', icon: '○', glyph: 'M1.6 1.6h6.8v6.8H1.6z', shape: 'квадрат' },
	{ id: 'Немає даних', short: 'Немає даних', color: '#b9c1cc', soft: '#f3f5f8', ink: '#2b3442', icon: '?', glyph: 'M5 .6 9.4 5 5 9.4.6 5z', shape: 'ромб' }
];

const BY_ID = new Map(K_CLASSES.map((c) => [c.id, c]));
export function kClassMeta(c: KClass | null | undefined): KClassMeta {
	return BY_ID.get(c as KClass) ?? K_CLASSES[4];
}

/** Клас за K (для макету та для перевірки) */
export function classifyK(k: number | null | undefined, hasSes: boolean | null, t = THRESHOLDS): KClass {
	if (hasSes === false) return 'Без СЕС';
	if (k == null || !isFinite(k)) return 'Немає даних';
	if (k < t.low) return 'Не вистачає';
	if (k > t.high) return 'Надлишок';
	return 'Ефективно';
}

/** «0,94» */
export function kText(k: number | null | undefined): string {
	if (k == null || !isFinite(k)) return '—';
	return k.toLocaleString('uk-UA', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ---------- /api/ses ----------

export interface SesTotals {
	objects: number;
	with_ses: number | null;
	effective: number | null;
	deficit: number | null;
	surplus: number | null;
	no_ses: number | null;
	no_data: number | null;
	gen_kwh: number | null;
	cons_kwh: number | null;
	k: number | null;
	capex_uah: number | null;
	saved_uah_year: number | null;
	grid_cost_uah_year: number | null;
	/** Споживання / K усієї громади (totals.cons_kwh і k — лише по об'єктах із СЕС) */
	cons_kwh_all?: number | null;
	k_all?: number | null;
}

export interface SesItem {
	id: number;
	name: string;
	address: string;
	category_short: string;
	lat: number | null;
	lon: number | null;
	precision: string | null;
	/** null — приховано для публічного режиму */
	has_ses: boolean | null;
	k: number | null;
	/** null — приховано для публічного режиму */
	k_class: KClass | null;
	gen_kwh: number | null;
	cons_kwh: number | null;
	ses_kw: number | null;
	battery_kwh: number | null;
	capex_uah: number | null;
	saved_uah_year: number | null;
	payback_years: number | null;
	/** null — для public / без фінансового доступу */
	grid_cost_uah_year?: number | null;
	/** Рівень доступу до цього об'єкта */
	access?: 'full' | 'ses' | 'public';
	approximate?: boolean;
	/** v2: розпорядник коштів (департамент) */
	department?: string;
	/** v2: середнє споживання е/е за місяць, кВт·год (2025 ÷ 12) */
	cons_kwh_month_avg?: number | null;
}

export interface SesList {
	demo: boolean;
	period: Period;
	thresholds: { low: number; high: number };
	totals: SesTotals;
	items: SesItem[];
	/** Помісячно по громаді (12 записів) */
	monthly?: { month: number; gen_kwh: number | null; cons_kwh: number | null; cons_kwh_all?: number | null; k: number | null }[];
	tariff_uah_kwh?: number;
	/** true — дані зібрано на клієнті (бекенд /api/ses ще не готовий) */
	mock?: boolean;
	/** true — по-об'єктні K приховано (публічний режим) */
	restricted?: boolean;
}

// ---------- /api/ses/{id} ----------

export interface SesInfo {
	panels_count: number | null;
	panel_w: number | null;
	total_kw: number | null;
	inverter_model: string | null;
	inverter_kw: number | null;
	battery_count: number | null;
	battery_module_kwh: number | null;
	battery_kwh: number | null;
	battery_kw: number | null;
	connected_kw: number | null;
	launched: string | null;
	source: 'ДЕМО' | 'введено';
}

export interface SesCosts {
	panels_uah: number | null;
	inverter_uah: number | null;
	batteries_uah: number | null;
	install_uah: number | null;
	total_uah: number | null;
}

export interface EnergyBlock {
	gen_kwh: number | null;
	cons_kwh: number | null;
	self_kwh: number | null;
	surplus_kwh: number | null;
	grid_kwh: number | null;
}

export interface SesFinance {
	tariff_uah_kwh: number | null;
	grid_cost_uah: { month: number | null; year: number | null };
	saved_uah: { month: number | null; year: number | null; since_launch: number | null };
	invested_uah: number | null;
	payback_years: number | null;
	payback_progress_pct: number | null;
}

export interface SesDetail {
	demo: boolean;
	building: Record<string, unknown> & { id: number; name: string; address?: string; category_short?: string };
	ses: SesInfo | null;
	costs: SesCosts | null;
	k: Record<Period, number | null>;
	k_class: Record<Period, KClass | null>;
	energy: Record<Period, EnergyBlock>;
	finance: SesFinance | null;
	monthly: { month: number; gen_kwh: number | null; cons_kwh: number | null; k: number | null }[];
	meters: { electricity: number | null; total: number | null; by_resource: Record<string, number> } | null;
	sem: Record<string, unknown> | null;
	can_edit: boolean;
}

export type SesUpdate = Partial<Omit<SesInfo, 'source' | 'battery_kwh'>> & Partial<Omit<SesCosts, 'total_uah'>>;

// ---------- Запити ----------

/** Токен входу (якщо є) — з auth.svelte.ts */
function token(): string | null {
	try {
		return authToken();
	} catch {
		return null;
	}
}

export async function req<T>(url: string, init: RequestInit = {}): Promise<T> {
	const headers = new Headers(init.headers);
	headers.set('Accept', 'application/json');
	const t = token();
	if (t && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${t}`);
	let res: Response;
	try {
		res = await fetch(url, { ...init, headers });
	} catch {
		throw new ApiError(0, 'Немає зв’язку із сервером');
	}
	if (!res.ok) {
		let msg = `Помилка ${res.status}`;
		try {
			const b = await res.json();
			if (typeof b?.detail === 'string') msg = b.detail;
		} catch {
			/* не JSON */
		}
		throw new ApiError(res.status, msg);
	}
	if (!(res.headers.get('content-type') ?? '').includes('json')) throw new ApiError(404, 'Ендпоінт ще не реалізовано');
	return (await res.json()) as T;
}

/** Список об'єктів з K за період. Поки /api/ses немає (404) — макет із /api/map (див. нижче). */
export async function fetchSes(period: Period = 'year', day?: string): Promise<SesList> {
	try {
		const d = await req<SesList>('/api/ses' + qs({ period, day }));
		const restricted = d.items.length > 0 && d.items.every((i) => i.k_class == null && i.has_ses == null);
		return { ...d, restricted };
	} catch (e) {
		if (e instanceof ApiError && e.status === 404) return mockSes(period);
		throw e;
	}
}

export async function fetchSesDetail(id: number, day?: string): Promise<SesDetail> {
	return req<SesDetail>(`/api/ses/${id}` + qs({ day }));
}

export async function updateSes(id: number, body: SesUpdate): Promise<SesDetail> {
	return req<SesDetail>(`/api/ses/${id}`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body)
	});
}

// ---------- Підрахунок підсумків (для фільтрів на клієнті) ----------

export function countClasses(items: SesItem[]): Record<KClass, number> {
	const out: Record<KClass, number> = { Ефективно: 0, 'Не вистачає': 0, Надлишок: 0, 'Без СЕС': 0, 'Немає даних': 0 };
	for (const i of items) if (i.k_class) out[i.k_class]++;
	return out;
}

// =====================================================================================
// ⚠ ТИМЧАСОВИЙ МАКЕТ (MOCK) — використовується ЛИШЕ коли /api/ses відповідає 404.
// Точки беремо з /api/map, а наявність СЕС і K — ВИПАДКОВІ (детерміновані за id).
// Прибрати, щойно бекенд віддає /api/ses.
// =====================================================================================

function rng(seed: number): () => number {
	let a = seed >>> 0;
	return () => {
		a = (a + 0x6d2b79f5) >>> 0;
		let t = a;
		t = Math.imul(t ^ (t >>> 15), t | 1);
		t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

async function mockSes(period: Period): Promise<SesList> {
	const { loadMap } = await import('#lib/api-map.ts');
	const map = await loadMap();
	const div = period === 'day' ? 365 : period === 'month' ? 12 : 1;
	const items: SesItem[] = map.points.map((p) => {
		const r = rng(p.id * 2654435761 + 7);
		const yearCons = p.elec_kwh_2025;
		const hasSes = r() < 0.45;
		const sesKw = hasSes ? Math.round((10 + r() * 60) * 10) / 10 : null;
		const periodJitter = period === 'year' ? 1 : 0.6 + r() * 0.8;
		const cons = yearCons != null ? yearCons / div : null;
		const gen = sesKw != null ? ((sesKw * 1150) / div) * periodJitter : null;
		const k = hasSes && cons && gen != null ? gen / cons : null;
		const capex = sesKw != null ? Math.round(sesKw * 32000) : null;
		const saved = gen != null && cons ? Math.round(Math.min(gen, cons) * div * 4.32) : null;
		return {
			id: p.id,
			name: p.name,
			address: p.address,
			category_short: p.category_short,
			lat: p.lat,
			lon: p.lon,
			precision: p.precision,
			has_ses: hasSes,
			k: k != null ? Math.round(k * 100) / 100 : null,
			k_class: classifyK(k, hasSes),
			gen_kwh: gen != null ? Math.round(gen) : hasSes ? null : 0,
			cons_kwh: cons != null ? Math.round(cons) : null,
			ses_kw: sesKw,
			battery_kwh: hasSes && r() < 0.5 ? Math.round(10 + r() * 40) : null,
			capex_uah: capex,
			saved_uah_year: saved,
			payback_years: capex && saved ? Math.round((capex / saved) * 10) / 10 : null
		};
	});
	const c = countClasses(items);
	const isPublic = currentRole() === 'public';
	const sum = (f: (i: SesItem) => number | null) => items.reduce((s, i) => s + (f(i) ?? 0), 0);
	const gen = sum((i) => (i.has_ses ? i.gen_kwh : 0));
	const cons = sum((i) => (i.has_ses ? i.cons_kwh : 0));
	return {
		demo: true,
		mock: true,
		restricted: isPublic,
		period,
		thresholds: { ...THRESHOLDS },
		totals: {
			objects: items.length,
			with_ses: items.filter((i) => i.has_ses).length,
			effective: c['Ефективно'],
			deficit: c['Не вистачає'],
			surplus: c['Надлишок'],
			no_ses: c['Без СЕС'],
			no_data: c['Немає даних'],
			gen_kwh: Math.round(gen),
			cons_kwh: Math.round(cons),
			k: cons ? Math.round((gen / cons) * 100) / 100 : null,
			capex_uah: sum((i) => i.capex_uah),
			saved_uah_year: sum((i) => i.saved_uah_year),
			grid_cost_uah_year: Math.round(sum((i) => i.cons_kwh) * div * 4.32)
		},
		// Публічний режим: як бекенд — прибираємо по-об'єктні СЕС-поля, підсумки лишаються
		items: isPublic
			? items.map((i) => ({ ...i, has_ses: null, k: null, k_class: null, ses_kw: null, battery_kwh: null, capex_uah: null }))
			: items
	};
}

// ---------- Фільтри (спільні для мапи й списку) ----------

export interface SesFilter {
	classes: KClass[];
	types: string[];
	q: string;
}

function norm(s: string): string {
	return s.toLocaleLowerCase('uk').replace(/[’ʼ`´']/g, '');
}

export function matchQ(it: SesItem, q: string): boolean {
	const t = norm(q.trim());
	if (!t) return true;
	return norm(`${it.name} ${it.address ?? ''} ${it.id}`).includes(t);
}

export function matchType(it: SesItem, types: string[]): boolean {
	return !types.length || types.includes(it.category_short);
}

export function matchClass(it: SesItem, classes: KClass[]): boolean {
	return !classes.length || (it.k_class != null && classes.includes(it.k_class));
}

export function filterItems(items: SesItem[], f: SesFilter): SesItem[] {
	return items.filter((i) => matchClass(i, f.classes) && matchType(i, f.types) && matchQ(i, f.q));
}

/** Гривні компактно: 1 250 000 → «1,3 млн ₴» */
export function uah(v: number | null | undefined): string {
	if (v == null || !isFinite(v)) return '—';
	const a = Math.abs(v);
	const f = (x: number, d: number) => x.toLocaleString('uk-UA', { maximumFractionDigits: d });
	if (a >= 1e6) return `${f(v / 1e6, a >= 1e7 ? 0 : 1)} млн ₴`;
	if (a >= 1e3) return `${f(v / 1e3, a >= 1e4 ? 0 : 1)} тис. ₴`;
	return `${f(v, 0)} ₴`;
}

/** кВт·год компактно: 12 400 → «12 тис. кВт·год», 1,2 млн → «1,2 ГВт·год» не робимо — тільки тис./млн */
export function kwh(v: number | null | undefined): string {
	if (v == null || !isFinite(v)) return '—';
	const a = Math.abs(v);
	const f = (x: number, d: number) => x.toLocaleString('uk-UA', { maximumFractionDigits: d });
	if (a >= 1e6) return `${f(v / 1e6, 1)} млн кВт·год`;
	if (a >= 1e4) return `${f(v / 1e3, 0)} тис. кВт·год`;
	return `${f(v, 0)} кВт·год`;
}
