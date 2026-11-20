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
 *   <tbody use:revealRows>…</tbody>            // видимі рядки — драбинка 20 мс, нижчі — при прокручуванні
 *
 * У видимій області анімує лише перша «хвиля» вмісту на маршруті: перший вузол із reveal відкриває
 * вікно ~1.2 с для цього шляху (а також вміст, що заміняє Skeleton, хоч би як довго вантажилось);
 * те, що змонтується у видимій області пізніше (зміна фільтра, періоду), з'являється миттєво.
 * Блоки нижче екрана завжди чекають прихованими (.rv-wait) і з'являються при прокручуванні до них
 * (спільний IntersectionObserver). Блоки без власного reveal підхоплює autoReveal на <main>
 * у +layout.svelte. Лише opacity + transform, WAAPI,
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
	if (now - t0 < WAVE_MS) return true;
	// Дані прийшли пізніше за вікно: вміст, що заміняє каркас (Skeleton), теж з'являється з рухом
	return now - skelEnd < SKEL_GRACE_MS || (skelLive > 0 && now - t0 < 15000);
}

/** Каркаси на екрані: лічильник і час зняття останнього (див. inFirstWave) */
let skelLive = 0;
let skelEnd = -1e9;
const SKEL_GRACE_MS = 300;

/** Викликає Skeleton.svelte при монтуванні; повернена функція — при знятті */
export function skeletonMounted(): () => void {
	skelLive++;
	return () => {
		skelLive = Math.max(0, skelLive - 1);
		skelEnd = performance.now();
	};
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

/*
 * ПОЯВА ПРИ ПРОКРУЧУВАННІ. Блок, що змонтувався нижче видимої області, ховається (клас .rv-wait у
 * app.css: opacity 0 + зсув, макет не змінюється) і з'являється, коли доїде до екрана. Один спільний
 * IntersectionObserver; unobserve одразу після показу. Блоки, що зайшли в екран одним кадром,
 * отримують невелику драбинку (зверху вниз, зліва направо).
 */
type Pending = { y: number; duration: number; step: number; run?: (k: number) => void };
const pending = new Map<Element, Pending>();
let io: IntersectionObserver | null = null;

function getIO(): IntersectionObserver {
	if (io) return io;
	io = new IntersectionObserver(
		(entries) => {
			const hits = entries
				.filter((e) => e.isIntersecting && pending.has(e.target))
				.sort(
					(a, b) =>
						a.boundingClientRect.top - b.boundingClientRect.top || a.boundingClientRect.left - b.boundingClientRect.left
				);
			hits.forEach((e, k) => {
				const el = e.target as HTMLElement;
				const o = pending.get(el)!;
				pending.delete(el);
				io!.unobserve(el);
				if (o.run) return o.run(k);
				el.classList.remove('rv-wait');
				el.style.removeProperty('--rv-y0');
				play(el, Math.min(k, 6) * o.step, o.y, o.duration);
			});
		},
		{ rootMargin: '0px 0px -4% 0px', threshold: 0 }
	);
	return io;
}

/** Зняти блок з очікування (вузол знищено або більше не потрібен) — він не лишиться прихованим */
export function unwatch(el: Element): void {
	if (pending.delete(el)) io?.unobserve(el);
	if (!el.classList.contains('rv-wait')) return;
	el.classList.remove('rv-wait');
	(el as HTMLElement).style?.removeProperty('--rv-y0');
}

/** Викликати run(k) один раз, коли елемент доїде до екрана (k — номер у пачці, що зайшла одним кадром); повертає скасування */
export function whenVisible(el: Element, run: (k: number) => void): () => void {
	pending.set(el, { y: 0, duration: 0, step: 0, run });
	getIO().observe(el);
	return () => {
		pending.delete(el);
		io?.unobserve(el);
	};
}

/**
 * Одна поява блоку: у видимій області — одразу (лише в першій хвилі; фільтри й повторні рендери —
 * без руху); нижче екрана — при прокручуванні до нього (користувач його ще не бачив); вище екрана
 * чи прихований (display:none) — без руху. Повертає true, якщо блок узято в роботу.
 */
export function revealNode(el: HTMLElement, delay = 0, y = 6, duration: number = DUR.base, step = 35): boolean {
	if (isReduced() || typeof el.animate !== 'function' || pending.has(el)) return false;
	const wave = inFirstWave();
	const r = el.getBoundingClientRect();
	if (!r.width && !r.height) return false;
	const vh = window.innerHeight || document.documentElement.clientHeight;
	if (r.top < vh * 0.96) {
		if (r.bottom <= 0 || !wave) return false;
		play(el, delay, y, duration);
		return true;
	}
	if (typeof IntersectionObserver === 'undefined') return false;
	el.style.setProperty('--rv-y0', `${y}px`);
	el.classList.add('rv-wait');
	pending.set(el, { y, duration, step });
	getIO().observe(el);
	return true;
}

export const reveal: Action<HTMLElement, number | RevealParams | undefined> = (node, p) => {
	node.dataset.rv = '';
	const o: RevealParams = typeof p === 'number' ? { i: p } : (p ?? {});
	const i = Math.min(o.i ?? 0, 6);
	revealNode(node, (o.delay ?? 0) + i * (o.step ?? 35), o.y ?? 6, o.duration ?? DUR.base, o.step ?? 35);
	return { destroy: () => unwatch(node) };
};

/**
 * Діти контейнера по черзі: видимі — драбинка `step` мс (після `max`-го — без подальшої затримки);
 * діти нижче екрана з'являються при прокручуванні до них.
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
	node.dataset.rv = '';
	const { max = 6, delay = 0, step = 35, y = 6, duration = DUR.base } = p ?? {};
	const kids = Array.from(node.children).filter((k) => !k.classList.contains('seg-ind')) as HTMLElement[];
	if (isReduced()) return;
	let n = 0;
	for (const k of kids) {
		// Видимі після перших `max` — разом з останнім кроком драбинки (не «вискакують» на високих екранах)
		revealNode(k, delay + Math.min(n, max) * step, y, duration, step);
		n++;
	}
	return { destroy: () => kids.forEach(unwatch) };
};

/** Рядки таблиці/списку: перші `max` (типово 8) — 20 мс драбинка, решта видимих — разом, нижчі — при прокручуванні */
export const revealRows: Action<HTMLElement, RevealKidsParams | undefined> = (node, p) =>
	revealKids(node, { max: 8, step: 20, y: 4, duration: 180, ...p });

/*
 * АВТОПОЯВА для <main> (use:autoReveal у +layout.svelte): кожен блок сторінки (картки, секції,
 * таблиці, графіки, списки) з'являється один раз — у першій хвилі або при прокручуванні. Високі
 * обгортки (вищі за екран) розбиваються на дітей, тож нижні частини довгих сторінок теж
 * анімуються. Блоки з власною появою (use:reveal*, <Reveal>) і [data-no-reveal] пропускаються.
 * Ловить і заміну каркаса (Skeleton) на вміст усередині вже показаних блоків. Фонове оновлення
 * даних нових вузлів зазвичай не створює, а якщо й створює — у видимій області вони без руху.
 */
const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'LINK', 'TEMPLATE', 'DIALOG', 'BR', 'HR']);
const OWN = '[data-rv], [data-no-reveal], .reveal, .rv-wait';

