<!-- Розсіювання: K (вертикаль) проти споживання (горизонталь, логарифмічна шкала).
     Форма точки = клас (● ефективно, ▼ не вистачає, ▲ надлишок) — колір не єдиний сигнал.
     Наведення/фокус → підказка; клік або Enter → картка об'єкта. Клавіатура: ←/→ між точками. -->
<script lang="ts">
	import { CLASS_BY_ID, kOf, type SesItem, type KClass } from './DashData.ts';
	import { catLabel } from '../categories.ts';

	let {
		items,
		low = 0.8,
		high = 1.2,
		unit = 'кВт·год',
		onopen
	}: { items: SesItem[]; low?: number; high?: number; unit?: string; onopen: (id: number) => void } = $props();

	const YMAX = 2.4;
	let w = $state(560);
	const H = 300;
	const m = { l: 40, r: 14, t: 12, b: 38 };
	const iw = $derived(Math.max(120, w - m.l - m.r));
	const ih = H - m.t - m.b;

	const pts = $derived(
		items
			.filter((i) => i.k !== null && Number.isFinite(i.k) && (i.cons_kwh ?? 0) > 0)
			.sort((a, b) => (a.cons_kwh ?? 0) - (b.cons_kwh ?? 0))
	);
	const lo = $derived(pts.length ? Math.floor(Math.log10(pts[0].cons_kwh as number)) : 2);
	const hi = $derived(pts.length ? Math.ceil(Math.log10(pts[pts.length - 1].cons_kwh as number)) : 6);
	const span = $derived(Math.max(1, hi - lo));
	const x = (v: number) => m.l + ((Math.log10(v) - lo) / span) * iw;
	const y = (k: number) => m.t + ih - (Math.min(k, YMAX) / YMAX) * ih;
	const decades = $derived(Array.from({ length: span + 1 }, (_, i) => lo + i));
	const dLabel = (e: number) => (e >= 6 ? `${10 ** (e - 6)} млн` : e >= 3 ? `${10 ** (e - 3)} тис.` : `${10 ** e}`);

	let act = $state<number | null>(null);
	const cur = $derived(act !== null ? pts[act] : null);
	const fmt = (n: number | null, d = 0) => (n === null ? '—' : n.toLocaleString('uk-UA', { maximumFractionDigits: d, minimumFractionDigits: d }));

	function key(e: KeyboardEvent) {
		if (!pts.length) return;
		if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
			act = act === null ? 0 : Math.min(pts.length - 1, act + 1);
			e.preventDefault();
		} else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
			act = act === null ? 0 : Math.max(0, act - 1);
			e.preventDefault();
		} else if (e.key === 'Home') {
			act = 0;
			e.preventDefault();
		} else if (e.key === 'End') {
			act = pts.length - 1;
			e.preventDefault();
		} else if ((e.key === 'Enter' || e.key === ' ') && cur) {
			onopen(cur.id);
			e.preventDefault();
		} else if (e.key === 'Escape') act = null;
	}
	function shape(c: KClass, s = 5.5): string {
		if (c === 'Не вистачає') return `M${-s},${-s * 0.8}L${s},${-s * 0.8}L0,${s}Z`;
		if (c === 'Надлишок') return `M${-s},${s * 0.8}L${s},${s * 0.8}L0,${-s}Z`;
		return `M${-s * 0.85},0a${s * 0.85},${s * 0.85} 0 1,0 ${s * 1.7},0a${s * 0.85},${s * 0.85} 0 1,0 ${-s * 1.7},0`;
	}
	const tipX = $derived(cur ? Math.min(Math.max(x(cur.cons_kwh as number), m.l + 105), m.l + iw - 105) : 0);
	const tipY = $derived(cur ? (y(cur.k as number) > m.t + 90 ? y(cur.k as number) - 84 : y(cur.k as number) + 14) : 0);
</script>

