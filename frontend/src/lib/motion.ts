/*
 * Моушн застосунку — самописні переходи й дії (actions), без бібліотек.
 *
 * ПРАВИЛА
 *   • Рух лише тоді, коли змінюється стан або треба направити погляд. Жодних масових «появ» списків.
 *   • Лише transform і opacity. Тривалості: 100–160 мс — рутинний UI, 200–300 мс — значущі зміни.
 *   • Криві — ті самі, що й у app.css (--ease-out / --ease-in-out / --ease-in / --ease-emph).
 *   • prefers-reduced-motion: reduce → усе миттєво (кожна функція тут це перевіряє).
 *
 * ВИКОРИСТАННЯ
 *   import { DUR, EASE, slideIn, swap, segIndicator, growOnce, pulseOnce, isReduced } from '#lib/motion.ts';
 *
 *   <aside in:slideIn={{ x: 24 }} out:slideIn={{ x: 24, out: true }}>…</aside>   // картка/шухляда з боку якоря
 *   {#key tab}<div in:swap={{ dir }}>…</div>{/key}                                 // вміст вкладки з урахуванням напрямку
 *   <div class="seg" use:segIndicator>…</div>                                       // індикатор, що ковзає під вибраним
 *   <g use:growOnce>…</g>                                                           // стовпці ростуть від осі лише при першому показі
 *   <span use:pulseOnce={selectedId}>…</span>                                       // одне кільце-імпульс при зміні ключа
 */
import { prefersReducedMotion } from 'svelte/motion';
import { cubicOut, cubicInOut, quintOut, backOut, expoOut, linear } from 'svelte/easing';
import type { TransitionConfig } from 'svelte/transition';
import type { Action } from 'svelte/action';

export { cubicOut, cubicInOut, quintOut, backOut, expoOut, linear };

/** Реактивна перевірка: reducedMotion.current === true → анімації вимкнено */
export const reducedMotion = prefersReducedMotion;

/** Разова перевірка (безпечно поза Svelte-компонентом) */
export function isReduced(): boolean {
	try {
		return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
	} catch {
		return false;
	}
}

/** Тривалості, мс — дзеркало --dur-* з app.css */
export const DUR = { press: 100, fast: 140, base: 220, slow: 300 } as const;

/** Кубічна Безьє (x1,y1,x2,y2) як функція t→прогрес — ті самі криві, що й у CSS */
function bezier(x1: number, y1: number, x2: number, y2: number): (t: number) => number {
	const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx;
	const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
	const sx = (t: number) => ((ax * t + bx) * t + cx) * t;
	const sy = (t: number) => ((ay * t + by) * t + cy) * t;
	const dx = (t: number) => (3 * ax * t + 2 * bx) * t + cx;
	return (x: number) => {
		if (x <= 0) return 0;
		if (x >= 1) return 1;
		let t = x;
		for (let i = 0; i < 6; i++) {
			const e = sx(t) - x;
			const d = dx(t);
			if (Math.abs(e) < 1e-4 || Math.abs(d) < 1e-6) break;
			t -= e / d;
		}
		return sy(Math.min(1, Math.max(0, t)));
	};
}

export const EASE = {
	out: bezier(0.2, 0.7, 0.2, 1),
	inOut: bezier(0.55, 0, 0.25, 1),
	in: bezier(0.4, 0, 1, 1),
	emph: bezier(0.16, 1, 0.3, 1)
} as const;

/** Застаріле: «драбинки» прибрано — завжди 0 (лишено, щоб старий код компілювався) */
export function stagger(_i: number, _step = 0, _max = 0): number {
	return 0;
}

export interface FadeUpParams {
	delay?: number;
	duration?: number;
	y?: number;
	easing?: (t: number) => number;
}

/** Поява нового результату (вердикт, відповідь калькулятора): прозорість + зсув на y px (типово 4) */
export function fadeUp(
	_node: Element,
	{ delay = 0, duration = DUR.base, y = 4, easing = EASE.out }: FadeUpParams = {}
): TransitionConfig {
	if (isReduced()) return { duration: 0 };
	return {
		delay,
		duration,
		easing,
		css: (t, u) => `opacity:${t};transform:translateY(${(u * y).toFixed(2)}px)`
	};
}

export interface ScaleInParams {
	delay?: number;
	duration?: number;
	start?: number;
	easing?: (t: number) => number;
}

/** Спливаюче вікно/підказка: 0.97 → 1 з точки походження (transform-origin задає компонент) */
export function scaleIn(
	_node: Element,
	{ delay = 0, duration = DUR.fast, start = 0.97, easing = EASE.out }: ScaleInParams = {}
): TransitionConfig {
	if (isReduced()) return { duration: 0 };
	return {
		delay,
		duration,
		easing,
		css: (t) => `opacity:${t};transform:scale(${(start + (1 - start) * t).toFixed(4)})`
	};
}

