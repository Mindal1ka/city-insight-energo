// v2 API: бюджет/ліміти, live-стан інверторів (МОК), розподіл доби, баланс мережі, звернення, звіт за місяць.
// Бекенд — backend/app/insight.py. Усе, що позначене source: 'МОК', — демонстраційні дані.

import { qs } from '#lib/api.ts';
import { req } from '#lib/api-ses.ts';
import { authToken } from '#lib/auth.svelte.ts';

export const DEPARTMENTS = [
	'Управління освіти',
	"Управління охорони здоров'я",
	'Управління культури',
	'Управління молоді та спорту',
	'Департамент ЖКГ',
	'Виконавчий комітет'
] as const;

export interface Budget {
	/** openbudget.gov.ua — реальний план програми 2026, розподілений пропорційно кВт·год; МОК — оцінка */
	source: 'МОК' | 'введено' | 'openbudget.gov.ua';
	limit_uah: { year: number; month: number; day: number };
	paid_uah: { year: number; month: number; day: number };
	/** Скільки коштувала б е/е без СЕС за рік */
	without_ses_uah_year: number;
	used_pct: { year: number | null; month: number | null };
	/** Ліміт − оплачено; < 0 — перевитрата */
	balance_uah: { year: number; month: number };
}

/** «Скільки доставити» — лише з кВт·год (без м²): панелі під K = 1 за рік, акумулятор під вечірню частку доби */
export interface Sizing {
	need: boolean;
	current_kw?: number;
	current_battery_kwh?: number;
	/** Потужність панелей, за якої річна генерація = річному споживанню */
	need_kw?: number;
	/** Ємність акумулятора під вечірнє споживання середньої доби */
	need_battery_kwh?: number;
	/** Скільки доставити (0 — не потрібно) */
	add_kw: number;
	add_battery_kwh?: number;
	cons_kwh_month_avg?: number;
	deficit_kwh_year?: number;
	gen_kwh_year_after?: number;
	self_kwh_year_after?: number;
	k_after?: number | null;
	capex_uah?: number;
	saved_uah_year?: number;
	payback_years?: number | null;
	reason?: string;
}

export interface Live {
	source: 'МОК';
	adapter: string;
	status: 'online' | 'offline';
	updated_at: string;
	gen_kw: number;
	load_kw: number;
	/** > 0 — купуємо з мережі, < 0 — віддаємо надлишок */
	grid_kw: number;
	/** > 0 — заряд, < 0 — розряд; null — немає доступу */
	battery_kw: number | null;
	soc_pct: number | null;
	today_gen_kwh: number;
	today_load_kwh: number;
}

export interface DistHour {
	hour: number;
	gen_kwh: number;
	cons_kwh: number;
	soc_pct: number | null;
	grid_kwh: number;
	surplus_kwh: number;
}

/** Вікно 3: розподіл енергії на сьогодні (з поточної години до кінця доби) */
export interface Distribution {
	hour: number;
	peak_kw: number;
	peak_hour: number;
	battery_kwh_now: number | null;
	battery_capacity_kwh: number | null;
	battery_usable_kwh: number | null;
	sun_left_kwh: number;
	demand_left_kwh: number;
	available_kwh: number;
	balance_kwh: number;
	enough: boolean;
	reserve_kwh: number;
	day_gen_kwh: number;
	day_cons_kwh: number;
	hourly: DistHour[];
}

export interface MonthRow {
	month: number;
	cons_kwh: number;
	gen_kwh: number | null;
	/** Власне споживання сонячної е/е (разом із тим, що пройшло через акумулятор) */
	self_kwh: number | null;
	/** Перенесено акумулятором з дня на вечір */
	battery_kwh: number | null;
	surplus_kwh: number | null;
	grid_kwh: number | null;
	saved_uah: number | null;
}

