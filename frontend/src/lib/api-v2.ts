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
	source: 'МОК' | 'введено';
	limit_uah: { year: number; month: number; day: number };
	paid_uah: { year: number; month: number; day: number };
	/** Скільки коштувала б е/е без СЕС за рік */
	without_ses_uah_year: number;
	used_pct: { year: number | null; month: number | null };
	/** Ліміт − оплачено; < 0 — перевитрата */
	balance_uah: { year: number; month: number };
}

export interface Sizing {
	need: boolean;
	current_kw?: number;
	/** Скільки кВт доставити (0 — не потрібно) */
	add_kw: number;
	roof_max_kw?: number;
	to_k1_kw?: number;
	limited_by?: 'дах' | 'споживання';
	deficit_kwh_year?: number;
	gain_kwh_year?: number;
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

export interface Insight {
	demo: boolean;
	id: number;
	department: string;
	day: string;
	/** Споживання е/е по місяцях (січ…гру), кВт·год */
	monthly_kwh: number[];
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
