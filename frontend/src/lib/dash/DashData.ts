// Дані дашборду ефективності СЕС: типи за контрактом GET /api/ses (docs/PLAN_v3.md),
// завантаження, класи K (колір + значок + текст), агрегати, CSV.
// Запити й макет-запаска — у спільному #lib/api-ses.ts.
import { K_CLASSES, classifyK, fetchSes, type KClass, type Period, type SesItem, type SesList as BaseList } from '../api-ses.ts';
export { PERIODS, kText, uah } from '../api-ses.ts';
export type { KClass, Period, SesItem };

export interface SesMonth {
	month: number;
	gen_kwh: number;
	cons_kwh: number;
	k?: number | null;
}
/** Список + необов'язковий помісячний агрегат громади (якщо бекенд його віддає) */
export type SesList = BaseList & { monthly?: SesMonth[] | null };

export interface SesTotals {
	objects: number;
	with_ses: number;
	effective: number;
	deficit: number;
	surplus: number;
	no_ses: number;
	no_data: number;
	gen_kwh: number;
	cons_kwh: number;
	k: number | null;
	capex_uah: number;
	saved_uah_year: number;
	grid_cost_uah_year: number;
}

export async function loadSes(period: Period, day?: string): Promise<SesList> {
	return (await fetchSes(period, day)) as SesList;
}

export interface ClassMeta {
	id: KClass;
	slug: string;
	short: string;
	color: string;
	ink: string;
	soft: string;
	sym: string;
	key: keyof Pick<SesTotals, 'effective' | 'deficit' | 'surplus' | 'no_ses' | 'no_data'>;
}

const SHARED = Object.fromEntries(K_CLASSES.map((c) => [c.id, c]));
const BASE: ClassMeta[] = [
	{ id: 'Ефективно', slug: 'eff', short: 'Ефективно', color: '#1a7f37', ink: '#14632b', soft: '#e3f4e8', sym: '✓', key: 'effective' },
	{ id: 'Не вистачає', slug: 'def', short: 'Не вистачає', color: '#d9670b', ink: '#9a3f05', soft: '#fdecdc', sym: '↓', key: 'deficit' },
	{ id: 'Надлишок', slug: 'sur', short: 'Надлишок', color: '#1f6fd1', ink: '#134f99', soft: '#e3eefb', sym: '↑', key: 'surplus' },
	{ id: 'Без СЕС', slug: 'none', short: 'Без СЕС', color: '#7b8796', ink: '#4f5b6b', soft: '#eef2f6', sym: '○', key: 'no_ses' },
	{ id: 'Немає даних', slug: 'nodata', short: 'Немає даних', color: '#b9c2cd', ink: '#5b6676', soft: '#f3f5f8', sym: '?', key: 'no_data' }
];
export const CLASSES: ClassMeta[] = BASE.map((c) => ({ ...c, color: SHARED[c.id]?.color ?? c.color, soft: SHARED[c.id]?.soft ?? c.soft }));
export const CLASS_BY_ID = Object.fromEntries(CLASSES.map((c) => [c.id, c])) as Record<KClass, ClassMeta>;
export const CLASS_BY_SLUG = Object.fromEntries(CLASSES.map((c) => [c.slug, c])) as Record<string, ClassMeta>;

export const classOf = classifyK;

// ---------- Агрегати ----------

export function sumTotals(items: SesItem[]): SesTotals {
	const t: SesTotals = {
		objects: items.length,
		with_ses: 0,
		effective: 0,
		deficit: 0,
		surplus: 0,
		no_ses: 0,
		no_data: 0,
		gen_kwh: 0,
		cons_kwh: 0,
		k: null,
		capex_uah: 0,
		saved_uah_year: 0,
		grid_cost_uah_year: 0
	};
	for (const i of items) {
		if (i.has_ses) t.with_ses++;
		const c = i.k_class ?? classOf(i.k, i.has_ses);
		t[CLASS_BY_ID[c].key]++;
		if (i.has_ses && i.k !== null && i.gen_kwh !== null && i.cons_kwh) {
			t.gen_kwh += i.gen_kwh;
			t.cons_kwh += i.cons_kwh;
		}
		t.capex_uah += i.capex_uah ?? 0;
		t.saved_uah_year += i.saved_uah_year ?? 0;
		t.grid_cost_uah_year += (i as SesItem & { grid_cost_uah_year?: number | null }).grid_cost_uah_year ?? 0;
	}
	t.k = t.cons_kwh > 0 ? t.gen_kwh / t.cons_kwh : null;
	return t;
}

export const kOf = (i: SesItem): KClass => i.k_class ?? classOf(i.k, i.has_ses);

/** Гістограма K: кошики по 0,1 від 0 до 2 (останній — «≥ 1,9») */
export function histogram(items: SesItem[], step = 0.1, max = 2): { x0: number; x1: number; n: number }[] {
	const nb = Math.round(max / step);
	const bins = Array.from({ length: nb }, (_, i) => ({ x0: +(i * step).toFixed(2), x1: +((i + 1) * step).toFixed(2), n: 0 }));
	for (const i of items) {
		if (i.k === null || !Number.isFinite(i.k)) continue;
		const b = Math.min(nb - 1, Math.max(0, Math.floor(i.k / step + 1e-9)));
		bins[b].n++;
	}
	return bins;
}

export function median(xs: number[]): number | null {
	if (!xs.length) return null;
	const s = [...xs].sort((a, b) => a - b);
	const m = s.length >> 1;
	return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

export interface TypeRow {
	key: string;
	label: string;
	count: number;
	withSes: number;
	k: number | null;
}

// ---------- CSV ----------

export function toCsv(rows: SesItem[], cols: { key: keyof SesItem | 'class' | 'type'; label: string }[], typeLabel: (c: string | null) => string): string {
	const esc = (v: unknown) => {
		if (v === null || v === undefined) return '';
		const s = typeof v === 'number' ? String(v).replace('.', ',') : String(v);
		return /[;"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
	};
	const head = cols.map((c) => esc(c.label)).join(';');
	const body = rows.map((r) =>
		cols
			.map((c) => (c.key === 'class' ? esc(kOf(r)) : c.key === 'type' ? esc(typeLabel(r.category_short)) : esc(r[c.key as keyof SesItem])))
			.join(';')
	);
	return '﻿' + [head, ...body].join('\r\n');
}

export function download(name: string, text: string): void {
	const blob = new Blob([text], { type: 'text/csv;charset=utf-8' });
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = name;
	document.body.appendChild(a);
	a.click();
	a.remove();
	setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const UAH = (n: number | null | undefined, digits = 0) =>
	n === null || n === undefined ? '—' : new Intl.NumberFormat('uk-UA', { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(n);

/** Велика сума грн → {v, unit}: млн / тис. */
export function moneyShort(n: number): { v: number; unit: string; d: number } {
	const a = Math.abs(n);
	if (a >= 1e6) return { v: n / 1e6, unit: 'млн грн', d: 1 };
	if (a >= 1e3) return { v: n / 1e3, unit: 'тис. грн', d: 0 };
	return { v: n, unit: 'грн', d: 0 };
}