export interface Insight {
	demo: boolean;
	id: number;
	department: string;
	day: string;
	/** Споживання е/е по місяцях (січ…гру), кВт·год */
	monthly_kwh: number[];
	/** Помісячно (січ…гру). null-поля — немає доступу */
	months: MonthRow[];
	/** Ємність акумулятора станції, кВт·год (null — немає доступу / немає СЕС) */
	battery_capacity_kwh: number | null;
	/** Оцінка 2026 з реальних даних UMUNI і тренд до 2025 */
	y2026: Y2026;
	/** null — немає фінансового доступу */
	budget: Budget | null;
	/** null — публічний режим */
	sizing: Sizing | null;
	/** null — немає СЕС або публічний режим */
	live: Live | null;
	distribution: Distribution | null;
}

export const fetchInsight = (id: number, day?: string) => req<Insight>(`/api/insight/${id}` + qs({ day }));

export const updateLimit = (id: number, limit_uah_year: number | null) =>
	req<{ id: number; limit_uah_year: number | null; source: string }>(`/api/limits/${id}`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ limit_uah_year })
	});

// ---------- live по громаді ----------

export interface LiveItem extends Live {
	id: number;
	name: string;
	department: string;
	peak_kw: number;
	balance_kwh: number;
	enough: boolean;
}

export interface LiveAll {
	source: 'МОК';
	updated_at: string;
	totals: {
		gen_kw: number;
		load_kw: number;
		grid_kw: number;
		online: number;
		offline: number;
		available_kwh: number;
		demand_left_kwh: number;
		battery_kwh_now: number;
		balance_kwh: number;
		enough: boolean;
	};
	/** Порожній для публічного режиму */
	items: LiveItem[];
}

export const fetchLive = () => req<LiveAll>('/api/live');

// ---------- департаменти ----------

export interface DeptRow {
	department: string;
	objects: number;
	with_ses: number;
	deficit: number;
	surplus: number;
	over_limit: number;
	cons_kwh_year: number;
	gen_kwh_year: number;
	limit_uah_year: number;
	paid_uah_year: number;
	without_ses_uah_year: number;
	saved_uah_year: number;
	invested_uah: number;
	balance_uah_year: number;
	limit_uah_month: number;
	paid_uah_month: number;
	used_pct_year: number | null;
	payback_years: number | null;
}

export interface Departments {
	source: 'МОК';
	tariff_uah_kwh: number;
	month: number;
	totals: Omit<DeptRow, 'department' | 'payback_years'>;
	items: DeptRow[];
}

export const fetchDepartments = () => req<Departments>('/api/departments');

// ---------- баланс мережі (вікно 4) ----------

export interface Pair {
	from_id: number;
	from_name: string;
	to_id: number;
	to_name: string;
	same_department: boolean;
	department_from: string;
	department_to: string;
	distance_km: number | null;
	move_kw: number;
	gain_kwh_year: number;
	saved_uah_year: number;
}

export interface Network {
	demo: boolean;
	period: 'day' | 'month' | 'year';
	day: string;
	totals: {
		gen_kwh: number;
		cons_kwh: number;
		diff_kwh: number;
		k: number | null;
		surplus_kwh: number;
		grid_kwh: number;
		surplus_uah: number;
		donors: number;
		takers: number;
		pairs: number;
		move_kw: number;
	};
	/** null — публічний режим */
	pairs: Pair[] | null;
	note: string;
}

export const fetchNetwork = (period: 'day' | 'month' | 'year' = 'year') =>
	req<Network>('/api/network' + qs({ period }));

// ---------- звіт за місяць (вікно 7) ----------

export interface ReportRow {
	id: number;
	name: string;
	department: string;
	has_ses: boolean;
	cons_kwh: number;
	gen_kwh: number;
	self_kwh: number;
	surplus_kwh: number;
	grid_kwh: number;
	cost_uah: number;
	saved_uah: number;
	limit_uah: number;
	saved_uah_year: number;
	invested_uah: number;
	saved_since_launch_uah: number;
}

export interface Report {
	demo: boolean;
	month: string;
	tariff_uah_kwh: number;
	totals: Omit<ReportRow, 'id' | 'name' | 'department' | 'has_ses'> & { over_limit_uah: number; k: number | null };
	/** Порожній для публічного режиму (лише підсумки) */
	items: ReportRow[];
}

