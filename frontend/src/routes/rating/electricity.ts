// Рейтинг будівель за питомим споживанням ЕЛЕКТРОЕНЕРГІЇ (кВт·год на 1 м² площі за рік).
// Рахується на клієнті з /api/buildings: бекенд ранжує за всіма видами енергії, а продукт — лише про електрику.
// Межі класів ті самі, що в classes.ts (відношення до медіани категорії).
import type { Building, Defect } from '#lib/api.ts';

export const BASE_YEAR = '2025';

/** Менше цього — майже напевно лічильник обліковує не всю будівлю */
const MIN_KWH_M2 = 0.5;
/** У стільки разів більше за медіану — ймовірна помилка в площі або показаннях */
const MAX_RATIO = 5;

export interface ElecRow {
	b: Building;
	kwh: number | null;
	kwhM2: number | null;
	median: number | null;
	ratio: number | null;
	cls: string | null;
	rank: number | null;
	rankOf: number | null;
	excluded: string | null;
}

export interface ElecRating {
	rows: Map<number, ElecRow>;
	medians: Record<string, number | null>;
	byCategory: Record<string, ElecRow[]>;
}

export function median(values: number[]): number | null {
	if (!values.length) return null;
	const s = [...values].sort((a, b) => a - b);
	const m = Math.floor(s.length / 2);
	return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

export function classOf(ratio: number | null): string | null {
	if (ratio === null) return null;
	if (ratio < 0.5) return 'A';
	if (ratio < 0.75) return 'B';
	if (ratio < 0.9) return 'C';
	if (ratio <= 1.1) return 'D';
	if (ratio <= 1.5) return 'E';
	if (ratio <= 2) return 'F';
	return 'G';
}

function fmt(v: number): string {
	return new Intl.NumberFormat('uk-UA', { maximumFractionDigits: 0 }).format(v);
}

export function electricityRating(buildings: Building[], year = BASE_YEAR): ElecRating {
	const rows = new Map<number, ElecRow>();
	const byCat: Record<string, ElecRow[]> = {};

	for (const b of buildings) {
		const y = b.years[year];
		const kwh = y?.elec_kwh ?? null;
		const area = b.heated_area;
		let excluded: string | null = null;
		let kwhM2: number | null = null;
		if (!kwh) excluded = `Немає даних про електроенергію за ${year} рік`;
		else if (!area || area <= 1) excluded = 'Не вказано коректну площу — немає на що ділити';
		else {
			kwhM2 = kwh / area;
			if (kwhM2 < MIN_KWH_M2)
				excluded = 'Підозріло мало (< 0,5 кВт·год/м² за рік) — схоже, лічильник обліковує не всю будівлю';
		}
		const row: ElecRow = { b, kwh, kwhM2, median: null, ratio: null, cls: null, rank: null, rankOf: null, excluded };
		rows.set(b.id, row);
		(byCat[b.category_short] ??= []).push(row);
	}

	const medians: Record<string, number | null> = {};
	for (const [cat, list] of Object.entries(byCat)) {
		const valid = list.filter((r) => !r.excluded && r.kwhM2 !== null).map((r) => r.kwhM2!);
		const m = median(valid);
		medians[cat] = m;
		for (const r of list) {
			r.median = m;
			if (r.excluded || r.kwhM2 === null || !m) continue;
			r.ratio = r.kwhM2 / m;
			if (r.ratio > MAX_RATIO) {
				r.excluded = `У ${fmt(r.ratio)} разів більше за медіану — ймовірна помилка в площі або показаннях`;
				r.ratio = null;
			} else r.cls = classOf(r.ratio);
		}
		// 1 = найбільше кВт·год на м² (з неї варто почати аудит)
		const rated = list.filter((r) => !r.excluded).sort((a, b) => b.kwhM2! - a.kwhM2!);
		rated.forEach((r, i) => {
			r.rank = i + 1;
			r.rankOf = rated.length;
		});
	}
	return { rows, medians, byCategory: byCat };
}

/** Поля, що стосуються тепла, газу чи води — у продукті про електроенергію їх приховуємо за замовчуванням */
const NON_ELEC_FIELDS = ['теплова енергія', 'газ', 'гаряча вода', 'холодна вода', 'вид опалення', 'питоме споживання'];

export function isElecRelevant(d: Defect): boolean {
	return !NON_ELEC_FIELDS.includes(String(d.поле).trim().toLocaleLowerCase('uk'));
}

/** Текст для «приблизно як типова будівля категорії» */
export const LEVEL_WORDS = 'на рівні типової';

/** «у 2,3 раза більше» / «на 40 % менше» / «на рівні типової» */
export function ratioWords(r: number | null): string {
	if (r === null) return '—';
	const nf = (v: number, d: number) =>
		new Intl.NumberFormat('uk-UA', { minimumFractionDigits: d, maximumFractionDigits: d }).format(v);
	if (r >= 1.5) return `у ${nf(r, 1)} раза більше`;
	if (r > 1.1) return `на ${nf((r - 1) * 100, 0)} % більше`;
	if (r >= 0.9) return LEVEL_WORDS;
	return `на ${nf((1 - r) * 100, 0)} % менше`;
}
