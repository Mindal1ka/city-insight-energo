<!-- Зараз: компактна смуга стану СЕС (online, генерація, навантаження, мережа ±, заряд) -->
<script lang="ts">
	import type { Live } from '#lib/api-v2.ts';
	import { num, moment } from '#lib/format.ts';
	import Icon from '#lib/Icon.svelte';

	let { l }: { l: Live } = $props();
	const online = $derived(l.status === 'online');
	const t = $derived(moment(l.updated_at));
	const charging = $derived((l.battery_kw ?? 0) > 0);
</script>

<div class="strip tnum" aria-label="Стан станції зараз">
	<span class="st" class:on={online}><i class="dot"></i>{online ? 'online' : 'offline'}{#if t}<small>{t.time}</small>{/if}</span>
	<span class="c gen" title="Генерація"><Icon name="sun" size={16} /><b>{num(l.gen_kw, 1)}</b><small>кВт</small></span>
	<span class="c load" title="Навантаження"><Icon name="plug" size={16} /><b>{num(l.load_kw, 1)}</b><small>кВт</small></span>
	<span class="c" class:buy={l.grid_kw > 0} class:give={l.grid_kw < 0} title="Мережа">
		<Icon name="grid" size={16} /><b>{l.grid_kw > 0 ? '+' : l.grid_kw < 0 ? '−' : ''}{num(Math.abs(l.grid_kw), 1)}</b><small>кВт {l.grid_kw > 0 ? 'купуємо' : l.grid_kw < 0 ? 'віддаємо' : ''}</small>
	</span>
	{#if l.soc_pct !== null}
		<span class="c bat" title="Заряд акумулятора">
			<Icon name="battery" size={16} /><b>{num(l.soc_pct)}</b><small>%{#if l.battery_kw !== null && l.battery_kw !== 0} {charging ? '↑' : '↓'} {num(Math.abs(l.battery_kw), 1)} кВт{/if}</small>
		</span>
	{/if}
</div>

<style>
	.strip {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
	}
	.st {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		margin-right: 0.3rem;
		font-weight: 700;
		color: var(--bad);
	}
	.st.on {
		color: var(--ok);
	}
	.dot {
		width: 0.65rem;
		height: 0.65rem;
		border-radius: 50%;
		background: currentColor;
	}
	.st.on .dot {
		box-shadow: 0 0 0 3px var(--ok-soft);
	}
	.c {
		display: inline-flex;
		align-items: baseline;
		gap: 0.3rem;
		padding: 0.4rem 0.7rem;
		border-radius: var(--r-card);
		background: var(--neutral-soft);
	}
	.c :global(svg) {
		align-self: center;
	}
	.c b {
		font-size: var(--fs-lg, 1.1rem);
		color: var(--ink);
	}
	small {
		color: var(--muted);
	}
	.gen { background: var(--sun-soft); color: var(--sun-ink); }
	.load { background: var(--accent-soft); color: var(--cons); }
	.buy { background: var(--warn-soft); color: var(--warn); }
	.give { background: var(--ok-soft); color: var(--ok); }
	.bat { background: var(--surplus-soft); color: var(--surplus-ink); }
	@media (max-width: 640px) {
		.st {
			flex-basis: 100%;
		}
	}
</style>
