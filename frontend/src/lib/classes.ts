// Умовні класи ефективності: аналітична оцінка відносно медіани категорії, НЕ офіційний енергосертифікат.
// Межі мають збігатися з CLASS_BOUNDS у backend/app/analytics.py.

export interface ClassInfo {
	letter: string;
	text: string;
	range: string;
}

export const CLASSES: ClassInfo[] = [
	{ letter: 'A', text: 'значно краще за аналоги', range: 'до 0,5 медіани' },
	{ letter: 'B', text: 'краще за аналоги', range: '0,5–0,75 медіани' },
	{ letter: 'C', text: 'трохи краще за аналоги', range: '0,75–0,9 медіани' },
	{ letter: 'D', text: 'на рівні аналогів', range: '0,9–1,1 медіани' },
	{ letter: 'E', text: 'гірше за аналоги', range: '1,1–1,5 медіани' },
	{ letter: 'F', text: 'помітно гірше за аналоги', range: '1,5–2 медіани' },
	{ letter: 'G', text: 'значно гірше за аналоги', range: 'понад 2 медіани' }
];

export function classInfo(letter: string | null | undefined): ClassInfo | null {
	if (!letter) return null;
	return CLASSES.find((c) => c.letter === letter) ?? null;
}
