<!-- Сьогодні: баланс (доступно vs потрібно) + невеликий 24-годинний графік -->
<script lang="ts">
	import type { Distribution } from '#lib/api-v2.ts';
	import { num, hh } from '#lib/format.ts';
	import Icon from '#lib/Icon.svelte';

	let { d }: { d: Distribution } = $props();

	const W = 720;
	const H = 100;
	const bw = W / 24;
	const hours = $derived(d.hourly);
	const max = $derived(Math.max(0.1, ...hours.flatMap((h) => [h.gen_kwh, h.cons_kwh])));
	const yy = (v: number) => H - (v / max) * (H - 6);
</script>

<div class="dist">
	<div class="top">
		<div class="big" class:good={d.enough} class:bad={!d.enough}>
			<Icon name={d.enough ? 'check' : 'alert'} size={20} />
			<span class="sign">{d.enough ? '+' : '−'}</span>
			<b class="tnum">{num(Math.abs(d.balance_kwh), 1)}</b><small>кВт·год</small>
		</div>
		<p class="cmp tnum">
			<span>Доступно <b>{num(d.available_kwh, 1)}</b>
				<small>
					{#if d.battery_usable_kwh !== null}(<Icon name="battery" size={12} /> {num(d.battery_usable_kwh, 1)} + <Icon name="sun" size={12} /> {num(d.sun_left_kwh, 1)}){:else}(<Icon name="sun" size={12} /> {num(d.sun_left_kwh, 1)}){/if}
				</small>
			</span>
			<span>Потрібно <b>{num(d.demand_left_kwh, 1)}</b> <small>кВт·год</small></span>
		</p>
	</div>

	{#if hours.length}
		<svg viewBox="0 0 {W} {H + 16}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Генерація (жовтий) та споживання (синій) по годинах">
			{#each hours as h (h.hour)}
				{@const x = h.hour * bw}
				{#if h.hour === d.hour}<rect class="now" x={x} y="0" width={bw} height={H} />{/if}
				<rect class="g" x={x + bw * 0.1} y={yy(h.gen_kwh)} width={bw * 0.38} height={H - yy(h.gen_kwh)} rx="1.5" />
				<rect class="c" x={x + bw * 0.5} y={yy(h.cons_kwh)} width={bw * 0.38} height={H - yy(h.cons_kwh)} rx="1.5" />
				{#if h.hour % 3 === 0}<text x={x + bw / 2} y={H + 12} text-anchor="middle">{h.hour}</text>{/if}
			{/each}
			<line class="base" x1="0" x2={W} y1={H} y2={H} />
		</svg>
		<p class="note tnum"><i class="sw g"></i>генерація <i class="sw c"></i>споживання · зараз {hh(d.hour)}</p>
	{/if}
</div>

<style>
	.dist {
		display: grid;
		gap: 0.6rem;
		min-width: 0;
	}
	.top {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.6rem 1.25rem;
	}
	.big {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		padding: 0.4rem 0.8rem;
		border-radius: var(--r-card);
	}
	.big.good { background: var(--ok-soft); color: var(--ok); }
	.big.bad { background: var(--bad-soft); color: var(--bad); }
	.sign {
		font-size: 1.6rem;
		font-weight: 800;
		line-height: 1;
	}
	.big b {
		font-size: 1.6rem;
		line-height: 1;
	}
	small {
		color: var(--muted);
		font-weight: 400;
	}
	.cmp {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem 1.25rem;
		margin: 0;
		color: var(--muted);
	}
	.cmp b {
		color: var(--ink);
		font-size: var(--fs-lg, 1.1rem);
	}
	.cmp small :global(svg) {
		vertical-align: -2px;
	}
	svg {
		display: block;
		width: 100%;
		height: auto;
		max-height: 140px;
	}
	svg .g { fill: var(--sun); }
	svg .c { fill: var(--cons); opacity: 0.85; }
	svg .now { fill: var(--neutral-soft); }
	svg .base { stroke: var(--line); }
	svg text { font-size: 10px; fill: var(--muted); }
	.note {
		margin: 0;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.35rem;
		font-size: var(--fs-xs);
		color: var(--muted);
	}
	.sw {
		display: inline-block;
		width: 0.7rem;
		height: 0.7rem;
		border-radius: var(--r-sm);
		margin-left: 0.4rem;
	}
	.sw:first-child {
		margin-left: 0;
	}
	.sw.g { background: var(--sun); }
	.sw.c { background: var(--cons); }
</style>
