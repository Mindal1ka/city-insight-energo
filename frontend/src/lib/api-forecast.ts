// Прогноз сонячної генерації на 3 дні: GET /api/forecast?days=3
// Якщо ендпоінт ще не готовий (404 / не JSON), повертаємо позначені демонстраційні дані,
// щоб картка не була порожньою. Один запит на всі картки сторінки (кеш на 10 хвилин).
import { getJSON, ApiError } from './api.ts';

export type ForecastWeather = 'сонячно' | 'мінлива хмарність' | 'похмуро';

export interface ForecastHour {
	hour: number;
	gti_wm2: number;
	cloud_pct: number;
	temp_c: number;
	gen_kwh_per_kwp: number;
}

export interface ForecastDay {
	date: string;
	label: 'сьогодні' | 'завтра' | 'післязавтра' | string;
	hourly: ForecastHour[];
	gen_kwh_per_kwp_day: number;
	pvgis_avg_kwh_per_kwp_day: number;
	/** частка від багаторічної норми PVGIS (1 = як зазвичай) */
	ratio_to_normal: number | null;
	weather: ForecastWeather | string;
	sun_hours: number;
}

export interface Forecast {
	source: string;
	stale: boolean;
	fetched_at: string | null;
	location?: { lat?: number; lon?: number; name?: string } | string | null;
	days: ForecastDay[];
	/** true — це демонстраційні дані фронтенду (бекенд ще не віддає прогноз) */
	demo?: boolean;
}

const TTL_MS = 10 * 60 * 1000;
let cached: { at: number; p: Promise<Forecast> } | null = null;

export function getForecast(force = false): Promise<Forecast> {
	if (!force && cached && Date.now() - cached.at < TTL_MS) return cached.p;
	const p = getJSON<Forecast>('/api/forecast?days=3').catch((e: unknown) => {
		if (e instanceof ApiError && (e.status === 404 || e.status === 501)) return mockForecast();
		cached = null; // помилку не кешуємо — наступна картка спробує ще раз
		throw e;
	});
	cached = { at: Date.now(), p };
	return p;
}

/** Частка від норми: беремо з API, а якщо її немає — рахуємо самі */
export function ratioOf(d: ForecastDay): number | null {
	if (d.ratio_to_normal !== null && d.ratio_to_normal !== undefined) {
		// захист від відсотків замість частки
		return d.ratio_to_normal > 5 ? d.ratio_to_normal / 100 : d.ratio_to_normal;
	}
	if (d.pvgis_avg_kwh_per_kwp_day > 0) return d.gen_kwh_per_kwp_day / d.pvgis_avg_kwh_per_kwp_day;
	return null;
}

export function locationName(f: Forecast): string {
	const l = f.location;
	if (!l) return 'Полтава';
	if (typeof l === 'string') return l;
	return l.name ?? 'Полтава';
}

// ——— Демонстраційні дані (лише поки немає ендпоінту) ———

function mockDay(offset: number, label: ForecastDay['label'], clouds: number): ForecastDay {
	const d = new Date();
	d.setDate(d.getDate() + offset);
	const iso = d.toISOString().slice(0, 10);
	// Листопад у Полтаві: світловий день ≈ 7:00–16:30, полудень ≈ 11:40
	const hourly: ForecastHour[] = [];
	for (let h = 0; h < 24; h++) {
		const x = (h + 0.5 - 11.7) / 4.6;
		const clear = Math.abs(x) < 1 ? Math.cos((x * Math.PI) / 2) ** 1.4 * 560 : 0;
		const wobble = 0.85 + 0.15 * Math.sin(h * 1.7 + offset * 2);
		const gti = Math.max(0, clear * (1 - 0.8 * clouds) * wobble);
		hourly.push({
			hour: h,
			gti_wm2: Math.round(gti),
			cloud_pct: Math.round(clouds * 100),
			temp_c: Math.round(2 + 4 * Math.max(0, 1 - Math.abs(x))),
			gen_kwh_per_kwp: +((gti / 1000) * 0.86).toFixed(3)
		});
	}
	const gen = +hourly.reduce((s, h) => s + h.gen_kwh_per_kwp, 0).toFixed(2);
	const normal = 1.32;
	return {
		date: iso,
		label,
		hourly,
		gen_kwh_per_kwp_day: gen,
		pvgis_avg_kwh_per_kwp_day: normal,
		ratio_to_normal: +(gen / normal).toFixed(2),
		weather: clouds < 0.3 ? 'сонячно' : clouds < 0.7 ? 'мінлива хмарність' : 'похмуро',
		sun_hours: +hourly.filter((h) => h.gti_wm2 > 120).length.toFixed(0)
	};
}

function mockForecast(): Forecast {
	return {
		source: 'демонстраційні дані',
		stale: false,
		fetched_at: new Date().toISOString(),
		location: { name: 'Полтава', lat: 49.589, lon: 34.551 },
		days: [mockDay(0, 'сьогодні', 0.55), mockDay(1, 'завтра', 0.15), mockDay(2, 'післязавтра', 0.85)],
		demo: true
	};
}
