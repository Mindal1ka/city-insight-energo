// Спільний стан «свіжості даних»: бейдж у меню й сторінка «Оновити дані» читають одне джерело.
import { api, type Freshness, type FreshStatus } from './api.ts';

export const fresh = $state<{ data: Freshness | null; error: boolean; loading: boolean }>({
	data: null,
	error: false,
	loading: false
});

let inflight: Promise<void> | null = null;

/** Завантажити (або перезавантажити після нового файлу) */
export function loadFreshness(force = false): Promise<void> {
	if (inflight) return inflight;
	if (fresh.data && !force) return Promise.resolve();
	fresh.loading = true;
	inflight = api
		.freshness()
		.then((d) => {
			fresh.data = d;
			fresh.error = false;
		})
		.catch(() => {
			fresh.error = true;
		})
		.finally(() => {
			fresh.loading = false;
			inflight = null;
		});
	return inflight;
}

export const STATUS_TEXT: Record<FreshStatus, string> = {
	fresh: 'Дані актуальні',
	due: 'Пора оновити',
	stale: 'Дані застаріли'
};

export const STATUS_SHORT: Record<FreshStatus, string> = {
	fresh: 'актуально',
	due: 'пора оновити',
	stale: 'застаріло'
};

/** «сьогодні», «вчора», «9 днів тому» */
export function ago(days: number | null): string {
	if (days === null) return 'немає даних';
	if (days <= 0) return 'сьогодні';
	if (days === 1) return 'вчора';
	const n = days % 100;
	const last = days % 10;
	const w = n >= 11 && n <= 14 ? 'днів' : last === 1 ? 'день' : last >= 2 && last <= 4 ? 'дні' : 'днів';
	return `${days} ${w} тому`;
}