function collectBlocks(el: Element, out: HTMLElement[], depth: number, vh: number) {
	if (!(el instanceof HTMLElement) || SKIP_TAGS.has(el.tagName)) return;
	if (el.closest(OWN) || el.classList.contains('skeleton') || el.classList.contains('sk-root')) return;
	const kids = Array.from(el.children).filter((k) => !SKIP_TAGS.has(k.tagName));
	const cs = getComputedStyle(el);
	if (cs.display === 'contents') {
		for (const k of kids) collectBlocks(k, out, depth + 1, vh);
		return;
	}
	if (cs.display === 'none' || cs.position === 'fixed' || cs.position === 'absolute') return;
	const r = el.getBoundingClientRect();
	if (!r.width && !r.height) return;
	// Висока обгортка або контейнер із власною появою всередині — анімуємо дітей, а не цілий блок
	// (інакше нижня частина «вже показана» або подвійна прозорість)
	if (depth < 6 && kids.length && (r.height > vh * 0.9 || el.querySelector('[data-rv], .reveal'))) {
		for (const k of kids) collectBlocks(k, out, depth + 1, vh);
		return;
	}
	out.push(el);
}

function isSkeletonNode(n: Node): boolean {
	return (
		n instanceof Element &&
		(n.classList.contains('skeleton') ||
			n.classList.contains('sk-root') ||
			n.classList.contains('sk-kpi') ||
			!!n.querySelector('.skeleton'))
	);
}

