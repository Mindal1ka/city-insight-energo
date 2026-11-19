// Форматування чисел, дат і підписів українською

const cache = new Map<number, Intl.NumberFormat>();

function nf(digits: number): Intl.NumberFormat {
	let f = cache.get(digits);
	if (!f) {
		f = new Intl.NumberFormat('uk-UA', {
			minimumFractionDigits: digits,
			maximumFractionDigits: digits
		});
		cache.set(digits, f);
	}
	return f;
}

/** Число з розділювачами тисяч; null → «—» */
export function num(v: number | null | undefined, digits = 0): string {
	if (v === null || v === undefined || Number.isNaN(v)) return '—';
	return nf(digits).format(v);
}

/** Число з одиницею виміру (нерозривний пробіл) */
export function withUnit(v: number | null | undefined, unit: string, digits = 0): string {
	if (v === null || v === undefined || Number.isNaN(v)) return '—';
	return `${num(v, digits)} ${unit}`;
}

/** Частка 0..1 → «86 %» */
export function pct(share: number | null | undefined, digits = 0): string {
	if (share === null || share === undefined) return '—';
	return `${num(share * 100, digits)} %`;
}

/** ISO-дата → «11.11.2026» */
export function date(iso: string | null | undefined): string {
	if (!iso) return '—';
	const d = new Date(iso);
	if (Number.isNaN(d.getTime())) return iso;
	return d.toLocaleDateString('uk-UA', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

/** ISO-дата і час → «11.11.2026, 11:55» */
export function dateTime(iso: string | null | undefined): string {
	if (!iso) return '—';
	const d = new Date(iso);
	if (Number.isNaN(d.getTime())) return iso;
	return d.toLocaleString('uk-UA', {
		day: '2-digit',
		month: '2-digit',
		year: 'numeric',
		hour: '2-digit',
		minute: '2-digit'
	});
}

/** «Гарні» межі шкали для графіка */
export function niceMax(v: number): number {
	if (v <= 0) return 1;
	const p = Math.pow(10, Math.floor(Math.log10(v)));
	for (const m of [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) {
		if (m * p >= v) return m * p;
	}
	return 10 * p;
}

export const MONTHS = ['січ', 'лют', 'бер', 'кві', 'тра', 'чер', 'лип', 'сер', 'вер', 'жов', 'лис', 'гру'];

export const MONTHS_FULL = [
	'Січень',
	'Лютий',
	'Березень',
	'Квітень',
	'Травень',
	'Червень',
	'Липень',
	'Серпень',
	'Вересень',
	'Жовтень',
	'Листопад',
	'Грудень'
];

/** Число зі знаком: «+12,4» / «−8,1» (справжній мінус U+2212) */
export function signed(v: number | null | undefined, digits = 1): string {
	if (v === null || v === undefined || Number.isNaN(v)) return '—';
	const r = Number(v.toFixed(digits));
	if (r === 0) return num(0, digits);
	return (r > 0 ? '+' : '−') + num(Math.abs(r), digits);
}

/** Енергія з адаптивною одиницею: кВт·год або МВт·год */
export function energy(kwh: number | null | undefined, digits = 1): { v: string; u: string } {
	if (kwh === null || kwh === undefined || Number.isNaN(kwh)) return { v: '—', u: '' };
	if (Math.abs(kwh) >= 10000) return { v: num(kwh / 1000, 1), u: 'МВт·год' };
	return { v: num(kwh, Math.abs(kwh) >= 1000 ? 0 : digits), u: 'кВт·год' };
}

/** Година → «08:00» */
export function hh(h: number): string {
	return `${String(h).padStart(2, '0')}:00`;
}

/** Момент «зараз» з бекенду («2026-11-19T13:12+02:00») без перерахунку в часовий пояс браузера */
export function moment(
	iso: string | null | undefined
): { date: string; time: string; hour: number; minute: number } | null {
	if (!iso) return null;
	const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso);
	if (!m) return null;
	return {
		date: `${m[3]}.${m[2]}.${m[1]}`,
		time: `${m[4]}:${m[5]}`,
		hour: Number(m[4]),
		minute: Number(m[5])
	};
}

const LONG = new Intl.DateTimeFormat('uk-UA', { day: 'numeric', month: 'long', year: 'numeric' });

/** «2026-11-19» → «19 листопада 2026 р.» */
export function longDate(iso: string | null | undefined): string {
	if (!iso) return '—';
	const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
	if (!m) return iso;
	return LONG.format(new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])));
}