export interface SlideParams {
	x?: number;
	y?: number;
	duration?: number;
	/** true — для out: швидше і з кривою «геть з дороги» */
	out?: boolean;
}

/** Картка/шухляда виїжджає з боку свого якоря (x або y у px) і проявляється */
export function slideIn(_node: Element, { x = 0, y = 0, duration, out = false }: SlideParams = {}): TransitionConfig {
	if (isReduced()) return { duration: 0 };
	return {
		duration: duration ?? (out ? DUR.fast : DUR.slow),
		easing: out ? EASE.in : EASE.emph,
		css: (t, u) =>
			`opacity:${Math.min(1, t * 1.6).toFixed(3)};transform:translate(${(u * x).toFixed(1)}px,${(u * y).toFixed(1)}px)`
	};
}

/** Зміна вмісту вкладки: зсув 12 px у бік руху + проявлення (dir: 1 — вправо, -1 — вліво) */
export function swap(_node: Element, { dir = 0, duration = DUR.base }: { dir?: number; duration?: number } = {}): TransitionConfig {
	if (isReduced()) return { duration: 0 };
	const dx = Math.sign(dir) * 12;
	return {
		duration,
		easing: EASE.out,
		css: (t, u) => `opacity:${t.toFixed(3)};transform:translateX(${(u * dx).toFixed(1)}px)`
	};
}

/**
 * Сегментований перемикач: одна «таблетка» ковзає під вибраною кнопкою (aria-pressed / aria-selected /
 * aria-current). Створює <span class="seg-ind"> усередині контейнера; стилі — у app.css (.seg-ind).
 * Перший показ — без руху (таблетка вже на місці), далі — 200 мс --ease-in-out.
 */
export const segIndicator: Action<HTMLElement, string | number | boolean | null | undefined> = (node) => {
	const ind = document.createElement('span');
	ind.className = 'seg-ind';
	ind.setAttribute('aria-hidden', 'true');
	node.prepend(ind);
	node.classList.add('has-ind');
	// Індикатор позиціонується відносно контейнера (offsetLeft рахується від нього ж)
	if (getComputedStyle(node).position === 'static') node.style.position = 'relative';
	let first = true;
	let px = 0, pw = 0, py = 0;
	const place = () => {
		const sel = node.querySelector<HTMLElement>(
			':scope > [aria-pressed="true"], :scope > [aria-selected="true"], :scope > [aria-current="page"], :scope > [aria-checked="true"]'
		);
		if (!sel) {
			ind.style.opacity = '0';
			first = true;
			return;
		}
		const x = sel.offsetLeft, y = sel.offsetTop, w = sel.offsetWidth;
		if (x === px && w === pw && y === py && !first) return;
		// FLIP: розмір ставимо одразу кінцевий, а рух і різницю ширини показуємо лише через transform
		ind.style.width = w + 'px';
		ind.style.height = sel.offsetHeight + 'px';
		if (first || isReduced() || !pw) {
			ind.style.transition = 'none';
			ind.style.transform = `translate(${x}px,${y}px)`;
		} else {
			ind.style.transition = 'none';
			ind.style.transform = `translate(${px}px,${py}px) scaleX(${(pw / w).toFixed(4)})`;
			void ind.offsetWidth;
			ind.style.transition = '';
			ind.style.transform = `translate(${x}px,${y}px)`;
		}
		ind.style.opacity = '1';
		px = x; pw = w; py = y;
		first = false;
	};
	place();
	const mo = new MutationObserver(place);
	mo.observe(node, { subtree: true, attributes: true, attributeFilter: ['aria-pressed', 'aria-selected', 'aria-current', 'aria-checked'], childList: true });
	const ro = new ResizeObserver(() => {
		first = true;
		place();
	});
	ro.observe(node);
	return {
		update: place,
		destroy() {
			mo.disconnect();
			ro.disconnect();
			ind.remove();
			node.classList.remove('has-ind');
		}
	};
};

/**
 * Стовпці/смуги ростуть від базової лінії лише при першому показі графіка (scaleY 0 → 1, 280 мс).
 * Повторні зміни даних не «перезапускають» ріст. axis: 'y' (типово) або 'x' (горизонтальні смуги).
 */
export const growOnce: Action<Element, 'x' | 'y' | undefined> = (node, axis = 'y') => {
	if (isReduced() || typeof (node as unknown as HTMLElement).animate !== 'function') return;
	const from = axis === 'x' ? 'scaleX(0)' : 'scaleY(0)';
	const to = axis === 'x' ? 'scaleX(1)' : 'scaleY(1)';
	(node as unknown as HTMLElement).animate([{ transform: from }, { transform: to }], {
		duration: 280,
		easing: 'cubic-bezier(0.16, 1, 0.3, 1)'
	});
};