export const autoReveal: Action<HTMLElement> = (main) => {
	if (typeof MutationObserver === 'undefined') return;
	const handle = (roots: Element[]) => {
		if (isReduced() || !roots.length) return;
		const vh = window.innerHeight || document.documentElement.clientHeight;
		const blocks: HTMLElement[] = [];
		for (const r of roots) collectBlocks(r, blocks, 0, vh);
		let n = 0;
		for (const b of blocks) if (revealNode(b, Math.min(n, 6) * 35)) n++;
	};
	handle(Array.from(main.children));
	const mo = new MutationObserver((recs) => {
		// Блоки, що зникли до показу (зміна сторінки, фільтра), не тримаємо в спостерігачі
		if (pending.size && recs.some((r) => r.removedNodes.length))
			for (const el of [...pending.keys()]) if (!el.isConnected) unwatch(el);
		const swapped = new Set<Node>();
		for (const rec of recs) if (Array.from(rec.removedNodes).some(isSkeletonNode)) swapped.add(rec.target);
		const roots: Element[] = [];
		for (const rec of recs) {
			if (rec.target !== main && !swapped.has(rec.target)) continue;
			rec.addedNodes.forEach((a) => {
				if (!(a instanceof HTMLElement) || !a.isConnected || isSkeletonNode(a)) return;
				// Дрібні вставки на місці каркаса (іконка, текст у рядку) не анімуємо
				if (rec.target !== main && (a.offsetHeight < 24 || a.offsetWidth < 60)) return;
				roots.push(a);
			});
		}
		handle(roots);
	});
	mo.observe(main, { childList: true, subtree: true });
	return {
		destroy() {
			mo.disconnect();
			main.querySelectorAll('.rv-wait').forEach(unwatch);
		}
	};
};

/**
 * Нова навігація (зокрема повторний візит, «назад/вперед») відкриває нову першу хвилю для
 * шляху-цілі: сторінка знову з'являється з драбинкою, а не «вискакує». Викликається з onNavigate.
 */
export function resetWave(path?: string): void {
	if (path) firstWave.delete(path);
}

/** Рядок/картка списку, що з'явилася після фільтра чи створення: 4 px + проявлення, 180 мс */
export function listIn(_node: Element, { delay = 0 }: { delay?: number } = {}): TransitionConfig {
	if (isReduced()) return { duration: 0 };
	return {
		delay,
		duration: 180,
		easing: EASE.out,
		css: (t, u) => `opacity:${t.toFixed(3)};transform:translateY(${(u * 4).toFixed(2)}px)`
	};
}

/** Рядок, що зникає: швидко геть (100 мс), без зсуву — сусіди під'їжджають через animate:flip */
export function listOut(_node: Element): TransitionConfig {
	if (isReduced()) return { duration: 0 };
	return { duration: DUR.press, easing: EASE.in, css: (t) => `opacity:${t.toFixed(3)}` };
}

/**
 * Короткий «спалах» тла при зміні ключа (новий статус, щойно створений запис): 600 мс ease-out.
 * Перший показ — без спалаху; передайте { key, now: true }, щоб спалахнути одразу при монтуванні.
 * Окремий шар із opacity — без анімації background-color.
 */
