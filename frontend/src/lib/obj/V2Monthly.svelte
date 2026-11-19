<!-- Споживання по місяцях (12 стовпчиків) + середнє за місяць -->
<script lang="ts">
	import { MONTHS, num } from '#lib/format.ts';

	let { data }: { data: number[] } = $props();
	const max = $derived(Math.max(1, ...data));
	const avg = $derived(data.length ? data.reduce((a, b) => a + b, 0) / data.length : 0);
	const curMonth = new Date().getMonth();
</script>

<div class="panel mo">
	<p class="avg tnum"><span class="l">сер./міс.</span> <b>{num(avg)}</b> <small>кВт·год</small></p>
	<div class="bars" role="img" aria-label="Споживання по місяцях, кВт·год">
		{#each data as v, i (i)}
			<div class="col" class:cur={i === curMonth} title="{MONTHS[i]}: {num(v)} кВт·год">
				<span class="val tnum">{v >= 1000 ? num(v / 1000, 1) + 'k' : num(v)}</span>
				<span class="bar" style="height: {Math.max(2, (v / max) * 100)}%"></span>
				<span class="m">{MONTHS[i]}</span>
			</div>
		{/each}
	</div>
</div>

<style>
	.mo {
		padding: 1rem;
	}
	.avg {
		margin: 0 0 0.6rem;
		display: flex;
		align-items: baseline;
		gap: 0.4rem;
		color: var(--muted);
	}
	.avg b {
		font-size: var(--fs-xl);
		color: var(--ink);
	}
	.l {
		font-size: var(--fs-xs);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.bars {
		display: grid;
		grid-template-columns: repeat(12, 1fr);
		gap: 0.25rem;
		height: 150px;
	}
	.col {
		display: grid;
		grid-template-rows: auto 1fr auto;
		justify-items: center;
		align-items: end;
		min-width: 0;
		gap: 2px;
	}
	.bar {
		width: 70%;
		background: var(--cons);
		opacity: 0.8;
		border-radius: 3px 3px 0 0;
	}
	.col.cur .bar {
		background: var(--sun-strong);
		opacity: 1;
	}
	.val {
		font-size: 10px;
		color: var(--muted);
	}
	.m {
		font-size: 11px;
		color: var(--muted);
	}
	@media (max-width: 640px) {
		.val {
			display: none;
		}
	}
</style>
