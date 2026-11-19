<!-- Скільки доставити: +X кВт, capex, окупність, кнопки звернень -->
<script lang="ts">
	import type { Sizing } from '#lib/api-v2.ts';
	import { uah } from '#lib/api-ses.ts';
	import { num } from '#lib/format.ts';
	import Icon from '#lib/Icon.svelte';

	let { s, id, hasStation = false, surplus = false }: { s: Sizing; id: string | number; hasStation?: boolean; surplus?: boolean } = $props();
</script>

<div class="panel siz">
	{#if s.need}
		<div class="big tnum"><span class="p">+</span><b>{num(s.add_kw, 1)}</b><small>кВт</small></div>
		<div class="grid tnum">
			{#if s.capex_uah !== undefined}<div class="cell"><span class="l">Вартість</span><b>{uah(s.capex_uah)}</b></div>{/if}
			{#if s.saved_uah_year !== undefined}<div class="cell good"><span class="l">Економія/рік</span><b>{uah(s.saved_uah_year)}</b></div>{/if}
			{#if s.payback_years != null}<div class="cell"><span class="l">Окупність</span><b>{num(s.payback_years, 1)} <small>р.</small></b></div>{/if}
			{#if s.limited_by}<div class="cell"><span class="l">Обмеження</span><b>{s.limited_by}</b></div>{/if}
			{#if s.roof_max_kw !== undefined}<div class="cell"><span class="l">Дах макс.</span><b>{num(s.roof_max_kw, 1)} <small>кВт</small></b></div>{/if}
		</div>
		<a class="btn btn-sun btn-sm" href="/appeals?building={id}&type=expand&kw={s.add_kw}"><Icon name="sun" size={16} /> Подати звернення</a>
	{:else if hasStation}
		<p class="ok"><Icon name="check" size={20} stroke={2.4} /> Потужності достатньо</p>
	{/if}
	{#if surplus}
		<a class="btn btn-secondary btn-sm" href="/appeals?building={id}&type=surplus"><Icon name="grid" size={16} /> Передати надлишок</a>
	{/if}
</div>

<style>
	.siz {
		display: grid;
		gap: 0.8rem;
		padding: 1rem;
		justify-items: start;
	}
	.big {
		display: flex;
		align-items: baseline;
		gap: 0.3rem;
		color: var(--sun-ink);
	}
	.big .p,
	.big b {
		font-size: 2.6rem;
		font-weight: 800;
		line-height: 1;
	}
	small {
		color: var(--muted);
		font-weight: 400;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
		gap: 0.5rem;
		width: 100%;
	}
	.cell {
		display: grid;
		gap: 0.15rem;
		padding: 0.55rem 0.7rem;
		border-radius: 10px;
		background: var(--neutral-soft);
	}
	.cell.good {
		background: var(--ok-soft);
		color: var(--ok);
	}
	.cell b {
		font-size: var(--fs-lg, 1.1rem);
	}
	.l {
		font-size: var(--fs-xs);
		color: var(--muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.cell.good .l {
		color: inherit;
	}
	.ok {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin: 0;
		font-weight: 700;
		color: var(--ok);
	}
</style>
