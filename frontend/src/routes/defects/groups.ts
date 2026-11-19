// Групування записів «Якості даних» за типом проблеми: замість стіни з сотень рядків —
// кілька зрозумілих груп «що не так → що робити», а самі рядки ховаємо за розгортанням.
import type { Defect } from '#lib/api.ts';

export type Severity = 'high' | 'mid' | 'low';

export interface GroupInfo {
	/** Стабільний ключ групи */
	key: string;
	/** Заголовок простою мовою */
	title: string;
	/** Одне речення: чим це заважає */
	why: string;
	/** Одне речення: що зробити */
	todo: string;
	/** Наскільки впливає на розрахунки електроенергії */
	severity: Severity;
}

export interface DefectGroup extends GroupInfo {
	items: Defect[];
	buildings: number;
}

/** Схожі правила з різними числами всередині зводимо до одного тексту */
export function ruleGroup(rule: string): string {
	return rule
		.replace(/\s*\(\+?\d+%\)/g, '')
		.replace(/в \d+ разів/g, 'в N разів')
		.trim();
}

const KNOWN: { test: (d: Defect) => boolean; info: Omit<GroupInfo, 'key'> & { key: string } }[] = [
	{
		test: (d) => /Жодного показника споживання/i.test(d.правило),
		info: {
			key: 'no-data',
			title: 'Немає жодних показників споживання',
			why: 'Будівля є в реєстрі, але за 2025 чи 2026 рік не внесено жодного показника — ні електрики, ні тепла, газу чи води. Її не можна оцінити.',
			todo: 'Перевірити, чи є лічильники, і внести показники в UMUNI.',
			severity: 'high'
		}
	},
	{
		test: (d) => /Площа\s*≤/i.test(d.правило),
		info: {
			key: 'area',
			title: 'Не вказано площу будівлі',
			why: 'Без площі не порахувати споживання на 1 м², тож будівлю не порівняти з іншими.',
			todo: 'Внести фактичну опалювану площу в UMUNI.',
			severity: 'high'
		}
	},
	{
		test: (d) => /Питоме споживання електроенергії\s*</i.test(d.правило),
		info: {
			key: 'too-low',
			title: 'Підозріло мало електроенергії',
			why: 'Менше 0,5 кВт·год на 1 м² за рік — схоже, лічильник обліковує не всю будівлю.',
			todo: 'Перевірити, чи враховано всі лічильники будівлі.',
			severity: 'high'
		}
	},
	{
		test: (d) => /Питоме споживання електроенергії\s*>/i.test(d.правило),
		info: {
			key: 'too-high',
			title: 'Підозріло багато електроенергії',
			why: 'Понад 150 кВт·год на 1 м² за рік — так буває вкрай рідко, найчастіше це помилка у площі чи показаннях.',
			todo: 'Перевірити площу та показання лічильника в UMUNI.',
			severity: 'high'
		}
	},
	{
		test: (d) => /Питоме споживання в \d+ разів/i.test(d.правило),
		info: {
			key: 'vs-median',
			title: 'У рази більше, ніж у схожих будівель',
			why: 'Споживання на 1 м² у кілька разів вище, ніж у типової будівлі тієї ж категорії.',
			todo: 'Перевірити площу та чи не обліковано на будівлю споживання інших об’єктів.',
			severity: 'high'
		}
	},
	{
		test: (d) => /Зростання в \d+ разів/i.test(d.правило),
		info: {
			key: 'jump',
			title: 'Різкий стрибок споживання',
			why: 'Споживання зросло в десятки разів за рік — майже напевно помилка вводу.',
			todo: 'Перевірити показники лічильника в UMUNI.',
			severity: 'mid'
		}
	},
	{
		test: (d) => /Неповний .* перевищив/i.test(d.правило),
		info: {
			key: 'partial-over',
			title: 'Цього року вже витрачено більше, ніж за весь минулий',
			why: 'Рік ще не закінчився, а споживання вже більше, ніж за весь попередній рік.',
			todo: 'З’ясувати: реально зросло споживання чи це помилка вводу.',
			severity: 'mid'
		}
	},
	{
		test: (d) => /Координати/i.test(d.правило),
		info: {
			key: 'coords',
			title: 'Координат немає в UMUNI — розташування визначили за адресою',
			why: 'Будівля є на карті: точку знайшли за адресою, тож вона може трохи відрізнятися від фактичної.',
			todo: 'Внести точні координати в UMUNI, щоб не залежати від пошуку за адресою.',
			severity: 'low'
		}
	},
	{
		test: (d) => /рік забудови/i.test(d.правило),
		info: {
			key: 'year-built',
			title: 'Не вказано рік забудови',
			why: 'Довідкове поле: на розрахунки електроенергії не впливає, але потрібне для планування ремонтів.',
			todo: 'Заповнити рік забудови в UMUNI.',
			severity: 'low'
		}
	},
	{
		test: (d) => /вид опалення/i.test(d.правило),
		info: {
			key: 'heating',
			title: 'Не вказано вид опалення',
			why: 'Довідкове поле про тепло; на розрахунки електроенергії не впливає.',
			todo: 'Заповнити вид опалення в UMUNI.',
			severity: 'low'
		}
	}
];

const SEV_ORDER: Record<Severity, number> = { high: 0, mid: 1, low: 2 };

function infoFor(d: Defect): GroupInfo {
	for (const k of KNOWN) if (k.test(d)) return k.info;
	const r = ruleGroup(d.правило);
	return {
		key: 'other:' + r,
		title: r,
		why: d.тип === 'аномалія споживання' ? 'Незвичні зміни у споживанні.' : 'Помилка або пропуск у даних.',
		todo: d.що_робити || 'Перевірити дані в UMUNI.',
		severity: d.тип === 'аномалія споживання' ? 'mid' : 'low'
	};
}

export function groupDefects(list: Defect[]): DefectGroup[] {
	const m = new Map<string, DefectGroup>();
	const ids = new Map<string, Set<string>>();
	for (const d of list) {
		const info = infoFor(d);
		let g = m.get(info.key);
		if (!g) {
			g = { ...info, items: [], buildings: 0 };
			m.set(info.key, g);
			ids.set(info.key, new Set());
		}
		g.items.push(d);
		ids.get(info.key)!.add(String(d.будівля_id || d.будівля));
	}
	for (const [k, g] of m) g.buildings = ids.get(k)!.size;
	return [...m.values()].sort(
		(a, b) => SEV_ORDER[a.severity] - SEV_ORDER[b.severity] || b.items.length - a.items.length
	);
}

export const SEVERITY_LABEL: Record<Severity, string> = {
	high: 'Заважає рейтингу',
	mid: 'Варто перевірити',
	low: 'Довідкове'
};