/** month — 'РРРР-ММ'; без нього — поточний */
export const fetchReport = (month?: string) => req<Report>('/api/report' + qs({ month }));

/** CSV завантажуємо через fetch (потрібен заголовок Authorization) */
export async function downloadReportCsv(month?: string): Promise<void> {
	let t: string | null = null;
	try {
		t = authToken();
	} catch {
		t = null;
	}
	const res = await fetch('/api/report.csv' + qs({ month }), { headers: t ? { Authorization: `Bearer ${t}` } : {} });
	const blob = await res.blob();
	const a = document.createElement('a');
	a.href = URL.createObjectURL(blob);
	a.download = `report-${month ?? 'current'}.csv`;
	a.click();
	URL.revokeObjectURL(a.href);
}

// ---------- звернення (вікно 6) ----------

export type AppealType = 'expand' | 'surplus' | 'over_limit' | 'repair' | 'other';
export const APPEAL_TYPES: Record<AppealType, string> = {
	expand: 'Потрібне розширення СЕС',
	surplus: 'Є надлишок — можемо передати',
	over_limit: 'Перевищення ліміту',
	repair: 'Несправність СЕС',
	other: 'Інше'
};
export const APPEAL_STATUSES = ['нове', 'в роботі', 'виконано', 'відхилено'] as const;
export type AppealStatus = (typeof APPEAL_STATUSES)[number];

export interface Appeal {
	id: number;
	building_id: number;
	building_name: string;
	type: AppealType;
	type_name: string;
	to: string;
	kw: number | null;
	text: string;
	status: AppealStatus;
	author: string;
	author_role: string;
	created_at: string;
	updated_at: string | null;
	answer?: string;
}

/** Потрібен вхід (401 для публічного режиму) */
export const fetchAppeals = () =>
	req<{ types: Record<AppealType, string>; statuses: AppealStatus[]; departments: string[]; items: Appeal[] }>(
		'/api/appeals'
	);

export const createAppeal = (body: {
	building_id: number;
	type: AppealType;
	to?: string;
	kw?: number | null;
	text?: string;
}) =>
	req<Appeal>('/api/appeals', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body)
	});

export const updateAppeal = (id: number, status: AppealStatus, answer?: string) =>
	req<Appeal>(`/api/appeals/${id}`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ status, answer })
	});

/** Сезон за місяцем (1–12) */
export function seasonOf(month: number): 'зима' | 'весна' | 'літо' | 'осінь' {
	return month <= 2 || month === 12 ? 'зима' : month <= 5 ? 'весна' : month <= 8 ? 'літо' : 'осінь';
}

// ---------- зони мапи ----------

export interface ZoneMember {
	id: number;
	name: string;
	category_short: string;
	lat: number;
	lon: number;
	department: string;
	/** donor — є надлишок, taker — бере з мережі */
	role: 'donor' | 'taker' | 'neutral' | null;
	has_ses: boolean | null;
	k_class: string | null;
	cons_kwh: number;
	gen_kwh: number | null;
	surplus_kwh: number | null;
	grid_kwh: number | null;
}

export interface Zone {
	/** id будівлі-якоря (школа / об'єкт зі СЕС) */
	id: number;
	name: string;
	lat: number;
	lon: number;
	radius_m: number;
	members: ZoneMember[];
	count: number;
	with_ses: number | null;
	status: 'surplus' | 'balanced' | 'deficit' | 'no_ses' | null;
	k: number | null;
	cons_kwh: number;
	gen_kwh: number | null;
	surplus_kwh: number | null;
	grid_kwh: number;
	self_kwh: number;
	/** Скільки надлишку можна віддати сусідам у зоні = min(Σ надлишок, Σ з мережі) */
	shareable_kwh: number | null;
	shareable_uah: number | null;
}

