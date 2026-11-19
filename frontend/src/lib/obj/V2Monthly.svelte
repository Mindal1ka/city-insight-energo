<!-- Місяць за місяцем: споживання vs генерація (частина через акумулятор) + компактна таблиця -->
<script lang="ts">
	import type { MonthRow } from '#lib/api-v2.ts';
	import { MONTHS, num } from '#lib/format.ts';
	import Disclosure from '#lib/Disclosure.svelte';

	let {
		months,
		capacity = null,
		months2026 = null
	}: { months: MonthRow[]; capacity?: number | null; months2026?: { month: number; kwh: number; kind: string }[] | null } = $props();

	let year = $state<'2025' | '2026'>('2025');
	const is26 = $derived(year === '2026' && !!months2026?.length);
	const m26 = $derived(Array.from({ length: 12 }, (_, i) => months2026?.find((x) => x.month === i + 1) ?? null));
	const consOf = (r: MonthRow, i: number) => (is26 ? (m26[i]?.kwh ?? null) : r.cons_kwh);

	const rows = $derived(months ?? []);
	const hasGen = $derived(!is26 && rows.some((r) => r.gen_kwh != null));
	const max = $derived(Math.max(1, ...rows.map((r, i) => Math.max(consOf(r, i) ?? 0, is26 ? 0 : (r.gen_kwh ?? 0)))));
	type NumKey = 'cons_kwh' | 'gen_kwh' | 'surplus_kwh' | 'grid_kwh';
	const sum = (k: NumKey) => {
		const v = rows.map((r) => r[k]);
		return v.some((x) => x != null) ? v.reduce((a: number, x) => a + (x ?? 0), 0) : null;
	};
	const totals = $derived(
		[
			{ l: 'Σ спожито', v: sum('cons_kwh'), cls: 'cons' },
			{ l: 'Σ згенеровано', v: sum('gen_kwh'), cls: 'gen' },
			{ l: 'Не використано', v: sum('surplus_kwh'), cls: 'sur' },
			{ l: 'З мережі', v: sum('grid_kwh'), cls: 'grid' }
		].filter((t) => t.v != null)
	);
	const curMonth = new Date().getMonth();

	type Def = { key: keyof MonthRow; label: string; cls: string };
	const defs: Def[] = [
		{ key: 'cons_kwh', label: 'Спожито', cls: 'c-cons' },
		{ key: 'gen_kwh', label: 'Згенеровано', cls: 'c-gen' },
		{ key: 'battery_kwh', label: 'Через акумулятор', cls: 'c-bat' },
		{ key: 'surplus_kwh', label: 'Не використано', cls: 'c-sur' },
		{ key: 'grid_kwh', label: 'З мережі', cls: 'c-grid' },
		{ key: 'saved_uah', label: 'Заощаджено, грн', cls: 'c-sav' }
	];
	const shown = $derived(defs.filter((d) => rows.some((r) => r[d.key] != null)));
	const h = (v: number | null | undefined) => `${Math.max(v ? 2 : 0, ((v ?? 0) / max) * 100)}%`;
</script>

