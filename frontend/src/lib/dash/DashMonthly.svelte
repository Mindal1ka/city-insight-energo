<!-- Помісячно: генерація СЕС (стовпці) проти споживання (лінія з точками), МВт·год -->
<script lang="ts">
	import { Tween } from 'svelte/motion';
	import { cubicOut, isReduced } from '../motion.ts';
	import type { SesMonth } from './DashData.ts';

	let { months }: { months: SesMonth[] } = $props();
	const MN = ['Січ', 'Лют', 'Бер', 'Кві', 'Тра', 'Чер', 'Лип', 'Сер', 'Вер', 'Жов', 'Лис', 'Гру'];

	let w = $state(560);
	const H = 220;
	const m = { l: 40, r: 10, t: 14, b: 28 };
	const iw = $derived(Math.max(120, w - m.l - m.r));
	const ih = H - m.t - m.b;
	const rows = $derived([...months].sort((a, b) => a.month - b.month));
	const maxV = $derived(Math.max(1, ...rows.flatMap((r) => [r.gen_kwh, r.cons_kwh])) / 1000);
	const step = $derived(niceStep(maxV / 4));
	const yMax = $derived(Math.ceil(maxV / step) * step);
	function niceStep(v: number) {
		const p = Math.pow(10, Math.floor(Math.log10(v || 1)));
		const f = v / p;
		return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p;
	}
	const bw = $derived(iw / 12);
	const xc = (i: number) => m.l + bw * i + bw / 2;
	const y = (mwh: number) => m.t + ih - (mwh / yMax) * ih;

	const g = new Tween<number[]>(Array(12).fill(0), { duration: 700, easing: cubicOut });
	const c = new Tween<number[]>(Array(12).fill(0), { duration: 700, easing: cubicOut });
	$effect(() => {
		const d = isReduced() ? 0 : 700;
		g.set(rows.map((r) => r.gen_kwh / 1000), { duration: d });
		c.set(rows.map((r) => r.cons_kwh / 1000), { duration: d });
	});
	const line = $derived(c.current.map((v, i) => `${i ? 'L' : 'M'}${xc(i).toFixed(1)},${y(v).toFixed(1)}`).join(''));
	let hover = $state<number | null>(null);
	const f1 = (v: number) => v.toLocaleString('uk-UA', { maximumFractionDigits: 1 });
	const desc = $derived(rows.map((r) => `${MN[r.month - 1]}: ${f1(r.gen_kwh / 1000)} / ${f1(r.cons_kwh / 1000)}`).join('; '));
</script>

<div class="dm" bind:clientWidth={w}>
	<svg viewBox="0 0 {w} {H}" width={w} height={H} role="img" aria-label="Помісячно, МВт·год, генерація / споживання. {desc}">
		{#each Array.from({ length: Math.round(yMax / step) + 1 }, (_, i) => i * step) as t (t)}
			<line x1={m.l} x2={m.l + iw} y1={y(t)} y2={y(t)} class="grid" />
			<text class="ax" x={m.l - 6} y={y(t) + 4} text-anchor="end">{f1(t)}</text>
		{/each}
		{#each rows as r, i (r.month)}
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<g onpointerenter={() => (hover = i)} onpointerleave={() => (hover = null)}>
				<rect x={m.l + bw * i} y={m.t} width={bw} height={ih} fill={hover === i ? 'var(--neutral-soft)' : 'transparent'} />
				<rect x={xc(i) - bw * 0.3} y={y(g.current[i] ?? 0)} width={bw * 0.6} height={Math.max(0, m.t + ih - y(g.current[i] ?? 0))} rx="3" fill="var(--sun)" />
				<text class="ax" x={xc(i)} y={H - 10} text-anchor="middle">{w < 480 ? MN[r.month - 1][0] : MN[r.month - 1]}</text>
			</g>
		{/each}
		<path d={line} fill="none" stroke="var(--cons)" stroke-width="2.4" stroke-linejoin="round" />
		{#each c.current as v, i (i)}
			<circle cx={xc(i)} cy={y(v)} r="3.6" fill="var(--surface)" stroke="var(--cons)" stroke-width="2" pointer-events="none" />
		{/each}
		<line x1={m.l} x2={m.l + iw} y1={m.t + ih} y2={m.t + ih} class="axis" />
		{#if hover !== null}
			{@const r = rows[hover]}
			{@const tx = Math.min(Math.max(xc(hover), m.l + 70), m.l + iw - 70)}
			<g class="tip" transform="translate({tx},{m.t + 4})" pointer-events="none">
				<rect x="-70" y="0" width="140" height="46" rx="8" />
				<text x="-60" y="18"><tspan class="sw sun">■</tspan> {f1(r.gen_kwh / 1000)} МВт·год</text>
				<text x="-60" y="36"><tspan class="sw cons">●</tspan> {f1(r.cons_kwh / 1000)} МВт·год</text>
			</g>
		{/if}
	</svg>
	<div class="lg" aria-hidden="true">
		<span><i class="b"></i>Генерація</span><span><i class="l"></i>Споживання</span><span class="u">МВт·год</span>
	</div>
</div>

<style>
	.dm {
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
	.ax {
		font-size: 11px;
		fill: var(--muted);
		font-variant-numeric: tabular-nums;
	}
	.tip rect {
		fill: var(--navy-deep, #0a1f38);
		opacity: 0.94;
	}
	.tip text {
		fill: #fff;
		font-size: 12px;
		font-weight: 600;
		font-variant-numeric: tabular-nums;
	}
	.sw.sun {
		fill: var(--sun);
	}
	.sw.cons {
		fill: #8fb6e6;
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
	.lg .u {
		margin-left: auto;
		color: var(--muted);
	}
	.b {
		width: 12px;
		height: 12px;
		border-radius: 3px;
		background: var(--sun);
	}
	.l {
		width: 18px;
		height: 2.4px;
		background: var(--cons);
		position: relative;
	}
	.l::after {
		content: '';
		position: absolute;
		left: 5px;
		top: -3.5px;
		width: 6px;
		height: 6px;
		border-radius: 50%;
		border: 2px solid var(--cons);
		background: var(--surface);
	}
</style>