export interface Zones {
	demo: boolean;
	period: 'day' | 'month' | 'year';
	day: string;
	radius_m: number;
	totals: { zones: number; buildings: number; shareable_kwh: number | null; with_share: number | null };
	items: Zone[];
}

export const fetchZones = (period: 'day' | 'month' | 'year' = 'month', day?: string) =>
	req<Zones>('/api/zones' + qs({ period, day }));

// ---------- генератори і блекаут (лише ролі з повним доступом; інакше 403) ----------

export interface Generator {
	generator_kw: number;
	fuel: string;
	tank_l: number;
	source: 'МОК' | 'введено';
	cost_uah?: number | null;
	bought?: string | null;
	doc?: string | null;
}

/** Витрати на генератор: вкладено (введено або оцінка) і пальне за рік (журнал або оцінка) */
export interface GenMoney {
	capex_uah: number;
	capex_source: 'МОК' | 'введено';
	bought: string | null;
	doc: string | null;
	fuel_year: number;
	fuel_year_l: number;
	fuel_year_uah: number;
	fuel_source: 'МОК' | 'журнал';
	fuel_entries: number;
}

export interface FuelEntry {
	id: number;
	building_id: number;
	date: string;
	liters: number;
	uah: number;
	note: string;
}

export interface Blackout {
	id: number;
	source: 'МОК';
	load_kw_avg: number;
	battery_kwh_now: number | null;
	battery_capacity_kwh: number | null;
	/** Години автономії: лише акумулятор */
	hours_battery: number;
	/** Акумулятор + сонце */
	hours_battery_sun: number;
	/** Акумулятор + сонце + генератор (через вхід генератора інвертора); null — генератора немає */
	hours_with_generator: number | null;
	/** Горизонт моделі, год (48 = «протримається»). */
	horizon_h: number;
	generator: Generator | null;
	generator_charges_battery: boolean;
	generator_full_charge_h: number | null;
	generator_cost_uah_kwh: number | null;
	fuel_l_per_day: number | null;
	fuel_used_l: number | null;
	assumptions: Record<string, number>;
	money: GenMoney | null;
	fuel_log: FuelEntry[];
	can_edit: boolean;
}

export const fetchBlackout = (id: number) => req<Blackout>(`/api/blackout/${id}`);

export const updateGenerator = (
	id: number,
	body: { generator_kw: number; tank_l: number; fuel?: string; cost_uah?: number | null; bought?: string | null; doc?: string | null }
) =>
	req<Blackout>(`/api/generator/${id}`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body)
	});

export interface BlackoutRow {
	id: number;
	name: string;
	department: string;
	has_ses: boolean;
	battery_kwh: number | null;
	generator_kw: number | null;
	generator_source: string | null;
	hours_battery_sun: number;
	hours_with_generator: number | null;
	load_kw_avg: number;
}

export const fetchBlackoutAll = () =>
	req<{
		source: 'МОК';
		updated_at: string;
		horizon_h: number;
		totals: { objects: number; with_generator: number; with_battery: number; hold_24h: number; under_4h: number; outage_today_h: number | null; hold_today: number };
		items: BlackoutRow[];
	}>('/api/blackout');

// ---------- реальні дані: оцінка 2026 з UMUNI і бюджет openbudget ----------

/** Оцінка 2026 з реальних даних UMUNI (з 1 січня до дати вивантаження) і тренд до 2025 */
export interface Y2026 {
	kwh_2025: number | null;
	kwh_2026_to_date: number | null;
	/** Дата вивантаження 2026 (ISO) */
	to_date: string | null;
	kwh_2026_est: number | null;
	/** % до 2025 (null — немає даних) */
	trend_pct: number | null;
	quality: 'ок' | 'ймовірна помилка даних' | 'немає даних' | 'немає даних 2026' | 'немає 2025';
	months_2026: { month: number; kwh: number; kind: 'оцінка факту' | 'прогноз' }[] | null;
}

export interface Trend {
	to_date: string | null;
	objects: number;
	kwh_2025: number;
	kwh_2026_est: number;
	trend_pct: number | null;
	growing: number;
	falling: number;
	suspicious: number;
	top_growth: { id: number; name: string; trend_pct: number; kwh_2025: number; kwh_2026_est: number }[];
}