<div class="mo">
	{#if months2026?.length}
		<div class="yr" role="radiogroup" aria-label="Рік споживання">
			{#each ['2025', '2026'] as y (y)}
				<button type="button" role="radio" aria-checked={year === y} class:on={year === y} onclick={() => (year = y as '2025' | '2026')}>{y}</button>
			{/each}
			{#if is26}<span class="yn">UMUNI · до 11.11 факт, далі прогноз</span>{/if}
		</div>
	{/if}
	<div class="head tnum">
		{#if is26}
			<p class="cons"><span class="l">≈ за 2026 рік</span> <b>{num(m26.reduce((a, x) => a + (x?.kwh ?? 0), 0))}</b> <small>кВт·год</small></p>
		{:else}
		{#each totals as t (t.l)}
			<p class={t.cls}><span class="l">{t.l}, за рік</span> <b>{num(t.v)}</b> <small>кВт·год</small></p>
		{/each}
		{/if}
	</div>

	<div class="bars" role="img" aria-label="Споживання та генерація по місяцях, кВт·год">
		{#each rows as r, i (r.month)}
			{@const bat = Math.min(r.battery_kwh ?? 0, r.gen_kwh ?? 0)}
			<div class="col" class:cur={i === curMonth} title="{MONTHS[i]}: спожито {num(consOf(r, i))}{is26 && m26[i] ? ` (${m26[i]?.kind})` : ''}{!is26 && r.gen_kwh != null ? `, згенеровано ${num(r.gen_kwh)}` : ''} кВт·год">
				<div class="pair">
					<span class="b cons" class:fc={is26 && m26[i]?.kind === 'прогноз'} style="height: {h(consOf(r, i))}"></span>
					{#if hasGen}
						<span class="b gen" style="height: {h(r.gen_kwh)}">
							{#if bat > 0}<span class="bt" style="height: {(bat / Math.max(1, r.gen_kwh ?? 1)) * 100}%"></span>{/if}
						</span>
					{/if}
				</div>
				<span class="m">{MONTHS[i]}</span>
			</div>
		{/each}
	</div>
	<p class="legend">
		<span><i class="sw cons"></i>Спожито</span>
		{#if is26}<span><i class="sw cons fc"></i>Прогноз</span>{/if}
		{#if hasGen}<span><i class="sw gen"></i>Згенеровано</span><span><i class="sw bt"></i>Через акумулятор</span>{/if}
	</p>

	{#if !is26}
	<Disclosure summary="Детально по місяцях">
	<div class="scroll-x">
		<table class="tbl tnum">
			<thead>
				<tr>
					<th></th>
					{#each rows as r, i (r.month)}<th class:cur={i === curMonth}>{MONTHS[i]}</th>{/each}
				</tr>
			</thead>
			<tbody>
				{#each shown as d (d.key)}
					<tr class={d.cls}>
						<th scope="row">{d.label}</th>
						{#each rows as r, i (r.month)}
							{@const v = r[d.key] as number | null}
							<td class:cur={i === curMonth}>{v == null ? '—' : num(v)}</td>
						{/each}
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	</Disclosure>
	{/if}
</div>

<style>
	.mo {
		display: grid;
		gap: 0.8rem;
		min-width: 0;
	}
	.head {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem 1.5rem;
	}
	.head p {
		margin: 0;
		display: grid;
		gap: 0.1rem;
		color: var(--muted);
	}
	.head b {
		font-size: var(--fs-xl);
		color: var(--ink);
		display: inline;
	}
	.head .gen b {
		color: var(--sun-ink);
	}
	.head .sur b {
		color: var(--surplus-ink);
	}
	.head .grid b {
		color: var(--cons);
	}
	.l {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		font-size: var(--fs-xs);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	small {
		color: var(--muted);
		font-weight: 400;
	}
	.bars {
		display: grid;
		grid-template-columns: repeat(12, 1fr);
		gap: 0.25rem;
		height: 160px;
	}
	.col {
		display: grid;
		grid-template-rows: 1fr auto;
		min-width: 0;
		gap: 2px;
	}
	.pair {
		display: flex;
		align-items: flex-end;
		justify-content: center;
		gap: 2px;
		min-height: 0;
	}
	.b {
		flex: 1 1 0;
		max-width: 14px;
		border-radius: 3px 3px 0 0;
		display: flex;
		flex-direction: column;
		justify-content: flex-end;
		overflow: hidden;
	}
	.b.cons,
	.sw.cons {
		background: var(--cons);
		opacity: 0.85;
	}
	.b.cons.fc,
	.sw.cons.fc {
		opacity: 0.5;
		background: repeating-linear-gradient(45deg, var(--cons) 0 3px, transparent 3px 6px);
		outline: 1px dashed var(--cons);
		outline-offset: -1px;
	}
	.yr {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.yr button {
		border: 1px solid var(--line);
		background: transparent;
		border-radius: 999px;
		padding: 0.1rem 0.7rem;
		font: inherit;
		font-size: var(--fs-xs);
		font-weight: 600;
		color: var(--muted);
		cursor: pointer;
	}
	.yr button.on {
		background: var(--surface);
		color: var(--ink);
		box-shadow: var(--shadow);
	}
	.yn {
		font-size: var(--fs-xs);
		color: var(--muted);
	}
	.b.gen,
	.sw.gen {
		background: var(--sun-strong);
	}
	.bt,
	.sw.bt {
		display: block;
		background: var(--bat, #6d4fc2);
	}
	.m {
		text-align: center;
		font-size: 11px;
		color: var(--muted);
	}
	.col.cur .m {
		color: var(--ink);
		font-weight: 700;
	}
	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem 1rem;
		margin: 0;
		font-size: var(--fs-xs);
		color: var(--muted);
	}
	.legend span {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
	}
	.sw {
		display: inline-block;
		width: 0.7rem;
		height: 0.7rem;
		border-radius: 3px;
	}
	.scroll-x {
		overflow-x: auto;
		-webkit-overflow-scrolling: touch;
	}
	.tbl {
		border-collapse: collapse;
		width: 100%;
		font-size: var(--fs-xs);
	}
	.tbl th,
	.tbl td {
		padding: 0.3rem 0.4rem;
		text-align: right;
		white-space: nowrap;
		border-top: 1px solid var(--line-soft, var(--line));
	}
	.tbl thead th {
		border-top: 0;
		color: var(--muted);
		font-weight: 600;
	}
	.tbl tbody th {
		position: sticky;
		left: 0;
		z-index: 1;
		text-align: left;
		background: var(--surface);
		font-weight: 600;
		color: var(--ink);
		padding-right: 0.8rem;
	}
	.tbl .cur {
		background: var(--sun-soft);
	}
	.c-gen td {
		color: var(--sun-ink);
	}
	.c-bat td {
		color: var(--bat, #6d4fc2);
	}
	.c-sav td {
		color: var(--ok);
		font-weight: 600;
	}
	@media (max-width: 640px) {
		.head {
			display: grid;
			grid-template-columns: 1fr 1fr;
		}
		.bars {
			height: 120px;
			gap: 0.1rem;
		}
		.m {
			font-size: 9px;
		}
		.tbl {
			min-width: 640px;
		}
	}
</style>
