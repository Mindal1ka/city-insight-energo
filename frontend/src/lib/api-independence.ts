// Енергонезалежність: індекс закладів, зведення громади й симуляція відключення світла.
// Поки бекенд не віддає ці методи (404 «Невідомий метод API»), підставляємо локальний макет,
// щоб екрани можна було перевірити. Щойно ендпоінт з'являється, використовуються справжні дані.
import { api, ApiError, getJSON, qs, VIEWS, type SiteItem, type ViewKey } from './api.ts';

export type IndexClass = 'висока' | 'середня' | 'низька' | 'відсутня';

export interface IndependenceItem {
	id: number;
	name: string;
	address: string;
	category_short: string;
	critical: boolean;
	has_ses: boolean;
	ses_kw: number | null;
	battery_kwh: number | null;
	elec_kwh_year: number | null;
	/** частка річної електроенергії, яку дає власне сонце, % */
	self_sufficiency_pct: number | null;
	/** скільки годин тримає акумулятор без сонця (ніч, середнє навантаження) */
	autonomy_hours: number | null;
	/** скільки годин тримає акумулятор + сонце (типовий день) */
	autonomy_hours_with_sun: number | null;
	index: number;
	index_class: IndexClass;
	/** рекомендована потужність СЕС під власне споживання (усього) */
	potential_kw: number | null;
	potential_self_sufficiency_pct: number | null;
	/** скільки кВт додати до наявної СЕС */
	potential_add_kw?: number | null;
	potential_cost_uah?: number | null;
	potential_payback_years?: number | null;
	has_battery?: boolean;
	/** автономність із сонцем обмежена горизонтом розрахунку (тобто «понад») */
	autonomy_with_sun_capped?: boolean;
	/** false — у UMUNI немає річного споживання, індекс не розраховано */
	data_ok?: boolean;
	priority_rank?: number;
}

/** Скільки кВт СЕС ще додати закладу */
export function addKw(i: IndependenceItem): number {
	return Math.max(0, i.potential_add_kw ?? i.potential_kw ?? 0);
}

export interface IndependenceCommunity {
	sites: number;
	ses_sites: number;
	ses_kw_total: number;
	battery_kwh_total: number;
	elec_kwh_year_2025: number;
	solar_kwh_year_est: number;
	self_sufficiency_pct: number;
	autonomy_hours_median: number | null;
	critical_sites_total: number;
	critical_with_ses: number;
	critical_with_battery: number;
	potential_kw: number;
	potential_self_sufficiency_pct: number;
	potential_cost_uah: number;
	battery_sites?: number;
	potential_sites?: number;
}

export interface IndependenceCategory {
	category_short: string;
	sites: number;
	with_ses: number;
	self_sufficiency_pct: number | null;
	autonomy_hours_median: number | null;
	potential_kw: number | null;
}

export interface IndependenceList {
	demo: boolean;
	now: string;
	community: IndependenceCommunity;
	categories: IndependenceCategory[];
	items: IndependenceItem[];
	notes?: string[];
	/** Як рахується індекс (текст для блоку «Як ми рахуємо») */
	formula?: { text: string; weights?: Record<string, number> };
	/** true — показано локальний макет (бекенд ще не віддає метод) */
	mock?: boolean;
}

export interface Improvement {
	action: string;
	effect: string;
	kw: number | null;
	battery_kwh: number | null;
	cost_uah: number | null;
	payback_years: number | null;
	priority: number | string;
}

export interface IndependenceDetail {
	demo: boolean;
	now: string;
	item: IndependenceItem;
	explain: string[];
	improve: Improvement[];
	formula: { text: string; weights?: Record<string, number> };
	notes?: string[];
	mock?: boolean;
}

export interface OutageHour {
	hour: number;
	load_kwh: number;
	solar_kwh: number;
	battery_kwh_after: number;
	from_battery_kwh: number;
	covered: boolean;
}

export interface OutageResult {
	demo: boolean;
	day: string;
	start_hour: number;
	hours: number;
	timeline: OutageHour[];
	survives_hours: number;
	survives_all: boolean;
	unmet_kwh: number;
	note: string;
	soc_start_pct?: number | null;
	mock?: boolean;
}

// ---------- запити ----------

function dayHour(view?: ViewKey): { day?: string; hour?: number } {
	const v = VIEWS[view ?? 'now'];
	return { day: v.day, hour: v.hour };
}

