<!--
	Число з українським форматуванням: пробіл між тисячами, кома в дробах, табличні цифри. null → «—».
	Типово НЕ анімується — числа мають читатися одразу. animate=true дозволено лише для одного
	«героя» на екрані (напр. кільце окупності): коротке набігання ≤ 500 мс, лише при першому показі.

	ВИКОРИСТАННЯ
	  import CountUp from '#lib/CountUp.svelte';
	  <CountUp value={1234.5} decimals={1} />                     → 1 234,5
	  <CountUp value={share * 100} suffix=" %" />                  → 86 %
	  <CountUp value={kwh} format={(n) => energy(n).v} />           → власне форматування
	  <CountUp value={pct} animate duration={450} />               → єдине анімоване число на екрані

	Props: value:number|null, decimals?=0, animate?=false, duration?=450 (мс), format?:(n)=>string, suffix?:string
	У DOM завжди один текстовий вузол із числом (екранні зчитувачі й innerText читають значення один раз).
-->
<script lang="ts">
	import { isReduced, EASE } from './motion.ts';

	let {
		value,
		decimals = 0,
		animate = false,
		duration = 450,
		format,
		suffix = ''
	}: {
		value: number | null | undefined;
		decimals?: number;
		animate?: boolean;
		duration?: number;
		format?: (n: number) => string;
		suffix?: string;
	} = $props();

	const fmtCache = new Map<number, Intl.NumberFormat>();
	function fmt(n: number): string {
		if (format) return format(n);
		let f = fmtCache.get(decimals);
		if (!f) {
			f = new Intl.NumberFormat('uk-UA', {
				minimumFractionDigits: decimals,
				maximumFractionDigits: decimals
			});
			fmtCache.set(decimals, f);
		}
		return f.format(n);
	}

	const valid = $derived(value !== null && value !== undefined && Number.isFinite(value));
	/** Проміжне значення лише під час першого набігання; null — показуємо кінцеве */
	let shown = $state<number | null>(null);
	let played = false;

	$effect(() => {
		if (!animate || played || !valid || isReduced() || duration <= 0) return;
		played = true;
		const target = value as number;
		const t0 = performance.now();
		let raf = 0;
		const step = (now: number) => {
			const t = Math.min(1, (now - t0) / duration);
			shown = t < 1 ? target * EASE.out(t) : null;
			if (t < 1) raf = requestAnimationFrame(step);
		};
		shown = 0;
		raf = requestAnimationFrame(step);
		return () => {
			cancelAnimationFrame(raf);
			shown = null;
		};
	});

	const text = $derived(valid ? fmt(shown ?? (value as number)) + suffix : '—');
</script>

<span class="countup">{text}</span>

<style>
	.countup {
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
</style>
