// Єдині короткі назви типів закладів для всього інтерфейсу.
// Використання: import { catLabel } from '#lib/categories.ts'; catLabel(b.category_short) → «Освіта».
// Порядок у CATEGORY_ORDER — пріоритет критичності (медицина → освіта → садочки → інші).

export const CATEGORY_LABEL: Record<string, string> = {
	"Охорона здоров'я": 'Медзаклади',
	'Заклади освіти': 'Освіта',
	'Дошкільні заклади': 'Садочки',
	'Громадські будівлі': 'Громадські',
	'Житлові будинки': 'Житлові',
	'Спортивні споруди': 'Спорт'
};

export const CATEGORY_ORDER = [
	"Охорона здоров'я",
	'Заклади освіти',
	'Дошкільні заклади',
	'Громадські будівлі',
	'Спортивні споруди',
	'Житлові будинки'
];

export function catLabel(category_short: string | null | undefined): string {
	if (!category_short) return 'Інше';
	return CATEGORY_LABEL[category_short] ?? category_short;
}
