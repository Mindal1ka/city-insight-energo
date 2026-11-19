// Дані для мапи комунальних об'єктів: GET /api/map + кольори, значки й шкали легенди.
//
// ПРАВИЛО БЕЗПЕКИ (вимога треку): на публічній мапі НЕ показуємо, де стоять СЕС, акумулятори,
// генератори чи резервне живлення / автономність. Тут лише: тип закладу, споживання електроенергії,
// сонячний ПОТЕНЦІАЛ даху та якість даних. normalize() пропускає тільки дозволені поля —
// навіть якщо бекенд колись віддасть щось зайве, на мапу воно не потрапить.

import { catLabel } from './categories.ts';
import { getJSON, ApiError, api, type Building } from '#lib/api.ts';
import { num } from '#lib/format.ts';

export type Precision = 'UMUNI' | 'будинок' | 'вулиця' | 'населений пункт';
export type ColorBy = 'category' | 'consumption' | 'potential';
export type LatLngBounds = [[number, number], [number, number]];

export interface MapPoint {
	id: number;
	name: string;
	address: string;
	category_short: string;
	/** null — адресу не вдалося знайти, об'єкта немає на мапі (але він є в списку) */
	lat: number | null;
	lon: number | null;
	precision: Precision | null;
	/** Бекенд позначив точку як приблизну (центр села зі зсувом тощо) */
	approximate?: boolean;
	elec_kwh_2025: number | null;
	elec_kwh_m2: number | null;
	solar_potential_kw: number | null;
	solar_payback_years: number | null;
	defects_count: number;
	data_ok: boolean;
}

export interface MapData {
	points: MapPoint[];
	bounds: LatLngBounds | null;
	counts: { total: number; on_map: number; by_precision: Record<string, number> };
	note: string | null;
	/** true — координати згенеровано локально (бекенд /api/map ще не готовий) */
	mock: boolean;
}

/** Центр Полтави */
export const POLTAVA: [number, number] = [49.589, 34.551];

// ---------- Типи закладів: колір (палітра Okabe–Ito, безпечна для дальтоніків) + значок ----------

export interface CategoryMeta {
	key: string;
	/** Підпис простою мовою */
	label: string;
	color: string;
	/** Колір значка всередині кружечка */
	ink: string;
	/** SVG-шлях значка у полі 10×10: форма дублює колір, щоб тип читався й без кольору */
	glyph: string;
	shape: string;
}

const G = {
	triangle: 'M5 1.1 9.2 8.7H.8z',
	circle: 'M5 1.4a3.6 3.6 0 1 1 0 7.2 3.6 3.6 0 0 1 0-7.2z',
	plus: 'M3.9 1.2h2.2v2.7h2.7v2.2H6.1v2.7H3.9V6.1H1.2V3.9h2.7z',
	square: 'M1.8 1.8h6.4v6.4H1.8z',
	diamond: 'M5 .6 9.4 5 5 9.4.6 5z',
	house: 'M5 .9 9.3 4.7V9.1H.7V4.7z',
	dot: 'M5 3a2 2 0 1 1 0 4 2 2 0 0 1 0-4z'
};

export const CATEGORIES: CategoryMeta[] = [
	{ key: 'Заклади освіти', label: catLabel('Заклади освіти'), color: '#0072B2', ink: '#fff', glyph: G.triangle, shape: 'трикутник' },
	{ key: 'Дошкільні заклади', label: catLabel('Дошкільні заклади'), color: '#E69F00', ink: '#3b2600', glyph: G.circle, shape: 'коло' },
	{ key: "Охорона здоров'я", label: catLabel("Охорона здоров'я"), color: '#D55E00', ink: '#fff', glyph: G.plus, shape: 'хрестик' },
	{ key: 'Громадські будівлі', label: catLabel('Громадські будівлі'), color: '#7E4BA0', ink: '#fff', glyph: G.square, shape: 'квадрат' },
	{ key: 'Спортивні споруди', label: catLabel('Спортивні споруди'), color: '#009E73', ink: '#fff', glyph: G.diamond, shape: 'ромб' },
	{ key: 'Житлові будинки', label: catLabel('Житлові будинки'), color: '#56B4E9', ink: '#0b2a40', glyph: G.house, shape: 'будиночок' }
];

const OTHER: CategoryMeta = {
	key: 'Інше',
	label: 'Інші об’єкти',
	color: '#6b7685',
	ink: '#fff',
	glyph: G.dot,
	shape: 'крапка'
};

