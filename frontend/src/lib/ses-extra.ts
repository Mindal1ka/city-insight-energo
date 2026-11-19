// Додаткові фільтри мапи/списку СЕС: розпорядник, потреба в розширенні, сезон.
import type { SesItem } from './api-ses.ts';

export type Season = 'зима' | 'весна' | 'літо' | 'осінь';

export const SEASONS: { id: Season; label: string; day: string }[] = [
	{ id: 'зима', label: 'Зима', day: '2026-01-15' },
	{ id: 'весна', label: 'Весна', day: '2026-04-15' },
	{ id: 'літо', label: 'Літо', day: '2026-07-15' },
	{ id: 'осінь', label: 'Осінь', day: '2026-10-15' }
];

export function seasonDay(s: Season | null): string | undefined {
	return SEASONS.find((x) => x.id === s)?.day;
}

export interface ExtraFilter {
	department: string;
	need: boolean;
}

export function matchExtra(it: SesItem, f: ExtraFilter): boolean {
	if (f.department && it.department !== f.department) return false;
	if (f.need && it.k_class !== 'Не вистачає') return false;
	return true;
}

/** «12 400 кВт·год/міс» → «≈ 12 400» */
export function kwhMonth(v: number | null | undefined): string {
	if (v == null || !isFinite(v)) return '—';
	return Math.round(v).toLocaleString('uk-UA');
}