export const flash: Action<HTMLElement, unknown> = (node, key) => {
	let last = key;
	const run = () => {
		if (isReduced() || typeof node.animate !== 'function') return;
		if (getComputedStyle(node).position === 'static') node.style.position = 'relative';
		const layer = document.createElement('span');
		layer.setAttribute('aria-hidden', 'true');
		layer.style.cssText =
			'position:absolute;inset:0;border-radius:inherit;background:var(--accent-soft,#e6f0ff);pointer-events:none;z-index:0;mix-blend-mode:multiply';
		node.prepend(layer);
		layer
			.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 600, easing: 'cubic-bezier(0.2, 0.7, 0.2, 1)' })
			.finished.finally(() => layer.remove());
	};
	if (key && typeof key === 'object' && (key as { now?: boolean }).now) queueMicrotask(run);
	return {
		update(k) {
			if (k !== last) {
				last = k;
				run();
			}
		}
	};
};

/**
 * Активний пункт бічного меню: одна «плашка», що ковзає між пунктами (FLIP, 220 мс ease-in-out).
 * Шукає a[aria-current="page"] на будь-якій глибині; стилі .nav-ind — у app.css.
 */
export const navIndicator: Action<HTMLElement> = (node) => {
	const ind = document.createElement('span');
	ind.className = 'nav-ind';
	ind.setAttribute('aria-hidden', 'true');
	node.prepend(ind);
	node.classList.add('has-nav-ind');
	if (getComputedStyle(node).position === 'static') node.style.position = 'relative';
	let px = -1, py = -1, ph = 0, first = true;
	const place = () => {
		const sel = node.querySelector<HTMLElement>('a[aria-current="page"]');
		if (!sel) {
			ind.style.opacity = '0';
			first = true;
			return;
		}
		const nb = node.getBoundingClientRect();
		const r = sel.getBoundingClientRect();
		const x = r.left - nb.left + node.scrollLeft, y = r.top - nb.top + node.scrollTop;
		if (!r.width) return;
		if (x === px && y === py && r.height === ph && !first) return;
		ind.style.width = r.width + 'px';
		ind.style.height = r.height + 'px';
		ind.style.transition = 'none';
		if (first || isReduced()) {
			ind.style.transform = `translate(${x}px,${y}px)`;
		} else {
			ind.style.transform = `translate(${px}px,${py}px)`;
			void ind.offsetWidth;
			ind.style.transition = '';
			ind.style.transform = `translate(${x}px,${y}px)`;
		}
		ind.style.opacity = '1';
		px = x; py = y; ph = r.height;
		first = false;
	};
	requestAnimationFrame(place);
	const mo = new MutationObserver(place);
	mo.observe(node, { subtree: true, attributes: true, attributeFilter: ['aria-current'], childList: true });
	const ro = new ResizeObserver(() => {
		first = true;
		place();
	});
	ro.observe(node);
	return {
		destroy() {
			mo.disconnect();
			ro.disconnect();
			ind.remove();
			node.classList.remove('has-nav-ind');
		}
	};
};

/**
 * Закриття модального <dialog> (шухляда, палітра) з рухом: панель 160 мс --ease-in у бік, звідки
 * прийшла, фон гасне паралельно; потім справжній close() (фокус повертає сам діалог/компонент).
 * Відкриття — CSS-анімація [open] (260–300 мс --ease-emph).
 */
export function closeDialog(dlg: HTMLDialogElement, { x = 0, y = 0 }: { x?: number; y?: number } = {}): void {
	if (!dlg.open || dlg.dataset.closing) return;
	if (isReduced() || typeof dlg.animate !== 'function') {
		dlg.close();
		return;
	}
	dlg.dataset.closing = '1';
	const opts = { duration: 160, easing: 'cubic-bezier(0.4, 0, 1, 1)', fill: 'forwards' as FillMode };
	const a = dlg.animate([{ opacity: 1, transform: 'none' }, { opacity: 0, transform: `translate(${x}px,${y}px)` }], opts);
	try {
		dlg.animate([{ opacity: 1 }, { opacity: 0 }], { ...opts, pseudoElement: '::backdrop' });
	} catch {
		/* старі рушії без pseudoElement — фон зникне разом із close() */
	}
	a.finished
		.catch(() => {})
		.finally(() => {
			delete dlg.dataset.closing;
			dlg.getAnimations({ subtree: false }).forEach((x) => x.cancel());
			try {
				dlg.getAnimations().forEach((x) => x.cancel());
			} catch {
				/* ignore */
			}
			if (dlg.open) dlg.close();
		});
}
