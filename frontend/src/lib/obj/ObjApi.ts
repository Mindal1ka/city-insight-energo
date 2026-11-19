// Дані картки об'єкта: GET/PUT /api/ses/{id}. Поки бекенд не готовий — синтетика (ДЕМО)
// з /api/sites/{id} + /api/buildings/{id}, щоб сторінка працювала.
import { getJSON, ApiError, type SiteDetail, type BuildingFull } from '#lib/api.ts';

import {
	fetchSesDetail,
	updateSes,
	classifyK,
	THRESHOLDS,
	type Period,
	type KClass,
	type SesInfo,
	type SesCosts,
	type EnergyBlock,
	type SesDetail,
	type SesUpdate
} from '#lib/api-ses.ts';

export type { Period, KClass };
export type ObjSes = SesInfo;
export type ObjCosts = SesCosts;
export type ObjEnergy = EnergyBlock;
export type ObjDetail = SesDetail & {
	/** Рівень доступу з бекенду: 'full' — усе, 'ses' — без акумуляторів, 'public' — без СЕС */
	access?: 'full' | 'ses' | 'public';
	notes?: string[];
	/** true — відповідь синтезована у фронтенді (бекенд /api/ses ще не відповідає) */
	mock?: boolean;
};

export const K_LOW = THRESHOLDS.low;
export const K_HIGH = THRESHOLDS.high;
export function kClassOf(k: number | null, hasSes: boolean, hasData: boolean): KClass {
	if (!hasSes) return 'Без СЕС';
	if (!hasData) return 'Немає даних';
	return classifyK(k, true);
}

/** Чи бекенд уже має /api/ses/{id} (кешуємо на сесію) */
let backendMissing = false;

export async function loadObj(id: string): Promise<ObjDetail> {
	if (!backendMissing) {
		try {
			return await fetchSesDetail(Number(id));
		} catch (e) {
			// 404 «невідомий метод» / SPA-відповідь → ендпоінту ще немає; 404 по об'єкту — справжня помилка
			if (!(e instanceof ApiError) || e.status !== 404 || !/метод|реалізовано|Not Found/i.test(e.message)) throw e;
			backendMissing = true;
		}
	}
	return mockObj(id);
}

export type ObjPatch = SesUpdate;

export async function saveObj(id: string | number, patch: ObjPatch, mock: boolean): Promise<ObjDetail | null> {
	if (mock) {
		// Демо без бекенду: зберігаємо локально, щоб зміни переживали перезавантаження
		try {
			const all = JSON.parse(localStorage.getItem(LS) ?? '{}');
			all[id] = { ...(all[id] ?? {}), ...patch };
			localStorage.setItem(LS, JSON.stringify(all));
		} catch {
			/* без сховища — лише в пам'яті */
		}
		await new Promise((r) => setTimeout(r, 350));
		return null;
	}
	return updateSes(Number(id), patch);
}

// ======================= Синтетика (ДЕМО) =======================
const LS = 'energo.obj.edits';
/** Частка річної генерації 1 кВт у Полтаві помісячно (PVGIS, ≈1150 кВт·год/кВт) */
const PV = [32, 52, 92, 125, 150, 155, 160, 146, 105, 70, 36, 25];
/** Сезонність споживання школи/лікарні (частка від року) */
const CONS = [0.105, 0.095, 0.09, 0.08, 0.075, 0.065, 0.055, 0.06, 0.08, 0.09, 0.1, 0.105];

function edits(id: string): ObjPatch {
	try {
		return JSON.parse(localStorage.getItem(LS) ?? '{}')[id] ?? {};
	} catch {
		return {};
	}
}

