<!-- Розподіл K: гістограма 0–2 із зонами «Не вистачає / Ефективно / Надлишок» -->
<script lang="ts">
	import { CLASS_BY_ID, type KClass } from './DashData.ts';

	let {
		bins,
		low = 0.8,
		high = 1.2
	}: { bins: { x0: number; x1: number; n: number }[]; low?: number; high?: number } = $props();

	let w = $state(560);
	const H = 250;
	const m = { l: 34, r: 10, t: 24, b: 34 };
	const iw = $derived(Math.max(100, w - m.l - m.r));
	const ih = H - m.t - m.b;
	const XMAX = 2;
	const x = (v: number) => m.l + (v / XMAX) * iw;


	const maxN = $derived(Math.max(1, ...bins.map((b) => b.n)));
	const yMax = $derived(maxN <= 5 ? maxN : Math.ceil(maxN / 5) * 5);
	const y = (n: number) => m.t + ih - (n / yMax) * ih;
	const ticks = $derived(yMax <= 5 ? Array.from({ length: yMax + 1 }, (_, i) => i) : [0, yMax / 5, (2 * yMax) / 5, (3 * yMax) / 5, (4 * yMax) / 5, yMax].map(Math.round));

	const zone = (v: number): KClass => (v < low ? 'Не вистачає' : v > high ? 'Надлишок' : 'Ефективно');
	const total = $derived(bins.reduce((s, b) => s + b.n, 0));
	const desc = $derived(
		`Об'єктів із K: ${total}. Не вистачає: ${bins.filter((b) => b.x1 <= low + 1e-9).reduce((s, b) => s + b.n, 0)}, ефективно: ${bins
			.filter((b) => b.x0 >= low - 1e-9 && b.x1 <= high + 1e-9)
			.reduce((s, b) => s + b.n, 0)}, надлишок: ${bins.filter((b) => b.x0 >= high - 1e-9).reduce((s, b) => s + b.n, 0)}.`
	);
	const uid = 'dh-' + Math.random().toString(36).slice(2, 8);
	let hover = $state<number | null>(null);
</script>

<div class="dh" bind:clientWidth={w}>
	<svg viewBox="0 0 {w} {H}" width={w} height={H} role="img" aria-labelledby="{uid}-t {uid}-d">
		<title id="{uid}-t">Розподіл K</title>
		<desc id="{uid}-d">{desc}</desc>
		<!-- зони -->
		{#each [{ a: 0, b: low, c: 'Не вистачає' }, { a: low, b: high, c: 'Ефективно' }, { a: high, b: XMAX, c: 'Надлишок' }] as z (z.c)}
			{@const meta = CLASS_BY_ID[z.c as KClass]}
			<rect x={x(z.a)} y={m.t} width={x(z.b) - x(z.a)} height={ih} fill={meta.soft} opacity="0.75" />
			<text class="zl" x={(x(z.a) + x(z.b)) / 2} y={m.t - 8} text-anchor="middle" fill={meta.ink}>{x(z.b) - x(z.a) < 84 ? meta.sym : `${meta.sym} ${meta.short}`}</text>
		{/each}
		<!-- сітка -->
		{#each ticks as t (t)}
			<line x1={m.l} x2={m.l + iw} y1={y(t)} y2={y(t)} class="grid" />
			<text class="ax" x={m.l - 6} y={y(t) + 4} text-anchor="end">{t}</text>
		{/each}
		<!-- стовпці -->
		{#each bins as b, i (b.x0)}
			{@const n = b.n}
			{@const meta = CLASS_BY_ID[zone((b.x0 + b.x1) / 2)]}
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<g onpointerenter={() => (hover = i)} onpointerleave={() => (hover = null)}>
				<rect x={x(b.x0)} y={m.t} width={x(b.x1) - x(b.x0)} height={ih} fill="transparent" />
				<rect
					x={x(b.x0) + 1.5}
					y={y(n)}
					width={Math.max(1, x(b.x1) - x(b.x0) - 3)}
					height={Math.max(0, m.t + ih - y(n))}
					rx="3"
					fill={meta.color}
					opacity={hover === null || hover === i ? 1 : 0.55}
					class="bar"
				/>
				{#if hover === i && b.n > 0}
					<text class="val" x={(x(b.x0) + x(b.x1)) / 2} y={y(b.n) - 5} text-anchor="middle">{b.n}</text>
				{/if}
			</g>
		{/each}
		<!-- осі -->
		<line x1={m.l} x2={m.l + iw} y1={m.t + ih} y2={m.t + ih} class="axis" />
		{#each [0, 0.4, low, 1, high, 1.6, 2] as t (t)}
			<text class="ax" class:strong={t === low || t === high || t === 1} x={x(t)} y={m.t + ih + 16} text-anchor="middle"
				>{t === 2 ? '≥2' : t.toLocaleString('uk-UA')}</text
			>
		{/each}
		<line x1={x(1)} x2={x(1)} y1={m.t} y2={m.t + ih} class="ideal" />
		<text class="ax" x={m.l + iw} y={H - 2} text-anchor="end">K</text>
	</svg>
</div>

<style>
	.dh {
		width: 100%;
		min-width: 0;
	}
	svg {
		display: block;
		overflow: visible;
	}
	.grid {
		stroke: var(--line-soft);
	}
	.axis {
		stroke: var(--line-strong);
	}
	.ideal {
		stroke: var(--ink);
		stroke-dasharray: 3 3;
		opacity: 0.5;
	}
	.ax {
		font-size: 11px;
		fill: var(--muted);
		font-variant-numeric: tabular-nums;
	}
	.ax.strong {
		font-weight: 700;
		fill: var(--text);
	}
	.zl {
		font-size: 11.5px;
		font-weight: 700;
	}
	.val {
		font-size: 12px;
		font-weight: 700;
		fill: var(--ink);
	}
	/* Перший показ — стовпці ростуть від осі (transform), далі числа одразу кінцеві */
	@media (prefers-reduced-motion: no-preference) {
		.bar {
			transform-box: fill-box;
			transform-origin: 50% 100%;
			animation: dh-grow 560ms var(--ease-emph) both;
		}
	}
	@keyframes dh-grow {
		from {
			transform: scaleY(0);
		}
	}
	rect {
		transition: opacity var(--dur-fast) var(--ease-out);
	}
</style>
