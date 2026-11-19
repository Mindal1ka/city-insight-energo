/*
 * Спільний моушн-дизайн застосунку. Усе вимикається за prefers-reduced-motion.
 *
 * ВИКОРИСТАННЯ
 *   import { fadeUp, scaleIn, stagger, DUR, cubicOut, reducedMotion } from '#lib/motion.ts';
 *
 *   {#each items as it, i (it.id)}
 *     <li in:fadeUp={{ delay: stagger(i) }}>…</li>          // поява з підйомом на 8 px, «драбинкою»
 *   {/each}
 *   <div transition:scaleIn>…</div>                          // спливаюче вікно / підказка
 *   <div in:fadeUp={{ y: 16, duration: DUR.slow }}>…</div>
 *
 *   reducedMotion.current   — true, якщо користувач просив менше анімації (реактивно в .svelte)
 *   isReduced()             — те саме, разова перевірка (для звичайного TS-коду, rAF-циклів)
 *   DUR = { fast: 150, base: 240, slow: 420 }  — тривалості, мс
 *   stagger(i, step = 40, max = 400) — затримка для i-го елемента списку, мс
 *
 * CSS-аналоги (app.css): змінні --dur-fast / --dur-base / --dur-slow, --ease-out, --ease-spring,
 * класи .fade-in, .lift (підйом при наведенні), .press (стискання при натисканні).
 */
import { prefersReducedMotion } from 'svelte/motion';
import { cubicOut, cubicInOut, quintOut, backOut, expoOut, linear } from 'svelte/easing';
import type { TransitionConfig } from 'svelte/transition';

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

export const DUR = { fast: 150, base: 240, slow: 420 } as const;

/** Затримка для i-го елемента списку («драбинка»), з верхньою межею, щоб довгі списки не чекали */
export function stagger(i: number, step = 35, max = 280): number {
	return isReduced() ? 0 : Math.min(i * step, max);
}

export interface FadeUpParams {
	delay?: number;
	duration?: number;
	y?: number;
	easing?: (t: number) => number;
}

/** Поява: прозорість + підйом на y px (типово 8) */
export function fadeUp(
	_node: Element,
	{ delay = 0, duration = DUR.base, y = 8, easing = cubicOut }: FadeUpParams = {}
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

/** Поява з легким збільшенням (0.96 → 1): спливаючі вікна, підказки, бейджі */
export function scaleIn(
	_node: Element,
	{ delay = 0, duration = DUR.fast + 40, start = 0.96, easing = cubicOut }: ScaleInParams = {}
): TransitionConfig {
	if (isReduced()) return { duration: 0 };
	return {
		delay,
		duration,
		easing,
		css: (t) => `opacity:${t};transform:scale(${start + (1 - start) * t})`
	};
}