async function mockObj(id: string): Promise<ObjDetail> {
	const [site, bld] = await Promise.all([
		getJSON<SiteDetail>(`/api/sites/${encodeURIComponent(id)}`).catch((e) => {
			if (e instanceof ApiError && e.status === 404) return null;
			throw e;
		}),
		getJSON<BuildingFull>(`/api/buildings/${encodeURIComponent(id)}`).catch(() => null)
	]);
	if (!site && !bld) throw new ApiError(404, 'Об’єкт не знайдено');
	const ed = edits(id);
	const s0 = site?.ses ?? null;
	const tariff = site?.limits.tariff_uah_kwh ?? 8;
	let ses: ObjSes | null = s0
		? {
				panels_count: s0.panels_count,
				panel_w: s0.panel_w,
				total_kw: s0.total_kw,
				inverter_model: s0.inverter_model,
				inverter_kw: s0.inverter_kw,
				battery_count: s0.battery_kwh > 0 ? Math.round(s0.battery_kwh / 5.12) : 0,
				battery_module_kwh: s0.battery_kwh > 0 ? 5.12 : null,
				battery_kwh: s0.battery_kwh,
				battery_kw: s0.battery_kw,
				connected_kw: s0.connected_kw,
				launched: s0.launched,
				source: 'ДЕМО'
			}
		: null;
	let costs: ObjCosts | null = ses
		? {
				panels_uah: Math.round((ses.total_kw ?? 0) * 11500),
				inverter_uah: Math.round((ses.inverter_kw ?? 0) * 9800),
				batteries_uah: Math.round((ses.battery_kwh ?? 0) * 13500),
				install_uah: Math.round((ses.total_kw ?? 0) * 4200),
				total_uah: null
			}
		: null;
	const sesKeys = Object.keys(ed).filter((k) => !k.endsWith('_uah'));
	if (sesKeys.length) {
		ses = { ...(ses ?? emptySes()), ...pick(ed, sesKeys), source: 'введено' } as ObjSes;
	}
	const costKeys = Object.keys(ed).filter((k) => k.endsWith('_uah'));
	if (costKeys.length) costs = { ...(costs ?? emptyCosts()), ...pick(ed, costKeys) } as ObjCosts;
	if (ses) ses = normSes(ses);
	if (costs) costs = normCosts(costs);

	const yearCons = bld?.years?.['2025']?.elec_kwh ?? site?.building.elec_kwh_2025 ?? null;
	const kw = ses?.total_kw ?? 0;
	const monthly = PV.map((p, i) => {
		const gen = ses ? Math.round(p * kw) : null;
		const cons = yearCons ? Math.round(yearCons * CONS[i]) : null;
		return { month: i + 1, gen_kwh: gen, cons_kwh: cons, k: gen !== null && cons ? +(gen / cons).toFixed(2) : null };
	});
	const now = new Date();
	const mi = now.getMonth();
	const sum = (a: (number | null)[]) => (a.some((x) => x === null) ? null : a.reduce<number>((s, x) => s + (x ?? 0), 0));
	const en = (gen: number | null, cons: number | null): ObjEnergy => {
		if (cons === null) return { gen_kwh: gen, cons_kwh: null, self_kwh: null, surplus_kwh: null, grid_kwh: null };
		const g = gen ?? 0;
		const self = Math.min(g, cons) * 0.92;
		return { gen_kwh: gen, cons_kwh: cons, self_kwh: Math.round(self * 10) / 10, surplus_kwh: Math.round((g - self) * 10) / 10, grid_kwh: Math.round((cons - self) * 10) / 10 };
	};
	const energy: Record<Period, ObjEnergy> = {
		day: site && yearCons ? en(ses ? site.today.generated_kwh : null, site.today.consumed_kwh) : en(ses ? 0 : null, null),
		month: en(monthly[mi].gen_kwh, monthly[mi].cons_kwh),
		year: en(sum(monthly.map((m) => m.gen_kwh)), sum(monthly.map((m) => m.cons_kwh)))
	};
	const kOf = (e: ObjEnergy) => (ses && e.gen_kwh !== null && e.cons_kwh ? +(e.gen_kwh / e.cons_kwh).toFixed(2) : null);
	const k = { day: kOf(energy.day), month: kOf(energy.month), year: kOf(energy.year) };
	const kc = (p: Period) => kClassOf(k[p], !!ses, energy[p].cons_kwh !== null);

	const invested = costs?.total_uah ?? null;
	const savedYear = energy.year.self_kwh !== null && ses ? Math.round(energy.year.self_kwh * tariff) : null;
	const months = ses?.launched ? Math.max(0, (now.getTime() - new Date(ses.launched).getTime()) / (30.44 * 864e5)) : null;
	const since = savedYear !== null && months !== null ? Math.round((savedYear / 12) * months) : null;
	const payback = invested && savedYear ? +(invested / savedYear).toFixed(1) : null;

	return {
		demo: true,
		mock: true,
		building: {
			id: Number(id),
			name: bld?.name ?? site?.building.name ?? '',
			address: bld?.address ?? site?.building.address ?? '',
			category_short: bld?.category_short ?? site?.building.category_short,
			heated_area: bld?.heated_area ?? null,
			floors: bld?.floors ?? null
		},
		ses,
		costs,
		k,
		k_class: { day: kc('day'), month: kc('month'), year: kc('year') },
		energy,
		finance: {
			tariff_uah_kwh: tariff,
			grid_cost_uah: {
				month: energy.month.grid_kwh !== null ? Math.round(energy.month.grid_kwh * tariff) : null,
				year: energy.year.grid_kwh !== null ? Math.round(energy.year.grid_kwh * tariff) : null
			},
			saved_uah: {
				month: energy.month.self_kwh !== null && ses ? Math.round(energy.month.self_kwh * tariff) : null,
				year: savedYear,
				since_launch: since
			},
			invested_uah: invested,
			payback_years: payback,
			payback_progress_pct: invested && since !== null ? Math.min(100, Math.round((since / invested) * 100)) : null
		},
		monthly,
		meters: yearCons ? { electricity: 1, total: 3, by_resource: {} } : { electricity: 0, total: 1, by_resource: {} },
		sem: null,
		can_edit: true
	};
}

function pick(o: Record<string, unknown>, keys: string[]) {
	return Object.fromEntries(keys.map((k) => [k, o[k]]));
}
export function emptySes(): ObjSes {
	return {
		panels_count: null, panel_w: null, total_kw: null, inverter_model: null, inverter_kw: null,
		battery_count: null, battery_module_kwh: null, battery_kwh: null, battery_kw: null,
		connected_kw: null, launched: null, source: 'введено'
	};
}
export function emptyCosts(): ObjCosts {
	return { panels_uah: null, inverter_uah: null, batteries_uah: null, install_uah: null, total_uah: null };
}
/** Похідні поля: сумарна потужність і ємність, якщо не задані явно */
export function normSes(s: ObjSes): ObjSes {
	const total_kw = s.panels_count && s.panel_w ? +((s.panels_count * s.panel_w) / 1000).toFixed(2) : s.total_kw;
	const battery_kwh = s.battery_count && s.battery_module_kwh ? +(s.battery_count * s.battery_module_kwh).toFixed(2) : s.battery_kwh;
	return { ...s, total_kw, battery_kwh };
}
export function normCosts(c: ObjCosts): ObjCosts {
	const parts = [c.panels_uah, c.inverter_uah, c.batteries_uah, c.install_uah];
	const any = parts.some((x) => x !== null && x !== undefined);
	return { ...c, total_uah: any ? parts.reduce<number>((s, x) => s + (x ?? 0), 0) : (c.total_uah ?? null) };
}
