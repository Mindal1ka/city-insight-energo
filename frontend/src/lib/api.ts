// Клієнт API бекенду (FastAPI). Усі шляхи відносні: у розробці працює проксі Vite, у продакшні — той самий сервер.

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

export interface UploadResult {
	ok: boolean;
	kind: string;
	summary: Summary;
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

export async function getJSON<T>(url: string): Promise<T> {
	let res: Response;
	try {
		res = await fetch(url, { headers: { Accept: 'application/json' } });
	} catch {
		throw new ApiError(0, NO_SERVER);
	}
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

export const api = {
	summary: () => getJSON<Summary>('/api/summary'),
	buildings: (category?: string) => getJSON<Building[]>('/api/buildings' + qs({ category })),
	building: (id: string | number) =>
		getJSON<BuildingFull>(`/api/buildings/${encodeURIComponent(id)}`),
	defects: () => getJSON<Defect[]>('/api/defects'),
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