/** Метод ще не реалізовано на бекенді (SPA-заглушка відповідає 404 «Невідомий метод API») */
function missing(e: unknown): boolean {
	return (
		e instanceof ApiError &&
		e.status === 404 &&
		(e.message === 'Невідомий метод API' || e.message === 'Ендпоінт ще не реалізовано' || e.message === 'Not Found')
	);
}

export const independenceApi = {
	async list(view?: ViewKey): Promise<IndependenceList> {
		try {
			return await getJSON<IndependenceList>('/api/independence' + qs(dayHour(view)));
		} catch (e) {
			if (!missing(e)) throw e;
			return mockList(view);
		}
	},
	async one(id: string | number, view?: ViewKey): Promise<IndependenceDetail> {
		try {
			return await getJSON<IndependenceDetail>(
				`/api/independence/${encodeURIComponent(id)}` + qs(dayHour(view))
			);
		} catch (e) {
			if (!missing(e)) throw e;
			return mockOne(Number(id), view);
		}
	},
	async outage(
		id: string | number,
		p: { day?: string | null; start_hour: number; hours: number }
	): Promise<OutageResult> {
		try {
			return await getJSON<OutageResult>(`/api/sites/${encodeURIComponent(id)}/outage` + qs(p));
		} catch (e) {
			if (!missing(e)) throw e;
			return mockOutage(Number(id), p);
		}
	}
};

// ---------- форматування ----------

function plural(n: number, one: string, few: string, many: string): string {
	const a = Math.abs(n) % 100;
	const b = a % 10;
	if (a > 10 && a < 20) return many;
	if (b === 1) return one;
	if (b >= 2 && b <= 4) return few;
	return many;
}

/** Години → «3 год 20 хв», «45 хв», «1 доба 4 год», «понад 3 доби» */
export function duration(h: number | null | undefined): string {
	if (h === null || h === undefined || Number.isNaN(h)) return '—';
	if (!Number.isFinite(h) || h > 72) return 'понад 3 доби';
	if (h <= 0) return '0 хв';
	let mins = Math.round(h * 60);
	if (mins < 60) return `${mins} хв`;
	if (mins >= 24 * 60) {
		const d = Math.floor(mins / (24 * 60));
		const rh = Math.round((mins - d * 24 * 60) / 60);
		const ds = `${d} ${plural(d, 'доба', 'доби', 'діб')}`;
		return rh ? `${ds} ${rh} год` : ds;
	}
	// округлюємо до 10 хв, щоб не створювати хибної точності
	mins = Math.round(mins / 10) * 10;
	const hh = Math.floor(mins / 60);
	const mm = mins % 60;
	return mm ? `${hh} год ${mm} хв` : `${hh} год`;
}

/** Гривні: «1,2 млн грн», «850 тис. грн», «12 400 грн» */
export function money(uah: number | null | undefined): string {
	if (uah === null || uah === undefined || Number.isNaN(uah)) return '—';
	const f = (v: number, d: number) =>
		new Intl.NumberFormat('uk-UA', { minimumFractionDigits: 0, maximumFractionDigits: d }).format(v);
	if (Math.abs(uah) >= 1e6) return `${f(uah / 1e6, 1)} млн грн`;
	if (Math.abs(uah) >= 1e4) return `${f(uah / 1e3, 0)} тис. грн`;
	return `${f(uah, 0)} грн`;
}

/** Роки окупності: «6,5 року», «4 роки» */
export function years(y: number | null | undefined): string {
	if (y === null || y === undefined || Number.isNaN(y)) return '—';
	const r = Math.round(y * 10) / 10;
	const s = new Intl.NumberFormat('uk-UA', { maximumFractionDigits: 1 }).format(r);
	if (!Number.isInteger(r)) return `${s} року`;
	return `${s} ${plural(r, 'рік', 'роки', 'років')}`;
}

export const CRITICAL_HINT =
	'Критичні заклади (охорона здоров’я) мають працювати без перерви: їм резерв потрібен насамперед.';

/** Порядок важливості категорій: лікарні, далі школи й садки */
export function categoryRank(cat: string): number {
	if (cat === 'Охорона здоров’я' || cat === "Охорона здоров'я") return 0;
	if (cat === 'Заклади освіти') return 1;
	if (cat === 'Дошкільні заклади') return 2;
	return 3;
}

export const CLASS_ORDER: IndexClass[] = ['відсутня', 'низька', 'середня', 'висока'];

// ---------- локальний макет (до появи методів на бекенді) ----------

