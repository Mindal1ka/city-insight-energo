<!-- Розподіл енергії сьогодні: пік, доступно vs потреба, баланс, 24-годинний графік -->
<script lang="ts">
	import type { Distribution } from '#lib/api-v2.ts';
	import { num, signed, hh } from '#lib/format.ts';
	import Icon from '#lib/Icon.svelte';

	let { d }: { d: Distribution } = $props();

	const W = 480;
	const H = 120;
	const bw = W / 24;
	const hours = $derived(d.hourly);
	const max = $derived(Math.max(0.1, ...hours.flatMap((h) => [h.gen_kwh, h.cons_kwh])));
	const yy = (v: number) => H - (v / max) * (H - 6);
</script>

<div class="panel dist">
	<div class="big" class:good={d.enough} class:bad={!d.enough}>
		<span class="sign">{d.enough ? '+' : '−'}</span>
		<b class="tnum">{num(Math.abs(d.balance_kwh), 1)}</b><small>кВт·год</small>
		<Icon name={d.enough ? 'check' : 'alert'} size={22} />
	</div>

	<div class="grid tnum">
		<div class="cell"><span class="l">Пік</span><b>{num(d.peak_kw, 1)} <small>кВт</small></b><em>@ {hh(d.peak_hour)}</em></div>
		<div class="cell"><span class="l">Доступно</span><b>{num(d.available_kwh, 1)} <small>кВт·год</small></b>
			<em>
				{#if d.battery_usable_kwh !== null}<Icon name="battery" size={13} /> {num(d.battery_usable_kwh, 1)} + {/if}<Icon name="sun" size={13} /> {num(d.sun_left_kwh, 1)}
			</em>
		</div>
		<div class="cell"><span class="l">Потреба</span><b>{num(d.demand_left_kwh, 1)} <small>кВт·год</small></b></div>
		<div class="cell"><span class="l">Резерв</span><b>{num(d.reserve_kwh, 1)} <small>кВт·год</small></b></div>
	</div>

	{#if hours.length}
		<ul class="legend" aria-hidden="true">
			<li><i class="sw g"></i>Генерація</li>
			<li><i class="sw c"></i>Споживання</li>
		</ul>
		<svg viewBox="0 0 {W} {H + 16}" role="img" aria-label="Генерація та споживання по годинах">
			{#each hours as h (h.hour)}
				{@const x = h.hour * bw}
				{#if h.hour === d.hour}<rect class="now" x={x} y="0" width={bw} height={H} />{/if}
				<rect class="g" x={x + bw * 0.1} y={yy(h.gen_kwh)} width={bw * 0.38} height={H - yy(h.gen_kwh)} rx="1.5" />
				<rect class="c" x={x + bw * 0.5} y={yy(h.cons_kwh)} width={bw * 0.38} height={H - yy(h.cons_kwh)} rx="1.5" />
				{#if h.hour % 4 === 0}<text x={x + bw / 2} y={H + 12} text-anchor="middle">{h.hour}</text>{/if}
			{/each}
			<line class="base" x1="0" x2={W} y1={H} y2={H} />
		</svg>
		<p class="note tnum"><i class="sw n"></i> {hh(d.hour)}</p>
	{/if}
</div>

<style>
	.dist {
		display: grid;
		gap: 0.8rem;
		padding: 1rem;
	}
	.big {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.6rem 0.9rem;
		border-radius: 12px;
	}
	.big.good { background: var(--ok-soft); color: var(--ok); }
	.big.bad { background: var(--bad-soft); color: var(--bad); }
	.sign {
		font-size: 2.4rem;
		font-weight: 800;
		line-height: 1;
	}
	.big b {
		font-size: 2.2rem;
		line-height: 1;
	}
	.big :global(svg) {
		margin-left: auto;
	}
	small {
		color: var(--muted);
		font-weight: 400;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
		gap: 0.5rem;
	}
	.cell {
		display: grid;
		gap: 0.15rem;
		padding: 0.55rem 0.7rem;
		border-radius: 10px;
		background: var(--neutral-soft);
	}
	.cell b {
		font-size: var(--fs-lg, 1.1rem);
		color: var(--ink);
	}
	.cell em {
		font-style: normal;
		font-size: var(--fs-xs);
		color: var(--muted);
		display: inline-flex;
		align-items: center;
		gap: 0.2rem;
	}
	.l {
		font-size: var(--fs-xs);
		color: var(--muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.legend {
		display: flex;
		gap: 1rem;
		list-style: none;
		margin: 0;
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
		display: inline-block;
		width: 0.8rem;
		height: 0.8rem;
		border-radius: 3px;
	}
	.sw.g { background: var(--sun); }
	.sw.c { background: var(--cons); }
	.sw.n { background: var(--neutral-soft); border: 1px solid var(--line); }
	svg {
		display: block;
		width: 100%;
		height: auto;
	}
	svg .g { fill: var(--sun); }
	svg .c { fill: var(--cons); opacity: 0.85; }
	svg .now { fill: var(--neutral-soft); }
	svg .base { stroke: var(--line); }
	svg text { font-size: 10px; fill: var(--muted); }
	.note {
		margin: 0;
		display: flex;
		align-items: center;
		gap: 0.35rem;
		font-size: var(--fs-xs);
		color: var(--muted);
	}
</style>
