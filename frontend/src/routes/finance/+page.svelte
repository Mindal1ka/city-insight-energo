<script lang="ts">
	// «Фінанси департаментів»: ліміт vs оплачено (з мережі), заощадження від СЕС, окупність. Ліміти — МОК.
	import { errMessage } from '#lib/api.ts';
	import { auth } from '#lib/auth.svelte.ts';
	import { fetchDepartments, type Departments } from '#lib/api-v2.ts';
	import { uah } from '#lib/api-ses.ts';
	import { num, MONTHS_FULL } from '#lib/format.ts';
	import StatCard from '#lib/StatCard.svelte';
	import Icon from '#lib/Icon.svelte';
	import Skeleton from '#lib/Skeleton.svelte';

	let data = $state<Departments | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);

	async function load() {
		loading = true;
		error = null;
		try {
			data = await fetchDepartments();
		} catch (e) {
			error = errMessage(e);
		} finally {
			loading = false;
		}
	}
	$effect(() => {
		void auth.user?.token;
		load();
	});

	const t = $derived(data?.totals);
	const usedTone = (p: number | null | undefined) => (p == null ? 'neutral' : p > 100 ? 'bad' : p > 90 ? 'warn' : 'good');
	const barPct = (paid: number, limit: number) => (limit > 0 ? Math.min(100, (paid / limit) * 100) : 0);
</script>

<svelte:head><title>Фінанси департаментів · Енергія</title></svelte:head>

<div class="pg">
	<header class="hd">
		<h1><Icon name="wallet" size={26} /> Фінанси департаментів</h1>
		<span class="mok" title="Ліміти змодельовані: споживання 2025 × тариф × 0,9–1,1">МОК</span>
	</header>

	{#if loading && !data}
		<Skeleton variant="kpis" count={8} />
	{:else if error && !data}
		<div class="state err" role="alert">{error} <button type="button" onclick={load}>Повторити</button></div>
	{:else if data && t}
		<div class="stat-grid">
			<StatCard label="Ліміт / рік" value={t.limit_uah_year} format={uah} icon="wallet" demo />
			<StatCard label="Оплачено / рік" value={t.paid_uah_year} format={uah} icon="plug" tone={usedTone(t.used_pct_year)} />
			<StatCard label="Без СЕС коштувало б" value={t.without_ses_uah_year} format={uah} icon="bolt" />
			<StatCard label="Заощаджено СЕС / рік" value={t.saved_uah_year} format={uah} icon="sun" tone="good" />
			<StatCard label="Вкладено в СЕС" value={t.invested_uah} format={uah} icon="panel" />
			<StatCard label="Використання ліміту" value={t.used_pct_year} unit="%" decimals={0} icon="gauge" tone={usedTone(t.used_pct_year)} />
			<StatCard label="Перевитрата, об’єктів" value={t.over_limit} icon="alert" tone={t.over_limit > 0 ? 'bad' : 'good'} />
		</div>

		<h2 class="sub">{MONTHS_FULL[(data.month ?? 1) - 1]}</h2>

		<div class="cards">
			{#each data.items as d (d.department)}
				{@const over = d.paid_uah_year > d.limit_uah_year}
				{@const overM = d.paid_uah_month > d.limit_uah_month}
				<a class="card" href="/objects?department={encodeURIComponent(d.department)}">
					<div class="top">
						<strong>{d.department}</strong>
						<span class="bal" class:bad={d.balance_uah_year < 0} class:ok={d.balance_uah_year >= 0}>
							{d.balance_uah_year >= 0 ? '+' : '−'}{uah(Math.abs(d.balance_uah_year))}
						</span>
					</div>
					<div class="bar" class:over role="img" aria-label="Оплачено {num(d.used_pct_year)} % ліміту">
						<i style="width:{barPct(d.paid_uah_year, d.limit_uah_year)}%"></i>
					</div>
					<div class="row">
						<span>{uah(d.paid_uah_year)} / {uah(d.limit_uah_year)}</span>
						<b class:bad={over}>{d.used_pct_year == null ? '—' : num(d.used_pct_year) + ' %'}</b>
					</div>
					<div class="row sm" class:bad={overM}>
						<span>Місяць: {uah(d.paid_uah_month)} / {uah(d.limit_uah_month)}</span>
						{#if overM}<Icon name="alert" size={14} />{/if}
					</div>
					<div class="chips">
						<span title="Об’єктів"><Icon name="building" size={14} /> {d.objects}</span>
						<span title="З СЕС"><Icon name="sun" size={14} /> {d.with_ses}</span>
						<span class="def" title="Не вистачає">▼ {d.deficit}</span>
						<span class="sur" title="Надлишок">▲ {d.surplus}</span>
						{#if d.over_limit > 0}<span class="bad" title="Перевитрата"><Icon name="alert" size={14} /> {d.over_limit}</span>{/if}
					</div>
					<div class="fin">
						<span title="Заощаджено/рік"><Icon name="sun" size={14} /> {uah(d.saved_uah_year)}</span>
						<span title="Вкладено"><Icon name="panel" size={14} /> {uah(d.invested_uah)}</span>
						<span title="Окупність"><Icon name="clock" size={14} /> {d.payback_years == null ? '—' : num(d.payback_years, 1) + ' р.'}</span>
					</div>
				</a>
			{/each}
		</div>
	{/if}
</div>

<style>
	.pg { max-width: 1200px; margin: 0 auto; padding: 1rem; }
	.hd { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 1rem; }
	h1 { margin: 0; font-size: var(--fs-xl); display: flex; align-items: center; gap: 0.5rem; }
	.sub { font-size: var(--fs-md); color: var(--muted); margin: 1.25rem 0 0.5rem; }
	.mok { font-size: var(--fs-xs); font-weight: 700; padding: 0.15rem 0.55rem; border-radius: 999px; background: var(--warn-soft); color: var(--warn); }
	.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 0.75rem; }
	.card { display: flex; flex-direction: column; gap: 0.5rem; padding: 0.9rem; background: var(--surface); border: 1px solid var(--card-line); border-radius: var(--radius); color: var(--text); text-decoration: none; box-shadow: var(--shadow); }
	.card:hover { border-color: var(--accent); }
	.top { display: flex; justify-content: space-between; gap: 0.5rem; align-items: baseline; }
	.bal { font-weight: 700; white-space: nowrap; }
	.bar { height: 10px; background: var(--line-soft); border-radius: 999px; overflow: hidden; }
	.bar i { display: block; height: 100%; background: var(--ok); }
	.bar.over i { background: var(--bad); }
	.row { display: flex; justify-content: space-between; gap: 0.5rem; font-size: var(--fs-sm); }
	.row.sm { font-size: var(--fs-xs); color: var(--muted); }
	.bad { color: var(--bad); }
	.ok { color: var(--ok); }
	.chips, .fin { display: flex; flex-wrap: wrap; gap: 0.75rem; font-size: var(--fs-sm); }
	.chips span, .fin span { display: inline-flex; align-items: center; gap: 0.25rem; }
	.def { color: var(--warn); }
	.sur { color: var(--ok); }
	.fin { padding-top: 0.5rem; border-top: 1px solid var(--line-soft); }
	.state.err { padding: 1rem; background: var(--bad-soft); color: var(--bad); border-radius: var(--radius); }
</style>