function rnd(seed: string): () => number {
	let h = 2166136261;
	for (let i = 0; i < seed.length; i++) h = Math.imul(h ^ seed.charCodeAt(i), 16777619);
	return () => {
		h += 0x6d2b79f5;
		let t = h;
		t = Math.imul(t ^ (t >>> 15), t | 1);
		t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

function classOf(i: number): IndexClass {
	if (i <= 0) return 'відсутня';
	if (i < 40) return 'низька';
	if (i < 70) return 'середня';
	return 'висока';
}

function mockItem(s: SiteItem): IndependenceItem {
	const r = rnd(`ind-${s.id}`);
	const critical = s.category_short.startsWith('Охорона');
	const elec = Math.round(8000 + r() * 160000);
	const battery = s.has_ses ? Math.round((s.ses_kw ?? 10) * (0.8 + r() * 1.5)) : r() < 0.12 ? 10 : 0;
	const avgKw = elec / 8760;
	const self = s.has_ses ? Math.min(45, ((s.ses_kw ?? 0) * 1150 * 0.85 * 100) / elec) : 0;
	const aut = battery ? (battery * 0.9) / Math.max(0.5, avgKw * (critical ? 1.1 : 0.7)) : 0;
	const autSun = s.has_ses ? aut + 4 + r() * 6 : aut;
	const index = Math.round(
		Math.min(100, (self / 40) * 45 + Math.min(1, aut / 12) * 40 + (critical && battery ? 15 : battery ? 10 : 0))
	);
	const potKw = Math.round(Math.max(5, (elec * 0.3) / 1150));
	return {
		id: s.id,
		name: s.name,
		address: s.address,
		category_short: s.category_short,
		critical,
		has_ses: s.has_ses,
		ses_kw: s.ses_kw,
		battery_kwh: battery,
		elec_kwh_year: elec,
		self_sufficiency_pct: Math.round(self * 10) / 10,
		autonomy_hours: Math.round(aut * 10) / 10,
		autonomy_hours_with_sun: Math.round(autSun * 10) / 10,
		index,
		index_class: classOf(index),
		potential_kw: s.has_ses ? Math.max(0, potKw - (s.ses_kw ?? 0)) || null : potKw,
		potential_self_sufficiency_pct: 28 + Math.round(r() * 6)
	};
}

function median(a: number[]): number | null {
	if (!a.length) return null;
	const s = [...a].sort((x, y) => x - y);
	const m = s.length >> 1;
	return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

async function mockList(view?: ViewKey): Promise<IndependenceList> {
	console.warn('[independence] бекенд ще не віддає /api/independence — показано локальний макет');
	const sites = await api.sites(view);
	const items = sites.items.map(mockItem);
	const sum = (f: (i: IndependenceItem) => number | null) => items.reduce((a, i) => a + (f(i) ?? 0), 0);
	const elec = sum((i) => i.elec_kwh_year);
	const solar = sum((i) => ((i.self_sufficiency_pct ?? 0) / 100) * (i.elec_kwh_year ?? 0));
	const potKw = sum((i) => i.potential_kw);
	const crit = items.filter((i) => i.critical);
	const cats = new Map<string, IndependenceItem[]>();
	for (const i of items) cats.set(i.category_short, [...(cats.get(i.category_short) ?? []), i]);
	return {
		demo: true,
		now: sites.now,
		mock: true,
		community: {
			sites: items.length,
			ses_sites: items.filter((i) => i.has_ses).length,
			ses_kw_total: sum((i) => i.ses_kw),
			battery_kwh_total: sum((i) => i.battery_kwh),
			elec_kwh_year_2025: elec,
			solar_kwh_year_est: solar,
			self_sufficiency_pct: (solar / elec) * 100,
			autonomy_hours_median: median(items.filter((i) => i.battery_kwh).map((i) => i.autonomy_hours ?? 0)),
			critical_sites_total: crit.length,
			critical_with_ses: crit.filter((i) => i.has_ses).length,
			critical_with_battery: crit.filter((i) => i.battery_kwh).length,
			potential_kw: potKw,
			potential_self_sufficiency_pct: ((solar + potKw * 1150 * 0.85) / elec) * 100,
			potential_cost_uah: potKw * 32000
		},
		categories: [...cats.entries()].map(([c, l]) => ({
			category_short: c,
			sites: l.length,
			with_ses: l.filter((i) => i.has_ses).length,
			self_sufficiency_pct:
				(l.reduce((a, i) => a + ((i.self_sufficiency_pct ?? 0) / 100) * (i.elec_kwh_year ?? 0), 0) /
					Math.max(1, l.reduce((a, i) => a + (i.elec_kwh_year ?? 0), 0))) *
				100,
			autonomy_hours_median: median(l.filter((i) => i.battery_kwh).map((i) => i.autonomy_hours ?? 0)),
			potential_kw: l.reduce((a, i) => a + (i.potential_kw ?? 0), 0)
		})),
		items
	};
}

async function mockOne(id: number, view?: ViewKey): Promise<IndependenceDetail> {
	const l = await mockList(view);
	const item = l.items.find((i) => i.id === id);
	if (!item) throw new ApiError(404, 'Об’єкт не знайдено');
	const improve: Improvement[] = [];
	if (!item.battery_kwh)
		improve.push({
			action: 'Поставити акумулятор 20 кВт·год',
			effect: 'Заклад протримається без світла близько 4 год замість 0',
			kw: null,
			battery_kwh: 20,
			cost_uah: 240000,
			payback_years: null,
			priority: 1
		});
	if (item.potential_kw)
		improve.push({
			action: `${item.has_ses ? 'Розширити' : 'Встановити'} СЕС на ${item.potential_kw} кВт`,
			effect: `Сонце покриватиме ${item.potential_self_sufficiency_pct} % електроенергії замість ${Math.round(item.self_sufficiency_pct ?? 0)} %`,
			kw: item.potential_kw,
			battery_kwh: null,
			cost_uah: item.potential_kw * 32000,
			payback_years: 6.5,
			priority: 2
		});
	improve.push({
		action: 'Перевести освітлення на LED і вимикати техніку на ніч',
		effect: 'Менше навантаження — акумулятор тримає на 20–30 % довше',
		kw: null,
		battery_kwh: null,
		cost_uah: 60000,
		payback_years: 2,
		priority: 3
	});
	return {
		demo: true,
		now: l.now,
		mock: true,
		item,
		explain: [
			`Сонце дає ${Math.round(item.self_sufficiency_pct ?? 0)} % річної електроенергії закладу.`,
			item.battery_kwh
				? `Акумулятор ${item.battery_kwh} кВт·год тримає заклад уночі приблизно ${duration(item.autonomy_hours)}.`
				: 'Акумулятора немає: у разі відключення світла заклад зупиняється одразу.',
			item.critical ? 'Заклад критичний — резерв для нього важливіший, ніж для інших.' : 'Заклад не критичний.'
		],
		improve,
		formula: {
			text: 'Індекс = 45 % × частка власної генерації + 40 % × автономність (до 12 год) + 15 % × наявність резерву',
			weights: { 'частка власної генерації': 0.45, автономність: 0.4, резерв: 0.15 }
		}
	};
}

async function mockOutage(
	id: number,
	p: { day?: string | null; start_hour: number; hours: number }
): Promise<OutageResult> {
	const one = await mockOne(id, 'now');
	const it = one.item;
	const avg = (it.elec_kwh_year ?? 20000) / 8760;
	let bat = (it.battery_kwh ?? 0) * 0.8;
	const timeline: OutageHour[] = [];
	let survives = 0;
	let broke = false;
	let unmet = 0;
	for (let k = 0; k < p.hours; k++) {
		const hour = (p.start_hour + k) % 24;
		const day = hour >= 8 && hour < 18;
		const load = avg * (day ? 1.4 : 0.6);
		const sunF = Math.max(0, Math.sin(((hour - 6) / 13) * Math.PI));
		const solar = it.has_ses ? Math.min(load * 1.6, (it.ses_kw ?? 0) * sunF * 0.55) : 0;
		const need = Math.max(0, load - solar);
		const fromBat = Math.min(bat, need);
		bat = Math.min((it.battery_kwh ?? 0) * 0.9, bat - fromBat + Math.max(0, solar - load));
		const covered = fromBat + Math.min(solar, load) >= load - 1e-6;
		if (!covered) unmet += load - fromBat - Math.min(solar, load);
		if (!broke) {
			if (covered) survives += 1;
			else {
				survives += (fromBat + Math.min(solar, load)) / load;
				broke = true;
			}
		}
		timeline.push({
			hour,
			load_kwh: load,
			solar_kwh: solar,
			battery_kwh_after: bat,
			from_battery_kwh: fromBat,
			covered
		});
	}
	return {
		demo: true,
		day: p.day ?? '2026-11-19',
		start_hour: p.start_hour,
		hours: p.hours,
		timeline,
		survives_hours: survives,
		survives_all: !broke,
		unmet_kwh: unmet,
		note: 'Макет розрахунку: середнє навантаження за рік, акумулятор заряджений на 80 %.',
		mock: true
	};
}
