<script lang="ts">
	// «Звіт за місяць»: підсумки, фін. ефект вкладень, таблиця об'єктів, CSV і друк.
	import { errMessage } from '#lib/api.ts';
	import { auth } from '#lib/auth.svelte.ts';
	import { fetchReport, downloadReportCsv, DEPARTMENTS, type Report, type ReportRow } from '#lib/api-v2.ts';
	import { uah, kwh } from '#lib/api-ses.ts';
	import { num } from '#lib/format.ts';
	import StatCard from '#lib/StatCard.svelte';
	import Icon from '#lib/Icon.svelte';
	import Skeleton from '#lib/Skeleton.svelte';

	const now = new Date();
	let month = $state(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`);
	let data = $state<Report | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);
	let seq = 0;

	async function load(m: string) {
		const my = ++seq;
		loading = true;
		error = null;
		try {
			const d = await fetchReport(m || undefined);
			if (my === seq) data = d;
		} catch (e) {
			if (my === seq) error = errMessage(e);
		} finally {
			if (my === seq) loading = false;
		}
	}
	$effect(() => {
		void auth.user?.token;
		load(month);
	});

	let csvBusy = $state(false);
	async function csv() {
		csvBusy = true;
		try {
			await downloadReportCsv(month || undefined);
		} catch (e) {
			error = errMessage(e);
		} finally {
			csvBusy = false;
		}
	}

	let q = $state('');
	let dep = $state('');
	type Key = 'name' | 'cons_kwh' | 'grid_kwh' | 'cost_uah' | 'saved_uah' | 'limit_uah';
	let sortKey = $state<Key>('cost_uah');
	let asc = $state(false);
	const norm = (s: string) => s.toLocaleLowerCase('uk').replace(/[’ʼ`´']/g, '');

	const rows = $derived.by(() => {
		const nq = norm(q.trim());
		const list = (data?.items ?? []).filter((r) => (!dep || r.department === dep) && (!nq || norm(r.name).includes(nq)));
		const k = sortKey;
		return list.sort((a, b) => {
			const r = k === 'name' ? a.name.localeCompare(b.name, 'uk') : (a[k] as number) - (b[k] as number);
			return asc ? r : -r;
		});
	});
	function sort(k: Key) {
		if (sortKey === k) asc = !asc;
		else {
			sortKey = k;
			asc = k === 'name';
		}
	}
	const arrow = (k: Key) => (sortKey === k ? (asc ? ' ▲' : ' ▼') : '');

	const t = $derived(data?.totals);
	const paybackPct = $derived(t && t.invested_uah > 0 ? (t.saved_since_launch_uah / t.invested_uah) * 100 : null);
	const over = (r: ReportRow) => r.limit_uah > 0 && r.cost_uah > r.limit_uah;
	const COLS: [Key, string][] = [
		['cons_kwh', 'Спожито'],
		['grid_kwh', 'З мережі'],
		['cost_uah', 'Вартість'],
		['saved_uah', 'Заощаджено'],
		['limit_uah', 'Ліміт']
	];
</script>

<svelte:head><title>Звіт за місяць · Insight Tool</title></svelte:head>

<header class="page-head">
	<div class="ph-text">
		<h1>Звіт за місяць</h1>
		<p class="ph-sub print-only">{month}</p>
	</div>
	<div class="side noprint">
		<input type="month" bind:value={month} aria-label="Місяць" />
		<button type="button" onclick={csv} disabled={csvBusy}>CSV</button>
		<button type="button" onclick={() => window.print()}>Друк</button>
	</div>
</header>

{#if loading && !data}
	<Skeleton variant="kpis" count={4} />
{:else if error && !data}
	<div class="state err" role="alert">{error} <button type="button" onclick={() => load(month)}>Повторити</button></div>
{:else if data && t}
	<div class="kpis">
		<StatCard label="Спожито" value={t.cons_kwh} format={kwh} icon="plug" />
		<StatCard
			label="Вартість · ліміт {uah(t.limit_uah)}"
			value={t.cost_uah}
			format={uah}
			icon="wallet"
			tone={t.limit_uah > 0 && t.cost_uah > t.limit_uah ? 'bad' : 'neutral'}
		/>
		<StatCard label="Заощаджено" value={t.saved_uah} format={uah} icon="sun" tone="good" />
		<StatCard label="K" value={t.k} decimals={2} icon="gauge" />
	</div>

	<section class="fx" aria-label="Фінансовий ефект вкладень">
		<div class="fxrow">
			<b>Фін. ефект вкладень</b>
			<span><Icon name="panel" size={15} /> вкладено {uah(t.invested_uah)}</span>
			<span><Icon name="check" size={15} /> повернуто {uah(t.saved_since_launch_uah)}</span>
			<b class:ok={(paybackPct ?? 0) >= 100}>{paybackPct == null ? '—' : num(paybackPct, 1) + ' %'}</b>
		</div>
		{#if paybackPct != null}
			<div class="bar"><i style="width:{Math.min(100, paybackPct)}%"></i></div>
		{/if}
	</section>

	{#if data.items.length}
		<div class="filters noprint">
			<input type="search" placeholder="Пошук" bind:value={q} aria-label="Пошук" />
			<select bind:value={dep} aria-label="Розпорядник">
				<option value="">Усі розпорядники</option>
				{#each DEPARTMENTS as d (d)}<option value={d}>{d}</option>{/each}
			</select>
			<span class="cnt">{rows.length}</span>
		</div>
		<div class="tw">
			<table>
				<thead>
					<tr>
						<th><button type="button" onclick={() => sort('name')}>Об’єкт{arrow('name')}</button></th>
						{#each COLS as [k, l] (k)}
							<th class="r"><button type="button" onclick={() => sort(k)}>{l}{arrow(k)}</button></th>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each rows as r (r.id)}
						<tr>
							<td class="nm">
								<a href="/object/{r.id}">{r.name}</a>
								{#if r.has_ses}<Icon name="sun" size={13} />{/if}
							</td>
							<td class="r" data-l="Спожито">{num(r.cons_kwh)}</td>
							<td class="r" data-l="З мережі">{num(r.grid_kwh)}</td>
							<td class="r" data-l="Вартість" class:bad={over(r)}>{num(r.cost_uah)}</td>
							<td class="r ok" data-l="Заощаджено">{num(r.saved_uah)}</td>
							<td class="r" data-l="Ліміт">{num(r.limit_uah)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
{/if}

<style>
	.page-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		flex-wrap: wrap;
		gap: 0.6rem;
		margin-bottom: 1rem;
	}
	.page-head h1 {
		margin: 0;
	}
	.ph-sub {
		margin: 0.15rem 0 0;
		font-size: 0.8125rem;
		color: var(--muted);
	}
	.side,
	.filters {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
		align-items: center;
	}
	input,
	select,
	button {
		font: inherit;
		padding: 0.4rem 0.6rem;
		border: 1px solid var(--line);
		border-radius: var(--radius-sm);
		background: var(--surface);
		color: var(--text);
	}
	button {
		cursor: pointer;
	}
	.side button {
		font-weight: 600;
	}
	.print-only {
		display: none;
	}
	.kpis {
		--fs-stat: 1.85rem;
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 11rem), 1fr));
		gap: 0.75rem;
		margin-bottom: 1rem;
	}
	.fx {
		margin: 0 0 1rem;
		padding: 0.7rem 0.9rem;
		background: var(--surface);
		border: 1px solid var(--card-line);
		border-radius: var(--radius);
	}
	.fxrow {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 1.1rem;
		align-items: center;
		font-size: 0.9rem;
	}
	.fxrow span {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		color: var(--text-2);
	}
	.fxrow b:last-child {
		margin-left: auto;
	}
	.bar {
		height: 8px;
		background: var(--line-soft);
		border-radius: 999px;
		margin-top: 0.5rem;
		overflow: hidden;
	}
	.bar i {
		display: block;
		height: 100%;
		background: var(--ok);
	}
	.filters {
		margin: 0 0 0.5rem;
	}
	.cnt {
		color: var(--muted);
		font-size: var(--fs-sm);
	}
	.tw {
		overflow-x: auto;
		background: var(--surface);
		border: 1px solid var(--card-line);
		border-radius: var(--radius);
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--fs-sm);
	}
	th,
	td {
		padding: 0.4rem 0.6rem;
		border-bottom: 1px solid var(--line-soft);
		white-space: nowrap;
	}
	th button {
		border: 0;
		padding: 0;
		background: none;
		font-weight: 700;
		color: var(--muted);
	}
	.r {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}
	.nm {
		white-space: normal;
		min-width: 180px;
	}
	.nm a {
		color: var(--accent);
		text-decoration: none;
	}
	.bad {
		color: var(--bad);
		font-weight: 700;
	}
	.ok {
		color: var(--ok);
	}
	.state.err {
		padding: 1rem;
		background: var(--bad-soft);
		color: var(--bad);
		border-radius: var(--radius);
	}

	@media (max-width: 640px) {
		.kpis {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 0.6rem;
		}
		.tw {
			background: none;
			border: 0;
		}
		thead {
			display: none;
		}
		table,
		tbody {
			display: block;
		}
		tr {
			display: grid;
			grid-template-columns: 1fr 1fr;
			gap: 0.1rem 0.8rem;
			margin-bottom: 0.6rem;
			padding: 0.6rem 0.8rem;
			background: var(--surface);
			border: 1px solid var(--card-line);
			border-radius: var(--radius);
		}
		td {
			border: 0;
			padding: 0.1rem 0;
			display: flex;
			justify-content: space-between;
			gap: 0.5rem;
		}
		td.nm {
			grid-column: 1 / -1;
			font-weight: 600;
		}
		td[data-l]::before {
			content: attr(data-l);
			color: var(--muted);
			font-weight: 400;
		}
	}

	@media print {
		:global(nav),
		:global(header.site),
		:global(footer),
		:global([role='navigation']) {
			display: none !important;
		}
		.noprint {
			display: none !important;
		}
		.print-only {
			display: block;
		}
		.tw {
			overflow: visible;
			border: 0;
		}
	}
</style>