/** Апостроф у даних буває різний: ' ’ ʼ */
export function normApos(s: string): string {
	return s.replace(/[’ʼ`´]/g, "'");
}

const CAT_BY_KEY = new Map(CATEGORIES.map((c) => [normApos(c.key), c]));

export function categoryMeta(cat: string | null | undefined): CategoryMeta {
	if (!cat) return OTHER;
	return CAT_BY_KEY.get(normApos(cat)) ?? { ...OTHER, key: cat, label: cat };
}

// ---------- Точність розташування ----------

export function hasCoords(p: MapPoint): p is MapPoint & { lat: number; lon: number } {
	return typeof p.lat === 'number' && typeof p.lon === 'number' && isFinite(p.lat) && isFinite(p.lon);
}

/** Відома лише вулиця або село — показуємо пунктирним колом */
export function isApprox(p: MapPoint): boolean {
	return p.approximate === true || p.precision === 'вулиця' || p.precision === 'населений пункт';
}

export const PRECISION_TEXT: Record<Precision, string> = {
	UMUNI: 'точні координати з UMUNI',
	будинок: 'знайдено за адресою будинку',
	вулиця: 'приблизно: відома лише вулиця',
	'населений пункт': 'приблизно: відоме лише село чи селище'
};

// ---------- Шкали для режимів «за споживанням» і «за потенціалом сонця» ----------

export interface ScaleStop {
	min: number;
	max: number;
	color: string;
	ink: string;
	label: string;
}

export interface Scale {
	colorBy: Exclude<ColorBy, 'category'>;
	title: string;
	explain: string;
	unit: string;
	/** Підпис одиниць під шкалою простою мовою */
	unitText: string;
	stops: ScaleStop[];
	noData: { color: string; ink: string; label: string };
}

// Послідовні палітри: світліше → темніше (читається й у відтінках сірого)
const BLUES = ['#c9def0', '#8dbbe0', '#4f91c9', '#2167a6', '#0d3d70'];
const SUN = ['#fbe6a6', '#f6c453', '#ee9a1c', '#c26a05', '#7a3e02'];
const INK_LIGHT = '#1a2433';
const NO_DATA = '#b8c0ca';

function niceRound(v: number): number {
	if (v <= 0) return 0;
	const p = Math.pow(10, Math.floor(Math.log10(v)) - 1);
	return Math.round(v / p) * p;
}

function quantileBreaks(values: number[], classes: number): number[] {
	const s = [...values].sort((a, b) => a - b);
	const out: number[] = [];
	for (let i = 1; i < classes; i++) {
		const q = s[Math.min(s.length - 1, Math.floor((i / classes) * s.length))];
		const r = niceRound(q);
		if (r > 0 && (out.length === 0 || r > out[out.length - 1])) out.push(r);
	}
	return out;
}

/** Компактне число: 8 400 → «8,4 тис.», 1 250 000 → «1,3 млн» */
export function compact(v: number): string {
	const a = Math.abs(v);
	if (a >= 1e6) return `${num(v / 1e6, a >= 1e7 ? 0 : 1)} млн`;
	if (a >= 1e3) return `${num(v / 1e3, a >= 1e4 ? 0 : 1)} тис.`;
	return num(v, a < 10 && a % 1 ? 1 : 0);
}

export function metricValue(p: MapPoint, colorBy: ColorBy): number | null {
	if (colorBy === 'consumption') return p.elec_kwh_2025;
	if (colorBy === 'potential') return p.solar_potential_kw;
	return null;
}

/** Шкала легенди будується з УСІХ точок, щоб фільтри не змінювали значення кольорів */
export function buildScale(points: MapPoint[], colorBy: ColorBy): Scale | null {
	if (colorBy === 'category') return null;
	const vals = points.map((p) => metricValue(p, colorBy)).filter((v): v is number => v !== null && v > 0);
	const palette = colorBy === 'consumption' ? BLUES : SUN;
	const unit = colorBy === 'consumption' ? 'кВт·год' : 'кВт';
	const breaks = vals.length ? quantileBreaks(vals, palette.length) : [];
	const edges = [0, ...breaks, Infinity];
	const n = edges.length - 1;
	// Спільний множник для всіх підписів: «1,8 – 5,9» + «тис. кВт·год» замість «1,8 тис. – 5,9 тис.»
	const div = breaks.length && breaks[breaks.length - 1] >= 1000 ? 1000 : 1;
	const f = (v: number) => {
		const x = v / div;
		return num(x, x < 10 && x % 1 ? 1 : 0);
	};
	// Якщо меж менше, ніж кольорів, беремо кольори рівномірно з палітри
	const pick = (i: number) => palette[n === 1 ? palette.length - 1 : Math.round((i * (palette.length - 1)) / (n - 1))];
	const stops: ScaleStop[] = [];
	for (let i = 0; i < n; i++) {
		const color = pick(i);
		const idx = palette.indexOf(color);
		const label =
			n === 1
				? 'усі значення'
				: i === 0
					? `до ${f(edges[1])}`
					: i === n - 1
						? `понад ${f(edges[i])}`
						: `${f(edges[i])} – ${f(edges[i + 1])}`;
		stops.push({ min: edges[i], max: edges[i + 1], color, ink: idx <= 1 ? INK_LIGHT : '#fff', label });
	}
	if (colorBy === 'consumption') {
		return {
			colorBy,
			title: 'Скільки електроенергії спожито за 2025 рік',
			explain: 'Темніше коло — більше споживання. Ділимо об’єкти на п’ять приблизно рівних груп.',
			unit,
			unitText: `в ${div === 1000 ? 'тисячах ' : ''}кВт·год за рік`,
			stops,
			noData: { color: NO_DATA, ink: INK_LIGHT, label: 'немає даних про споживання' }
		};
	}
	return {
		colorBy,
		title: 'Яку сонячну станцію (СЕС) можна поставити на дах',
		explain: 'Оцінка потужності за площею даху й споживанням. Темніше — більший потенціал.',
		unit,
		unitText: 'у кВт — потужність можливої станції',
		stops,
		noData: { color: NO_DATA, ink: INK_LIGHT, label: 'потенціал не оцінено' }
	};
}

export interface PointStyle {
	color: string;
	ink: string;
	glyph: string;
	/** Діаметр кружечка в пікселях за масштабу 1 */
	size: number;
}

export function pointStyle(p: MapPoint, colorBy: ColorBy, scale: Scale | null): PointStyle {
	const cat = categoryMeta(p.category_short);
	if (colorBy === 'category' || !scale) return { color: cat.color, ink: cat.ink, glyph: cat.glyph, size: 16 };
	const v = metricValue(p, colorBy);
	if (v === null || v <= 0) return { color: scale.noData.color, ink: scale.noData.ink, glyph: cat.glyph, size: 12 };
	let i = scale.stops.findIndex((s) => v < s.max);
	if (i < 0) i = scale.stops.length - 1;
	const s = scale.stops[i];
	// Більші значення — трохи більший кружечок (13…21 px)
	const size = 13 + Math.round((i / Math.max(1, scale.stops.length - 1)) * 8);
	return { color: s.color, ink: s.ink, glyph: cat.glyph, size };
}

/** Одне головне число для картки та списку */
export function keyFigure(p: MapPoint, colorBy: ColorBy): { value: string; unit: string; label: string } {
	if (colorBy === 'potential') {
		if (p.solar_potential_kw === null) return { value: '—', unit: '', label: 'сонячний потенціал не оцінено' };
		const pb = p.solar_payback_years;
		return {
			value: num(p.solar_potential_kw, p.solar_potential_kw < 10 ? 1 : 0),
			unit: 'кВт',
			label: pb !== null ? `можлива СЕС на даху · окупність ≈ ${num(pb, 1)} р.` : 'можлива СЕС на даху'
		};
	}
	const e = p.elec_kwh_2025;
	if (e === null || e <= 0) return { value: '—', unit: '', label: 'немає даних про споживання за 2025 рік' };
	// Одна одиниця для всього списку — МВт·год (не змішуємо з кВт·год)
	const mwh = e / 1000;
	return { value: num(mwh, mwh < 1 ? 2 : mwh < 100 ? 1 : 0), unit: 'МВт·год', label: 'електроенергії за 2025 рік' };
}

// ---------- Завантаження ----------

const PRECISIONS: Precision[] = ['UMUNI', 'будинок', 'вулиця', 'населений пункт'];

function numOrNull(v: unknown): number | null {
	return typeof v === 'number' && isFinite(v) ? v : null;
}

/** Білий список полів — див. правило безпеки вгорі файлу */
function normalize(raw: Record<string, unknown>): MapPoint {
	const prec = raw.precision as Precision;
	return {
		id: Number(raw.id),
		name: String(raw.name ?? ''),
		address: String(raw.address ?? ''),
		category_short: String(raw.category_short ?? ''),
		lat: numOrNull(raw.lat),
		lon: numOrNull(raw.lon),
		precision: PRECISIONS.includes(prec) ? prec : null,
		approximate: raw.approximate === true,
		elec_kwh_2025: numOrNull(raw.elec_kwh_2025),
		elec_kwh_m2: numOrNull(raw.elec_kwh_m2),
		solar_potential_kw: numOrNull(raw.solar_potential_kw),
		solar_payback_years: numOrNull(raw.solar_payback_years),
		defects_count: Number(raw.defects_count ?? 0) || 0,
		data_ok: raw.data_ok !== false
	};
}

interface RawMap {
	points: Record<string, unknown>[];
	bounds?: LatLngBounds | null;
	counts?: { total?: number; on_map?: number; by_precision?: Record<string, number> };
	note?: string | null;
	/** Об'єкти без координат (якщо бекенд віддає їх окремо) */
	not_on_map?: unknown[];
}

function finish(points: MapPoint[], raw: Partial<RawMap>, mock: boolean): MapData {
	const onMap = points.filter(hasCoords);
	const byPrec: Record<string, number> = {};
	for (const p of onMap) if (p.precision) byPrec[p.precision] = (byPrec[p.precision] ?? 0) + 1;
	return {
		points,
		bounds: raw.bounds ?? null,
		counts: {
			total: raw.counts?.total ?? points.length,
			on_map: raw.counts?.on_map ?? onMap.length,
			by_precision: raw.counts?.by_precision ?? byPrec
		},
		note: raw.note ?? null,
		mock
	};
}

export async function loadMap(): Promise<MapData> {
	try {
		const raw = await getJSON<RawMap>('/api/map');
		const points = (raw.points ?? []).map(normalize);
		const seen = new Set(points.map((p) => p.id));
		for (const o of raw.not_on_map ?? []) {
			if (!o || typeof o !== 'object') continue;
			const p = normalize(o as Record<string, unknown>);
			if (!seen.has(p.id)) {
				p.lat = p.lon = null;
				points.push(p);
				seen.add(p.id);
			}
		}
		return finish(points, raw, false);
	} catch (e) {
		// Поки бекенд не віддає /api/map — будуємо тимчасовий макет із /api/buildings
		if (e instanceof ApiError && e.status === 404) return mockFromBuildings();
		throw e;
	}
}

// =====================================================================================
// ⚠ ТИМЧАСОВИЙ МАКЕТ (MOCK). Координати ВИПАДКОВІ навколо центру Полтави, потенціал СЕС —
// груба оцінка. Використовується ЛИШЕ коли /api/map відповідає 404. Прибрати, щойно бекенд готовий.
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

const MOCK_VILLAGES: [number, number][] = [
	[49.5365, 34.4805],
	[49.6512, 34.4931],
	[49.5528, 34.6602],
	[49.6305, 34.6371]
];

async function mockFromBuildings(): Promise<MapData> {
	const list: Building[] = await api.buildings();
	const points = list.map((b): MapPoint => {
		const r = rng(b.id * 2654435761);
		const roll = r();
		let lat: number | null = null;
		let lon: number | null = null;
		let precision: Precision | null = null;
		if (roll < 0.042) {
			// без адреси
		} else if (roll < 0.12) {
			const v = MOCK_VILLAGES[Math.floor(r() * MOCK_VILLAGES.length)];
			[lat, lon] = v;
			precision = 'населений пункт';
		} else {
			const ang = r() * Math.PI * 2;
			const d = Math.pow(r(), 0.75);
			lat = POLTAVA[0] + Math.sin(ang) * d * 0.045;
			lon = POLTAVA[1] + Math.cos(ang) * d * 0.07;
			precision = roll < 0.24 ? 'вулиця' : roll < 0.5 ? 'UMUNI' : 'будинок';
		}
		const y = b.years?.['2025'];
		const elec = y?.elec_kwh ?? null;
		const roofKw = b.heated_area ? (b.heated_area / Math.max(1, b.floors ?? 1)) * 0.12 : null;
		const needKw = elec ? elec / 1150 : null;
		const kw = roofKw && needKw ? Math.round(Math.min(roofKw, needKw) * 10) / 10 : null;
		return {
			id: b.id,
			name: b.name,
			address: b.address,
			category_short: b.category_short,
			lat,
			lon,
			precision,
			elec_kwh_2025: elec,
			elec_kwh_m2: y?.elec_kwh_m2 ?? null,
			solar_potential_kw: kw && kw >= 1 ? kw : null,
			solar_payback_years: kw && kw >= 1 ? Math.round((4 + r() * 5) * 10) / 10 : null,
			defects_count: b.defects_count ?? 0,
			data_ok: (b.defects_count ?? 0) === 0
		};
	});
	return finish(points, { note: 'Тимчасові координати для перевірки інтерфейсу: справжнє геокодування ще готується.' }, true);
}
