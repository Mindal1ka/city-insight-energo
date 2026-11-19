<!--
	Анімоване число («набігає» від попереднього значення до нового). Українське форматування:
	пробіл між тисячами, кома в дробах, табличні цифри. null → «—».

	ВИКОРИСТАННЯ
	  import CountUp from '#lib/CountUp.svelte';
	  <CountUp value={1234.5} decimals={1} />                     → 1 234,5
	  <CountUp value={share * 100} suffix=" %" />                  → 86 %
	  <CountUp value={kwh} format={(n) => energy(n).v} />           → власне форматування
	  <CountUp value={null} />                                     → —

	Props: value:number|null, decimals?=0, duration?=800 (мс), format?:(n)=>string, suffix?:string
	Екранні зчитувачі отримують лише кінцеве значення; за prefers-reduced-motion — без анімації.
-->
<script lang="ts">
	import { isReduced } from './motion.ts';

	let {
		value,
		decimals = 0,
		duration = 800,
		format,
		suffix = ''
	}: {
		value: number | null | undefined;
		decimals?: number;
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
	let shown = $state(0);
	let from = 0;
	let raf = 0;

	const easeOutExpo = (t: number) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t));

	$effect(() => {
		const target = valid ? (value as number) : 0;
		cancelAnimationFrame(raf);
		if (!valid || isReduced() || duration <= 0 || from === target) {
			shown = from = target;
			return;
		}
		const start = from;
		const t0 = performance.now();
		const step = (now: number) => {
			const t = Math.min(1, (now - t0) / duration);
			shown = start + (target - start) * easeOutExpo(t);
			from = shown;
			if (t < 1) raf = requestAnimationFrame(step);
			else shown = from = target;
		};
		raf = requestAnimationFrame(step);
		return () => cancelAnimationFrame(raf);
	});

	const finalText = $derived(valid ? fmt(value as number) + suffix : '—');
</script>

{#if valid}<span class="countup"
		><span aria-hidden="true">{fmt(shown)}{suffix}</span><span class="visually-hidden"
			>{finalText}</span
		></span
	>{:else}<span class="countup">—</span>{/if}

<style>
	.countup {
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
</style>
