<!-- 12 місяців: згенеровано (сонце) vs спожито (синій) + лінія K (права вісь, смуга 0,8–1,2) -->
<script lang="ts">
	import { MONTHS, num } from '#lib/format.ts';
	import Icon from '#lib/Icon.svelte';
	import { kText } from '#lib/api-ses.ts';
	import { K_LOW, K_HIGH } from './ObjApi.ts';

	let { data, hasSes }: { data: { month: number; gen_kwh: number | null; cons_kwh: number | null; k: number | null }[]; hasSes: boolean } = $props();

	let cw = $state(640);
	const W = $derived(Math.max(300, Math.round(cw)));
	const H = $derived(cw < 500 ? 200 : 240);
	const P = $derived({ l: cw < 500 ? 34 : 44, r: hasSes ? 26 : 8, t: 12, b: 26 });
	const iw = $derived(W - P.l - P.r);
	const ih = $derived(H - 38);
	const max = $derived.by(() => {
		const m = Math.max(1, ...data.flatMap((d) => [d.gen_kwh ?? 0, d.cons_kwh ?? 0]));
		const pow = 10 ** Math.floor(Math.log10(m));
		return Math.ceil(m / pow) * pow;
	});
	const kMax = $derived(Math.max(1.6, ...data.map((d) => d.k ?? 0)) * 1.05);
	const bw = $derived(iw / 12);
	const x = (i: number) => P.l + i * bw;
	const y = (v: number) => P.t + ih - (v / max) * ih;
	const yk = (k: number) => P.t + ih - (k / kMax) * ih;
	const kPath = $derived(
		data
			.map((d, i) => (d.k === null ? null : `${x(i) + bw / 2},${yk(d.k)}`))
			.filter(Boolean)
			.map((p, i) => (i ? 'L' : 'M') + p)
			.join(' ')
	);
	const ticks = $derived([0, 0.5, 1].map((f) => f * max));
	let hover = $state<number | null>(null);
</script>

