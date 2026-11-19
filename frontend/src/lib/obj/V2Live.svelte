<!-- Стан СЕС зараз (МОК · API інвертора) -->
<script lang="ts">
	import type { Live } from '#lib/api-v2.ts';
	import { num, moment } from '#lib/format.ts';
	import Icon from '#lib/Icon.svelte';

	let { l }: { l: Live } = $props();
	const online = $derived(l.status === 'online');
	const t = $derived(moment(l.updated_at));
	const charging = $derived((l.battery_kw ?? 0) > 0);
</script>

<div class="panel live">
	<div class="top">
		<span class="st" class:on={online}><i class="dot"></i>{online ? 'online' : 'offline'}</span>
		<span class="mock">МОК · API інвертора</span>
		{#if t}<span class="up tnum"><Icon name="clock" size={14} /> {t.time}</span>{/if}
	</div>
	<div class="grid tnum">
		<div class="c gen"><Icon name="sun" size={18} /><b>{num(l.gen_kw, 1)}</b><small>кВт</small></div>
		<div class="c load"><Icon name="plug" size={18} /><b>{num(l.load_kw, 1)}</b><small>кВт</small></div>
		<div class="c" class:buy={l.grid_kw > 0} class:give={l.grid_kw < 0}>
			<Icon name="grid" size={18} /><b>{num(Math.abs(l.grid_kw), 1)}</b><small>кВт</small>
			<em>{l.grid_kw > 0 ? '↓ купуємо' : l.grid_kw < 0 ? '↑ віддаємо' : '—'}</em>
		</div>
		{#if l.soc_pct !== null}
			<div class="c bat">
				<Icon name="battery" size={18} /><b>{num(l.soc_pct)}</b><small>%</small>
				{#if l.battery_kw !== null && l.battery_kw !== 0}<em>{charging ? '↑ заряд' : '↓ розряд'} {num(Math.abs(l.battery_kw), 1)} кВт</em>{/if}
			</div>
		{/if}
	</div>
	<p class="today tnum">
		<span><Icon name="sun" size={15} /> {num(l.today_gen_kwh)} <small>кВт·год</small></span>
		<span><Icon name="plug" size={15} /> {num(l.today_load_kwh)} <small>кВт·год</small></span>
	</p>
</div>

<style>
	.live {
		display: grid;
		gap: 0.8rem;
		padding: 1rem;
	}
	.top {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.5rem 0.9rem;
	}
	.st {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		font-weight: 700;
		color: var(--bad);
	}
	.st.on {
		color: var(--ok);
	}
	.dot {
		width: 0.7rem;
		height: 0.7rem;
		border-radius: 50%;
		background: currentColor;
	}
	.st.on .dot {
		box-shadow: 0 0 0 4px var(--ok-soft);
	}
	.mock {
		padding: 0.1rem 0.55rem;
		border-radius: 999px;
		border: 1px dashed #d08a1c;
		background: var(--sun-soft);
		color: var(--sun-ink);
		font-size: var(--fs-xs);
		font-weight: 700;
	}
	.up {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		margin-left: auto;
		color: var(--muted);
		font-size: var(--fs-sm);
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
		gap: 0.5rem;
	}
	.c {
		display: flex;
		align-items: baseline;
		flex-wrap: wrap;
		gap: 0.3rem;
		padding: 0.6rem 0.75rem;
		border-radius: 10px;
		background: var(--neutral-soft);
	}
	.c :global(svg) {
		align-self: center;
	}
	.c b {
		font-size: var(--fs-xl);
		color: var(--ink);
	}
	small {
		color: var(--muted);
	}
	.c em {
		flex-basis: 100%;
		font-style: normal;
		font-size: var(--fs-xs);
		font-weight: 600;
	}
	.gen { background: var(--sun-soft); color: var(--sun-ink); }
	.load { background: var(--accent-soft); color: var(--cons); }
	.buy { background: var(--warn-soft); color: var(--warn); }
	.give { background: var(--ok-soft); color: var(--ok); }
	.bat { background: var(--surplus-soft); color: var(--surplus-ink); }
	.today {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 1.2rem;
		margin: 0;
		color: var(--muted);
	}
	.today span {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
</style>
