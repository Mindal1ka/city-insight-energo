<!-- Місяць за місяцем: споживання vs генерація (частина через акумулятор) + компактна таблиця -->
<script lang="ts">
	import type { MonthRow } from '#lib/api-v2.ts';
	import { MONTHS, num } from '#lib/format.ts';
	import Icon from '#lib/Icon.svelte';

	let { months, capacity = null }: { months: MonthRow[]; capacity?: number | null } = $props();

	const rows = $derived(months ?? []);
	const hasGen = $derived(rows.some((r) => r.gen_kwh != null));
	const max = $derived(Math.max(1, ...rows.map((r) => Math.max(r.cons_kwh ?? 0, r.gen_kwh ?? 0))));
	const avg = $derived(rows.length ? rows.reduce((a, r) => a + (r.cons_kwh ?? 0), 0) / rows.length : 0);
	const sum = (k: 'gen_kwh' | 'saved_uah') => {
		const key = k === 'gen_kwh' ? 'gen_kwh' : 'saved_uah';
		const v = rows.map((r) => r[key]);
		return v.some((x) => x != null) ? v.reduce((a: number, x) => a + (x ?? 0), 0) : null;
	};
	const genYear = $derived(sum('gen_kwh'));
	const savedYear = $derived(sum('saved_uah'));
	const curMonth = new Date().getMonth();

	type Def = { key: keyof MonthRow; label: string; cls: string };
	const defs: Def[] = [
		{ key: 'cons_kwh', label: 'Спожито', cls: 'c-cons' },
		{ key: 'gen_kwh', label: 'Згенеровано', cls: 'c-gen' },
		{ key: 'battery_kwh', label: 'Через акумулятор', cls: 'c-bat' },
		{ key: 'surplus_kwh', label: 'Надлишок', cls: 'c-sur' },
		{ key: 'grid_kwh', label: 'З мережі', cls: 'c-grid' },
		{ key: 'saved_uah', label: 'Заощаджено, грн', cls: 'c-sav' }
	];
	const shown = $derived(defs.filter((d) => rows.some((r) => r[d.key] != null)));
	const h = (v: number | null | undefined) => `${Math.max(v ? 2 : 0, ((v ?? 0) / max) * 100)}%`;
</script>

<div class="panel mo">
	<div class="head tnum">
		<p><span class="l">сер. спожито/міс</span> <b>{num(avg)}</b> <small>кВт·год</small></p>
		{#if genYear != null}<p class="gen"><span class="l"><Icon name="sun" size={14} /> Σ згенеровано/рік</span> <b>{num(genYear)}</b> <small>кВт·год</small></p>{/if}
		{#if savedYear != null}<p class="sav"><span class="l"><Icon name="wallet" size={14} /> Σ заощаджено/рік</span> <b>{num(savedYear)}</b> <small>грн</small></p>{/if}
		{#if capacity != null && capacity > 0}<p class="bat"><span class="l"><Icon name="battery" size={14} /> акумулятор</span> <b>{num(capacity, 1)}</b> <small>кВт·год</small></p>{/if}
	</div>

	<div class="bars" role="img" aria-label="Споживання та генерація по місяцях, кВт·год">
		{#each rows as r, i (r.month)}
			{@const bat = Math.min(r.battery_kwh ?? 0, r.gen_kwh ?? 0)}
			<div class="col" class:cur={i === curMonth} title="{MONTHS[i]}: спожито {num(r.cons_kwh)}{r.gen_kwh != null ? `, згенеровано ${num(r.gen_kwh)}` : ''} кВт·год">
				<div class="pair">
					<span class="b cons" style="height: {h(r.cons_kwh)}"></span>
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
		{#if hasGen}<span><i class="sw gen"></i>Згенеровано</span><span><i class="sw bt"></i>Через акумулятор</span>{/if}
	</p>

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
</div>

<style>
	.mo {
		padding: 1rem;
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
	.head .sav b {
		color: var(--ok);
	}
	.head .bat b {
		color: var(--bat, #6d4fc2);
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
		height: 150px;
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
		.mo {
			padding: 0.75rem 0.6rem;
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
