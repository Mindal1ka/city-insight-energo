<!-- Кільце прогресу (0–100 %) з анімованим заповненням; reduced-motion — одразу кінцевий стан -->
<script lang="ts">
	import CountUp from '#lib/CountUp.svelte';
	import { isReduced } from '#lib/motion.ts';

	let { pct, size = 132, label = 'окуплено' }: { pct: number | null; size?: number; label?: string } = $props();

	const R = 52;
	const C = 2 * Math.PI * R;
	let shown = $state(0);
	$effect(() => {
		const v = Math.max(0, Math.min(100, pct ?? 0));
		if (isReduced()) {
			shown = v;
			return;
		}
		const id = requestAnimationFrame(() => (shown = v));
		return () => cancelAnimationFrame(id);
	});
	const done = $derived((pct ?? 0) >= 100);
</script>

<div class="ring" style="--s: {size}px" role="img" aria-label="{label} {pct ?? 0} %">
	<svg viewBox="0 0 120 120" aria-hidden="true">
		<circle class="trk" cx="60" cy="60" r={R} />
		<circle class="bar" class:done cx="60" cy="60" r={R} stroke-dasharray={C} stroke-dashoffset={C * (1 - shown / 100)} />
	</svg>
	<div class="c" aria-hidden="true">
		<b><CountUp value={pct} suffix=" %" duration={1100} /></b>
		<span>{label}</span>
	</div>
</div>

<style>
	.ring {
		position: relative;
		width: var(--s);
		height: var(--s);
		flex: none;
	}
	svg {
		width: 100%;
		height: 100%;
		transform: rotate(-90deg);
	}
	circle {
		fill: none;
		stroke-width: 11;
	}
	.trk {
		stroke: var(--line-soft);
	}
	.bar {
		stroke: var(--sun-strong);
		stroke-linecap: round;
		transition: stroke-dashoffset 1.1s var(--ease-out);
	}
	.bar.done {
		stroke: var(--surplus);
	}
	.c {
		position: absolute;
		inset: 0;
		display: grid;
		place-content: center;
		text-align: center;
		line-height: 1.1;
	}
	b {
		font-size: 1.5rem;
		color: var(--ink);
		font-variant-numeric: tabular-nums;
	}
	span {
		font-size: var(--fs-xs);
		color: var(--muted);
	}
	@media (prefers-reduced-motion: reduce) {
		.bar {
			transition: none;
		}
	}
</style>
