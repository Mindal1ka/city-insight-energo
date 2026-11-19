<!-- Фінанси: вкладено (розбивка), витрачено з мережі, заощаджено, окупність + кільце -->
<script lang="ts">
	import CountUp from '#lib/CountUp.svelte';
	import Icon from '#lib/Icon.svelte';
	import { num } from '#lib/format.ts';
	import ObjRing from './ObjRing.svelte';
	import type { ObjDetail } from './ObjApi.ts';

	let { d, showSes = true }: { d: ObjDetail; showSes?: boolean } = $props();

	const f = $derived(d.finance);
	const c = $derived(d.costs);
	const invested = $derived(f?.invested_uah ?? c?.total_uah ?? null);
	const parts = $derived(
		c
			? [
					{ k: 'Панелі', v: c.panels_uah, cls: 'p' },
					{ k: 'Інвертор', v: c.inverter_uah, cls: 'i' },
					{ k: 'Акумулятори', v: c.batteries_uah, cls: 'b' },
					{ k: 'Монтаж', v: c.install_uah, cls: 'm' }
				].filter((x) => (x.v ?? 0) > 0)
			: []
	);
	const sumParts = $derived(parts.reduce((s, x) => s + (x.v ?? 0), 0));
	const hasCosts = $derived(showSes && !!d.ses && !!invested);
	let shown = $state(false);
	$effect(() => {
		const id = requestAnimationFrame(() => (shown = true));
		return () => cancelAnimationFrame(id);
	});
</script>

<div class="fin">
	<!-- Мережа: завжди, якщо є споживання -->
	<div class="card grid-cost">
		<p class="h"><span class="ic grid" aria-hidden="true"><Icon name="plug" size={18} /></span>Витрачено на е/е з мережі</p>
		<div class="pair">
			<div><span class="v tnum"><CountUp value={f?.grid_cost_uah.month ?? null} /></span><small>грн / міс</small></div>
			<div><span class="v tnum"><CountUp value={f?.grid_cost_uah.year ?? null} /></span><small>грн / рік</small></div>
		</div>
		{#if f?.tariff_uah_kwh}<p class="foot tnum">{num(f.tariff_uah_kwh, 2)} грн/кВт·год</p>{/if}
	</div>

	{#if showSes && d.ses}
		<div class="card saved">
			<p class="h"><span class="ic good" aria-hidden="true"><Icon name="wallet" size={18} /></span>Заощаджено завдяки СЕС</p>
			<div class="pair three">
				<div><span class="v tnum"><CountUp value={f?.saved_uah.month ?? null} /></span><small>грн / міс</small></div>
				<div><span class="v tnum"><CountUp value={f?.saved_uah.year ?? null} /></span><small>грн / рік</small></div>
				<div><span class="v tnum strong"><CountUp value={f?.saved_uah.since_launch ?? null} /></span><small>з запуску</small></div>
			</div>
		</div>

		{#if hasCosts}
			<div class="card invest">
				<p class="h"><span class="ic sun" aria-hidden="true"><Icon name="panel" size={18} /></span>Вкладено в СЕС</p>
				<p class="big tnum"><CountUp value={invested} /> <small>грн</small></p>
				{#if parts.length}
					<div class="bar" role="img" aria-label={parts.map((p) => `${p.k} ${num(p.v)} грн`).join(', ')}>
						{#each parts as p, i (p.k)}
							<i class="seg {p.cls}" style="flex-basis: {shown ? ((p.v ?? 0) / sumParts) * 100 : 0}%; transition-delay: {i * 80}ms"></i>
						{/each}
					</div>
					<ul class="leg">
						{#each parts as p (p.k)}
							<li><i class="dot {p.cls}"></i>{p.k}<b class="tnum">{num(p.v)}</b></li>
						{/each}
					</ul>
				{/if}
			</div>
			<div class="card payback">
				<ObjRing pct={f?.payback_progress_pct ?? null} />
				<div>
					<p class="h">Окупність</p>
					<p class="big tnum"><CountUp value={f?.payback_years ?? null} decimals={1} /> <small>років</small></p>
				</div>
			</div>
		{/if}
	{/if}
</div>

<style>
	.fin {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.75rem;
	}
	.card {
		background: var(--surface);
		border: 1px solid var(--card-line);
		border-radius: var(--radius);
		padding: 1rem;
		min-width: 0;
		animation: fin-rise 0.5s var(--ease-out) both;
	}
	.card:nth-child(2) { animation-delay: 60ms; }
	.card:nth-child(3) { animation-delay: 120ms; }
	.card:nth-child(4) { animation-delay: 180ms; }
	.h {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin: 0 0 0.6rem;
		font-size: var(--fs-sm);
		color: var(--muted);
		font-weight: 600;
	}
	.ic {
		display: grid;
		place-items: center;
		width: 1.9rem;
		height: 1.9rem;
		border-radius: 8px;
	}
	.ic.grid { background: var(--accent-soft); color: var(--cons); }
	.ic.good { background: var(--surplus-soft); color: var(--surplus-ink); }
	.ic.sun { background: var(--sun-soft); color: var(--sun-ink); }
	.pair {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.5rem;
	}
	.pair.three {
		grid-template-columns: repeat(3, minmax(0, 1fr));
	}
	.pair > div {
		display: grid;
		min-width: 0;
	}
	.v {
		font-size: 1.35rem;
		font-weight: 700;
		color: var(--ink);
	}
	.v.strong {
		color: var(--surplus-ink);
	}
	small {
		font-size: var(--fs-xs);
		color: var(--muted);
		font-weight: 500;
	}
	.foot {
		margin: 0.5rem 0 0;
		font-size: var(--fs-xs);
		color: var(--muted);
	}
	.big {
		margin: 0;
		font-size: 1.9rem;
		font-weight: 800;
		color: var(--ink);
		line-height: 1.1;
	}
	.bar {
		display: flex;
		gap: 2px;
		height: 12px;
		margin: 0.8rem 0 0.6rem;
		border-radius: 999px;
		overflow: hidden;
		background: var(--line-soft);
	}
	.seg {
		flex: 0 0 0;
		transition: flex-basis 0.9s var(--ease-out);
	}
	.p { background: var(--sun); }
	.i { background: var(--cons); }
	.b { background: #6a55c9; }
	.m { background: var(--line-strong); }
	.leg {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.3rem 1rem;
		list-style: none;
		margin: 0;
		padding: 0;
		font-size: var(--fs-xs);
		color: var(--muted);
	}
	.leg li {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}
	.leg b {
		margin-left: auto;
		color: var(--ink);
	}
	.dot {
		width: 0.6rem;
		height: 0.6rem;
		border-radius: 3px;
	}
	.payback {
		display: flex;
		align-items: center;
		gap: 1.25rem;
	}
	.payback .h {
		margin-bottom: 0.2rem;
	}
	@keyframes fin-rise {
		from {
			opacity: 0;
			transform: translateY(10px);
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.card { animation: none; }
		.seg { transition: none; }
	}
	@media (max-width: 760px) {
		.fin {
			grid-template-columns: 1fr;
		}
		.v {
			font-size: 1.15rem;
		}
	}
</style>
