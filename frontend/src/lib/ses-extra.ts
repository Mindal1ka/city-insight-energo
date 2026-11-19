// Додаткові фільтри мапи/списку СЕС: розпорядник, потреба в розширенні, сезон, індекс ефективності.
import type { SesItem } from './api-ses.ts';

export type Season = 'зима' | 'весна' | 'літо' | 'осінь';
export type EffClass = 'eco' | 'typ' | 'waste';

export const SEASONS: { id: Season; label: string; day: string }[] = [
	{ id: 'зима', label: 'Зима', day: '2026-01-15' },
	{ id: 'весна', label: 'Весна', day: '2026-04-15' },
	{ id: 'літо', label: 'Літо', day: '2026-07-15' },
	{ id: 'осінь', label: 'Осінь', day: '2026-10-15' }
];

export const EFF_CLASSES: { id: EffClass; label: string; color: string }[] = [
	{ id: 'eco', label: 'Економно <0,8', color: '#1f8a4c' },
	{ id: 'typ', label: 'Типово 0,8–1,2', color: '#7a8594' },
	{ id: 'waste', label: 'Марнотратно >1,2', color: '#c0392b' }
];

export function seasonDay(s: Season | null): string | undefined {
	return SEASONS.find((x) => x.id === s)?.day;
}

export function effClassOf(v: number | null | undefined): EffClass | null {
	if (v == null || !isFinite(v)) return null;
	return v < 0.8 ? 'eco' : v > 1.2 ? 'waste' : 'typ';
}

export interface ExtraFilter {
	department: string;
	need: boolean;
	eff: EffClass | null;
}

export function matchExtra(it: SesItem, f: ExtraFilter): boolean {
	if (f.department && it.department !== f.department) return false;
	if (f.need && it.k_class !== 'Не вистачає') return false;
	if (f.eff && effClassOf(it.eff_index) !== f.eff) return false;
	return true;
}

/** «12 400 кВт·год/міс» → «≈ 12 400» */
export function kwhMonth(v: number | null | undefined): string {
	if (v == null || !isFinite(v)) return '—';
	return Math.round(v).toLocaleString('uk-UA');
}

export function effText(v: number | null | undefined): string {
	if (v == null || !isFinite(v)) return '—';
	return v.toLocaleString('uk-UA', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