export const fetchTrend = () => req<Trend>('/api/trend');

export interface BudgetProgram {
	/** Код програми ТПКВКМБ (1021 — школи, 1010 — садки, …) */
	program: string;
	name: string;
	/** Будівель UMUNI, віднесених до програми */
	buildings: number;
	kwh_2025: number | null;
	plan_2025: number | null;
	fact_2025: number | null;
	plan_2026: number | null;
	/** Касове виконання 2026 наростаючим до fact_2026_month */
	fact_2026: number | null;
	fact_2026_month: number | null;
	/** Фактична ціна 2025 = факт ÷ кВт·год UMUNI групи */
	price_2025: number | null;
	/** Ліміт програми розподілено на будівлі (будівлі UMUNI покривають програму) */
	allocated: boolean;
	monthly_2025: (number | null)[] | null;
	monthly_2026: (number | null)[] | null;
}

export interface BudgetReal {
	source: 'openbudget.gov.ua';
	budget_code: string;
	kekv: string;
	updated_month_2026: number | null;
	totals: { plan_2025: number; fact_2025: number; plan_2026: number; fact_2026: number; price_2025: number | null };
	items: BudgetProgram[];
}

export const fetchBudgetReal = () => req<BudgetReal>('/api/budget-real');

// ---------- графіки відключень ПОЕ і реальні платежі (spending.gov.ua) ----------

export interface OutageDay {
	day: string;
	hours_off: number;
	hours_maybe: number;
	longest_off_h: number;
	longest_with_maybe_h: number;
	off: string[];
	/** 48 півгодин: 1 — світло, 2 — відключення, 3 — можливе */
	cells: number[];
	updated: string | null;
}

export interface Outages {
	status: 'онлайн' | 'кеш' | 'збережений кеш' | 'недоступно';
	source?: string;
	updated?: string | null;
	days: string[];
	queues: { queue: string; now: string | null; days: OutageDay[] }[];
	/** Найдовше безперервне відключення сьогодні серед черг, год */
	worst_longest_h: number | null;
	worst_hours_off: number | null;
}

export const fetchOutages = () => req<Outages>('/api/outages');

export interface SpendingMonth {
	payer_edrpou: string;
	payer: string;
	year: number;
	month: number;
	'енергія': number;
	'розподіл': number;
	'інше': number;
	total: number;
}

export interface Spending {
	source: 'spending.gov.ua';
	kekv: string;
	payers: { edrpou: string; name: string }[];
	years: Record<string, { 'енергія': number; 'розподіл': number; 'інше': number; total: number; distribution_share_pct: number | null }>;
	items: SpendingMonth[];
}

export const fetchSpending = () => req<Spending>('/api/spending');

// ---------- облік генераторів: пальне і зведення витрат ----------

export const addFuel = (id: number, body: { date: string; liters: number; uah?: number; note?: string }) =>
	req<Blackout>(`/api/generator/${id}/fuel`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body)
	});

export const deleteFuel = (id: number, eid: number) => req<Blackout>(`/api/generator/${id}/fuel/${eid}`, { method: 'DELETE' });

export interface GenSummaryItem extends GenMoney {
	id: number;
	name: string;
	department: string;
	generator_kw: number;
	generator_source: 'МОК' | 'введено';
}
export interface GenSummary {
	year: number;
	totals: {
		count: number;
		kw: number;
		capex_uah: number;
		capex_real: number;
		fuel_year_uah: number;
		fuel_year_l: number;
		fuel_real: number;
	};
	departments: { department: string; count: number; kw: number; capex_uah: number; fuel_year_uah: number }[];
	items: GenSummaryItem[];
	assumptions: Record<string, number | number[]>;
}
/** Зведення витрат на генератори (енергоменеджер, адміністратор даних, фінанси; інакше 403) */
export const fetchGenerators = () => req<GenSummary>('/api/generators');
