<!-- Одна рядкова рекомендація за сайзингом: достатньо / доставити / надлишок -->
<script lang="ts">
	import type { Sizing } from '#lib/api-v2.ts';
	import { num } from '#lib/format.ts';
	import Icon from '#lib/Icon.svelte';

	let { s, id, hasStation = false, surplus = false }: { s: Sizing; id: string | number; hasStation?: boolean; surplus?: boolean } = $props();

	const addBat = $derived(s.add_battery_kwh ?? 0);
	const needMore = $derived(s.need && (s.add_kw > 0 || addBat > 0));
</script>

{#if needMore}
	<div class="reco warn">
		<p>
			<span class="ic" aria-hidden="true">↓</span>
			Доставити
			{#if s.add_kw > 0}<b class="tnum">+{num(s.add_kw, 1)} кВт</b> панелей{/if}
			{#if s.add_kw > 0 && addBat > 0} і {/if}
			{#if addBat > 0}<b class="tnum">+{num(addBat, 1)} кВт·год</b> акумулятора{/if}
			{#if s.payback_years != null}<span class="pb tnum">· окупність {num(s.payback_years, 1)} р.</span>{/if}
		</p>
		<a class="btn btn-sun btn-sm" href="/appeals?building={id}&type=expand&kw={s.add_kw}"><Icon name="sun" size={16} /> Подати звернення</a>
	</div>
{:else if surplus}
	<div class="reco good">
		<p><span class="ic" aria-hidden="true">↑</span> Надлишок — можна поділитися</p>
		<a class="btn btn-secondary btn-sm" href="/appeals?building={id}&type=surplus"><Icon name="grid" size={16} /> Передати надлишок</a>
	</div>
{:else if hasStation}
	<div class="reco good">
		<p><span class="ic" aria-hidden="true"><Icon name="check" size={14} stroke={2.6} /></span> Станції достатньо</p>
	</div>
{/if}

<style>
	.reco {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem 1rem;
		padding: 0.6rem 0.9rem;
		border-radius: var(--r-card);
	}
	.reco p {
		margin: 0;
		font-weight: 600;
		flex: 1 1 260px;
	}
	.reco.good {
		background: var(--ok-soft);
		color: var(--ok);
	}
	.reco.warn {
		background: var(--sun-soft);
		color: var(--sun-ink);
	}
	.ic {
		font-weight: 800;
		margin-right: 0.2rem;
	}
	.pb {
		font-weight: 500;
	}
</style>