/** Одне кільце-імпульс, коли змінюється ключ (вибраний маркер, щойно збережене поле) */
export const pulseOnce: Action<HTMLElement, unknown> = (node, key) => {
	let last = key;
	const run = () => {
		if (isReduced()) return;
		// Кільце — окремий елемент: анімуємо лише transform і opacity
		if (getComputedStyle(node).position === 'static') node.style.position = 'relative';
		const ring = document.createElement('span');
		ring.setAttribute('aria-hidden', 'true');
		ring.style.cssText =
			'position:absolute;inset:-2px;border-radius:inherit;border:2px solid var(--sun,#f5a524);pointer-events:none';
		node.appendChild(ring);
		ring
			.animate(
				[
					{ transform: 'scale(1)', opacity: 0.8 },
					{ transform: 'scale(1.6)', opacity: 0 }
				],
				{ duration: 600, easing: 'cubic-bezier(0.2, 0.7, 0.2, 1)' }
			)
			.finished.finally(() => ring.remove());
	};
	return {
		update(k) {
			if (k !== last) {
				last = k;
				run();
			}
		}
	};
};

/*
 * ПЕРША ПОЯВА ДАНИХ НА СТОРІНЦІ (reveal)
 *
 *   <div class="tile" use:reveal={0}>…</div>  <div class="tile" use:reveal={1}>…</div>
 *   <div class="chart" use:reveal={{ i: 4, y: 0 }}>…</div>
 *   <tbody use:revealRows>…</tbody>            // перші 8 рядків — драбинка 20 мс, решта миттєво
 *
 * Анімує лише перша «хвиля» вмісту на маршруті: перший вузол із reveal відкриває вікно ~1.2 с
 * для цього шляху; усе, що змонтується пізніше (зміна фільтра, періоду, повернення на вже
 * відкриту сторінку в межах сесії), з'являється миттєво. Лише opacity + transform, WAAPI,
 * reduced-motion → без руху. Вміст має стояти у слоті-каркасі такої ж висоти — тоді поява
 * не зсуває макет.
 */
const firstWave = new Map<string, number>();
const WAVE_MS = 1200;

/** Чи ще триває перша хвиля появи для поточного маршруту (і відкриває її, якщо це перший виклик) */
export function inFirstWave(): boolean {
	if (typeof location === 'undefined') return false;
	const key = location.pathname;
	const now = performance.now();
	const t0 = firstWave.get(key);
	if (t0 == null) {
		firstWave.set(key, now);
		return true;
	}
	return now - t0 < WAVE_MS;
}

export interface RevealParams {
	/** порядковий номер у ряду — затримка i × step */
	i?: number;
	/** зсув знизу, px (типово 6) */
	y?: number;
	/** крок драбинки, мс (типово 35) */
	step?: number;
	/** додаткова затримка, мс (напр. графік після плиток) */
	delay?: number;
	duration?: number;
}

function play(el: HTMLElement, delay: number, y: number, duration: number) {
	if (typeof el.animate !== 'function') return;
	el.animate(
		[
			{ opacity: 0, transform: `translateY(${y}px)` },
			{ opacity: 1, transform: 'none' }
		],
		{ duration, delay, easing: 'cubic-bezier(0.2, 0.7, 0.2, 1)', fill: 'backwards' }
	);
}

export const reveal: Action<HTMLElement, number | RevealParams | undefined> = (node, p) => {
	if (isReduced() || !inFirstWave()) return;
	const o: RevealParams = typeof p === 'number' ? { i: p } : (p ?? {});
	const i = Math.min(o.i ?? 0, 6);
	play(node, (o.delay ?? 0) + i * (o.step ?? 35), o.y ?? 6, o.duration ?? DUR.base);
};

/**
 * Діти контейнера по черзі: перші `max` — драбинка `step` мс, решта — одразу.
 *   <div class="kpis" use:revealKids>…плитки…</div>        (типово 35 мс, y 6, 220 мс, max 6)
 *   <tbody use:revealRows>…</tbody>                        (рядки: 20 мс, y 4, 180 мс, max 8)
 */
export interface RevealKidsParams {
	max?: number;
	delay?: number;
	step?: number;
	y?: number;
	duration?: number;
}
export const revealKids: Action<HTMLElement, RevealKidsParams | undefined> = (node, p) => {
	if (isReduced() || !inFirstWave()) return;
	const { max = 6, delay = 0, step = 35, y = 6, duration = DUR.base } = p ?? {};
	const kids = Array.from(node.children).filter((k) => !k.classList.contains('seg-ind')).slice(0, max) as HTMLElement[];
	kids.forEach((k, i) => play(k, delay + i * step, y, duration));
};

/** Рядки таблиці/списку: перші `max` (типово 8) — 20 мс драбинка, решта — одразу */
export const revealRows: Action<HTMLElement, RevealKidsParams | undefined> = (node, p) =>
	revealKids(node, { max: 8, step: 20, y: 4, duration: 180, ...p });
