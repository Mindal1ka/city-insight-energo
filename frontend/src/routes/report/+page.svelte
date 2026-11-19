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
	type Key = 'name' | 'cons_kwh' | 'gen_kwh' | 'surplus_kwh' | 'grid_kwh' | 'cost_uah' | 'limit_uah' | 'saved_uah';
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
		['gen_kwh', 'Генер.'],
		['surplus_kwh', 'Надл.'],
		['grid_kwh', 'Мережа'],
		['cost_uah', 'Вартість'],
		['limit_uah', 'Ліміт'],
		['saved_uah', 'Заощ.']
	];
</script>

<svelte:head><title>Звіт за місяць · Енергія</title></svelte:head>

<div class="pg">
	<header class="hd">
		<h1><Icon name="chart" size={26} /> Звіт за місяць</h1>
		<div class="side noprint">
			<input type="month" bind:value={month} aria-label="Місяць" />
			<button type="button" onclick={csv} disabled={csvBusy}>CSV</button>
			<button type="button" onclick={() => window.print()}>Друк</button>
		</div>
		<span class="print-only">{month}</span>
	</header>

	{#if loading && !data}
		<Skeleton variant="kpis" count={8} />
	{:else if error && !data}
		<div class="state err" role="alert">{error} <button type="button" onclick={() => load(month)}>Повторити</button></div>
	{:else if data && t}
		<div class="stat-grid">
			<StatCard label="Спожито" value={t.cons_kwh} format={kwh} icon="plug" />
			<StatCard label="Згенеровано" value={t.gen_kwh} format={kwh} icon="sun" tone="good" />
			<StatCard label="Надлишок (віддано / не використано)" value={t.surplus_kwh} format={kwh} icon="battery" />
			<StatCard label="З мережі" value={t.grid_kwh} format={kwh} icon="bolt" />
			<StatCard
				label="Вартість е/е · ліміт {uah(t.limit_uah)}"
				value={t.cost_uah}
				format={uah}
				icon="wallet"
				tone={t.limit_uah > 0 && t.cost_uah > t.limit_uah ? 'bad' : 'neutral'}
			/>
			<StatCard label="Перевитрата" value={t.over_limit_uah} format={uah} icon="alert" tone={t.over_limit_uah > 0 ? 'bad' : 'good'} />
			<StatCard label="Заощаджено за місяць" value={t.saved_uah} format={uah} icon="sun" tone="good" />
			<StatCard label="K" value={t.k} decimals={2} icon="gauge" />
		</div>

		<section class="fx" aria-label="Фінансовий ефект вкладень">
			<h2>Фін. ефект вкладень</h2>
			<div class="fxrow">
				<span><Icon name="sun" size={16} /> {uah(t.saved_uah_year)} / рік</span>
				<span><Icon name="panel" size={16} /> {uah(t.invested_uah)}</span>
				<span><Icon name="check" size={16} /> {uah(t.saved_since_launch_uah)} з запуску</span>
				<b class:ok={(paybackPct ?? 0) >= 100}>{paybackPct == null ? '—' : num(paybackPct, 1) + ' % окупності'}</b>
			</div>
			{#if paybackPct != null}
				<div class="bar"><i style="width:{Math.min(100, paybackPct)}%"></i></div>
			{/if}
		</section>

		{#if data.items.length}
			<div class="filters noprint">
				<input type="search" placeholder="Пошук" bind:value={q} aria-label="Пошук" />
				<select bind:value={dep} aria-label="Департамент">
					<option value="">Усі департаменти</option>
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
								<td class="r">{num(r.cons_kwh)}</td>
								<td class="r">{num(r.gen_kwh)}</td>
								<td class="r">{num(r.surplus_kwh)}</td>
								<td class="r">{num(r.grid_kwh)}</td>
								<td class="r" class:bad={over(r)}>{num(r.cost_uah)}</td>
								<td class="r">{num(r.limit_uah)}</td>
								<td class="r ok">{num(r.saved_uah)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}
</div>

<style>
	.pg { max-width: 1200px; margin: 0 auto; padding: 1rem; }
	.hd { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 1rem; justify-content: space-between; }
	h1 { margin: 0; font-size: var(--fs-xl); display: flex; align-items: center; gap: 0.5rem; }
	.side, .filters { display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; }
	input, select, button { font: inherit; padding: 0.4rem 0.6rem; border: 1px solid var(--line); border-radius: var(--radius-sm); background: var(--surface); color: var(--text); }
	button { cursor: pointer; }
	.side button { font-weight: 600; }
	.print-only { display: none; }
	.fx { margin: 1rem 0; padding: 0.9rem; background: var(--surface); border: 1px solid var(--card-line); border-radius: var(--radius); }
	.fx h2 { margin: 0 0 0.5rem; font-size: var(--fs-md); color: var(--muted); }
	.fxrow { display: flex; flex-wrap: wrap; gap: 1rem; align-items: center; }
	.fxrow span { display: inline-flex; align-items: center; gap: 0.3rem; }
	.bar { height: 8px; background: var(--line-soft); border-radius: 999px; margin-top: 0.6rem; overflow: hidden; }
	.bar i { display: block; height: 100%; background: var(--ok); }
	.filters { margin: 1rem 0 0.5rem; }
	.cnt { color: var(--muted); font-size: var(--fs-sm); }
	.tw { overflow-x: auto; background: var(--surface); border: 1px solid var(--card-line); border-radius: var(--radius); }
	table { width: 100%; border-collapse: collapse; font-size: var(--fs-sm); }
	th, td { padding: 0.4rem 0.6rem; border-bottom: 1px solid var(--line-soft); white-space: nowrap; }
	th button { border: 0; padding: 0; background: none; font-weight: 700; color: var(--muted); }
	.r { text-align: right; font-variant-numeric: tabular-nums; }
	.nm { white-space: normal; min-width: 180px; }
	.nm a { color: var(--accent); text-decoration: none; }
	.bad { color: var(--bad); font-weight: 700; }
	.ok { color: var(--ok); }
	.state.err { padding: 1rem; background: var(--bad-soft); color: var(--bad); border-radius: var(--radius); }

	@media print {
		:global(nav), :global(header.site), :global(footer), :global([role='navigation']) { display: none !important; }
		.noprint { display: none !important; }
		.print-only { display: inline; }
		.tw { overflow: visible; border: 0; }
		.pg { padding: 0; max-width: none; }
	}
</style>