<div class="ds" bind:clientWidth={w}>
	<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
	<svg
		viewBox="0 0 {w} {H}"
		width={w}
		height={H}
		role="application"
		aria-roledescription="діаграма розсіювання"
		aria-label="K проти споживання, {pts.length} об'єктів. Стрілки — вибір, Enter — відкрити."
		tabindex="0"
		onkeydown={key}
		onblur={() => (act = null)}
		onpointerleave={() => (act = null)}
	>
		<rect x={m.l} y={y(low)} width={iw} height={y(0) - y(low)} fill={CLASS_BY_ID['Не вистачає'].soft} opacity="0.6" />
		<rect x={m.l} y={y(high)} width={iw} height={y(low) - y(high)} fill={CLASS_BY_ID['Ефективно'].soft} opacity="0.9" />
		<rect x={m.l} y={y(YMAX)} width={iw} height={y(high) - y(YMAX)} fill={CLASS_BY_ID['Надлишок'].soft} opacity="0.6" />
		{#each [0, 0.4, low, 1, high, 1.6, 2, YMAX] as t (t)}
			<line x1={m.l} x2={m.l + iw} y1={y(t)} y2={y(t)} class="grid" class:one={t === 1} />
			<text class="ax" class:strong={t === low || t === high || t === 1} x={m.l - 6} y={y(t) + 4} text-anchor="end"
				>{t === YMAX ? `≥${t.toLocaleString('uk-UA')}` : t.toLocaleString('uk-UA')}</text
			>
		{/each}
		{#each decades as e (e)}
			<line x1={x(10 ** e)} x2={x(10 ** e)} y1={m.t} y2={m.t + ih} class="grid" />
			<text class="ax" x={x(10 ** e)} y={m.t + ih + 15} text-anchor={e === hi ? 'end' : e === lo ? 'start' : 'middle'}>{dLabel(e)}</text>
		{/each}
		<text class="ax" x={m.l + iw} y={H - 3} text-anchor="end">Спожито, {unit}</text>
		<text class="ax" x={4} y={m.t + 4} text-anchor="start">K</text>

		{#each pts as p, i (p.id)}
			{@const c = kOf(p)}
			{@const meta = CLASS_BY_ID[c]}
			<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
			<g
				class="pt"
				class:on={act === i}
				style="transform:translate({x(p.cons_kwh as number)}px,{y(p.k as number)}px)"
				onpointerenter={() => (act = i)}
				onclick={() => onopen(p.id)}
			>
				<circle r="11" fill="transparent" />
				<path d={shape(c)} fill={meta.color} stroke="#fff" stroke-width="1.2" fill-opacity="0.85" />
			</g>
		{/each}
		{#if cur}
			{@const meta = CLASS_BY_ID[kOf(cur)]}
			<circle cx={x(cur.cons_kwh as number)} cy={y(cur.k as number)} r="10" fill="none" stroke="var(--ink)" stroke-width="2" pointer-events="none" />
			<g class="tip" transform="translate({tipX - 105},{tipY})" pointer-events="none">
				<rect width="210" height="72" rx="9" />
				<text x="10" y="19" class="nm">{cur.name.length > 30 ? cur.name.slice(0, 29) + '…' : cur.name}</text>
				<text x="10" y="38">{catLabel(cur.category_short)}</text>
				<text x="10" y="58"
					><tspan font-weight="800" fill={meta.soft}>{meta.sym} K {fmt(cur.k, 2)}</tspan> · {fmt(cur.cons_kwh)} {unit}</text
				>
			</g>
		{/if}
	</svg>
	<div class="lg" aria-hidden="true">
		{#each ['Ефективно', 'Не вистачає', 'Надлишок'] as c (c)}
			{@const meta = CLASS_BY_ID[c as KClass]}
			<span><svg width="14" height="14" viewBox="-7 -7 14 14"><path d={shape(c as KClass, 5)} fill={meta.color} /></svg>{meta.short}</span>
		{/each}
	</div>
	{#if cur}<p class="visually-hidden" aria-live="polite">{cur.name}, K {fmt(cur.k, 2)}, {fmt(cur.cons_kwh)} {unit}</p>{/if}
</div>

<style>
	.ds {
		width: 100%;
		min-width: 0;
	}
	svg {
		display: block;
		overflow: visible;
		border-radius: 8px;
	}
	svg:focus-visible {
		outline: 3px solid var(--focus);
		outline-offset: 3px;
	}
	.grid {
		stroke: var(--line-soft);
	}
	.grid.one {
		stroke: var(--ink);
		stroke-dasharray: 3 3;
		opacity: 0.45;
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
	.pt {
		cursor: pointer;
		transition: transform var(--dur-slow) var(--ease-out);
	}
	.pt path {
		transition: transform var(--dur-fast);
	}
	.pt.on path {
		transform: scale(1.5);
	}
	.tip rect {
		fill: var(--navy-deep, #0a1f38);
		opacity: 0.95;
	}
	.tip text {
		fill: #dbe5f1;
		font-size: 12px;
		font-variant-numeric: tabular-nums;
	}
	.tip .nm {
		fill: #fff;
		font-weight: 700;
		font-size: 12.5px;
	}
	.lg {
		display: flex;
		gap: 1rem;
		flex-wrap: wrap;
		font-size: 0.85rem;
		color: var(--text-2);
		margin-top: 0.35rem;
	}
	.lg span {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	@media (prefers-reduced-motion: reduce) {
		.pt,
		.pt path {
			transition: none;
		}
	}
</style>