<div class="mc" bind:clientWidth={cw}>
	<ul class="legend" aria-hidden="true">
		{#if hasSes}<li><i class="sw gen"></i>Згенеровано</li>{/if}
		<li><i class="sw cons"></i>Спожито</li>
		{#if hasSes}<li><i class="sw k"></i>Покриття</li>{/if}
	</ul>
	<svg viewBox="0 0 {W} {H}" role="img" aria-label="Генерація та споживання по місяцях" onmouseleave={() => (hover = null)}>
		{#if hasSes}
			<rect class="band" x={P.l} width={iw} y={yk(K_HIGH)} height={yk(K_LOW) - yk(K_HIGH)} />
		{/if}
		{#each ticks as t (t)}
			<line class="grid" x1={P.l} x2={W - P.r} y1={y(t)} y2={y(t)} />
			<text class="ax" x={P.l - 6} y={y(t) + 4} text-anchor="end">{t >= 1000 ? num(t / 1000, t % 1000 ? 1 : 0) + 'k' : num(t)}</text>
		{/each}
		{#if hasSes}
			{#each [0, 1] as kk (kk)}
				<text class="ax k" x={W - P.r + 6} y={yk(kk) + 4}>{kk}</text>
			{/each}
		{/if}
		{#each data as d, i (d.month)}
			{@const gw = hasSes ? bw * 0.34 : bw * 0.56}
			<g class="m" class:on={hover === i} style="--d: {i * 40}ms" onmouseenter={() => (hover = i)} role="presentation">
				<rect class="hit" x={x(i)} y={P.t} width={bw} height={ih} />
				{#if hasSes && d.gen_kwh !== null}
					<rect class="bar gen" x={x(i) + bw * 0.14} y={y(d.gen_kwh)} width={gw} height={Math.max(0, P.t + ih - y(d.gen_kwh))} rx="3" />
				{/if}
				{#if d.cons_kwh !== null}
					<rect class="bar cons" x={x(i) + (hasSes ? bw * 0.52 : bw * 0.22)} y={y(d.cons_kwh)} width={gw} height={Math.max(0, P.t + ih - y(d.cons_kwh))} rx="3" />
				{/if}
				<text class="ax mo" x={x(i) + bw / 2} y={H - 8} text-anchor="middle">{MONTHS[d.month - 1]}</text>
			</g>
		{/each}
		{#if hasSes && kPath}
			<path class="kline" d={kPath} pathLength="1" />
			{#each data as d, i (d.month)}
				{#if d.k !== null}<circle class="kdot" cx={x(i) + bw / 2} cy={yk(d.k)} r={hover === i ? 4.5 : 3} />{/if}
			{/each}
		{/if}
	</svg>
	{#if hover !== null}
		{@const d = data[hover]}
		<p class="tip" style="left: {((x(hover) + bw / 2) / W) * 100}%">
			<b>{MONTHS[d.month - 1]}</b>
			{#if hasSes}<span class="g"><Icon name="sun" size={13} /><span class="visually-hidden">генерація</span> {num(d.gen_kwh)}</span>{/if}
			<span class="c"><Icon name="bolt" size={13} /><span class="visually-hidden">споживання</span> {num(d.cons_kwh)}</span>
			{#if hasSes}<span>покриття {kText(d.k)}</span>{/if}
		</p>
	{/if}
	<table class="visually-hidden">
		<caption>Помісячно, кВт·год</caption>
		<thead><tr><th>Місяць</th>{#if hasSes}<th>Згенеровано</th>{/if}<th>Спожито</th>{#if hasSes}<th>Покриття</th>{/if}</tr></thead>
		<tbody>
			{#each data as d (d.month)}
				<tr><td>{MONTHS[d.month - 1]}</td>{#if hasSes}<td>{num(d.gen_kwh)}</td>{/if}<td>{num(d.cons_kwh)}</td>{#if hasSes}<td>{kText(d.k)}</td>{/if}</tr>
			{/each}
		</tbody>
	</table>
</div>

<style>
	.mc {
		position: relative;
	}
	svg {
		display: block;
		width: 100%;
		height: auto;
		overflow: visible;
	}
	.legend {
		display: flex;
		gap: 1rem;
		list-style: none;
		margin: 0 0 0.4rem;
		padding: 0;
		font-size: var(--fs-xs);
		color: var(--muted);
	}
	.legend li {
		display: flex;
		align-items: center;
		gap: 0.35rem;
	}
	.sw {
		width: 0.8rem;
		height: 0.8rem;
		border-radius: var(--r-sm);
	}
	.sw.gen { background: var(--sun); }
	.sw.cons { background: var(--cons); }
	.sw.k { height: 3px; background: var(--surplus); }
	.band { fill: var(--surplus-soft); opacity: 0.7; }
	.grid { stroke: var(--line-soft); }
	.ax { font-size: 11px; fill: var(--muted); font-variant-numeric: tabular-nums; }
	.ax.k { fill: var(--surplus-ink); }
	.hit { fill: transparent; }
	.m.on .hit { fill: var(--neutral-soft); }
	.bar {
		transform-box: fill-box;
		transform-origin: bottom;
		/* Перший показ: стовпці ростуть від осі разом (без «драбинки»), 280 мс */
		animation: grow 280ms var(--ease-emph) both;
	}
	.gen { fill: var(--sun); }
	.cons { fill: var(--cons); opacity: 0.85; }
	.kline {
		fill: none;
		stroke: var(--surplus);
		stroke-width: 2.5;
		stroke-linejoin: round;
		stroke-dasharray: 1;
		animation: draw 300ms 120ms var(--ease-out) both;
	}
	.kdot { fill: var(--surface); stroke: var(--surplus); stroke-width: 2; transition: r var(--dur-fast); }
	.tip {
		position: absolute;
		top: 1.4rem;
		transform: translateX(-50%);
		margin: 0;
		display: flex;
		gap: 0.5rem;
		padding: 0.3rem 0.55rem;
		background: var(--ink);
		color: #fff;
		border-radius: var(--r-btn);
		font-size: var(--fs-xs);
		white-space: nowrap;
		pointer-events: none;
		font-variant-numeric: tabular-nums;
	}
	.tip .g { color: #ffd27a; }
	.tip .c { color: #b9d4f5; }
	@keyframes grow {
		from { transform: scaleY(0); }
	}
	@keyframes draw {
		from { stroke-dashoffset: 1; }
		to { stroke-dashoffset: 0; }
	}
	@media (prefers-reduced-motion: reduce) {
		.bar, .kline { animation: none; }
	}
</style>
