// Момент перегляду телеметрії зберігається в адресі (?view=summer), щоб посилання й «Назад» працювали
import type { ViewKey } from './api.ts';

export function viewFrom(url: { searchParams: { get(name: string): string | null } }): ViewKey {
	return url.searchParams.get('view') === 'summer' ? 'summer' : 'now';
}

/** Додає ?view=… до шляху (для «Зараз» параметр не потрібен) */
export function withView(path: string, view: ViewKey, extra: Record<string, string> = {}): string {
	const p = new URLSearchParams(extra);
	if (view !== 'now') p.set('view', view);
	const s = p.toString();
	return s ? `${path}?${s}` : path;
}
