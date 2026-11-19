<script lang="ts">
	// «Фінанси»: ліміт vs оплачено (з мережі), заощадження від СЕС, окупність. Ліміти — МОК.
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
	const barPct = (paid: number, limit: number) => (limit > 0 ? Math.min(100, (paid / limit) * 100) : 0);
	const sgn = (v: number) => `${v >= 0 ? '+' : '−'}${uah(Math.abs(v))}`;
</script>

<svelte:head><title>Фінанси · Insight Tool</title></svelte:head>

<header class="page-head">
	<div class="ph-text">
		<h1>Фінанси</h1>
		{#if data}<p class="ph-sub">Ліміти і оплата за електроенергію · {MONTHS_FULL[(data.month ?? 1) - 1]}</p>{/if}
	</div>
	<div class="head-side">
		<span class="mok" title="Ліміти змодельовані: споживання 2025 × тариф × 0,9–1,1">МОК</span>
	</div>
</header>

{#if loading && !data}
	<Skeleton variant="kpis" count={4} />
{:else if error && !data}
	<div class="state err" role="alert">{error} <button type="button" onclick={load}>Повторити</button></div>
{:else if data && t}
	<div class="kpis">
		<StatCard label="Ліміт на рік" value={t.limit_uah_year} format={uah} icon="wallet" />
		<StatCard label="Оплачено" value={t.paid_uah_year} format={uah} icon="plug" tone={t.used_pct_year != null && t.used_pct_year > 100 ? 'bad' : 'neutral'} />
		<StatCard label="Заощаджено СЕС" value={t.saved_uah_year} format={uah} icon="sun" tone="good" />
		<StatCard label="Перевищують ліміт" value={t.over_limit} unit="об'єктів" icon="alert" tone={t.over_limit > 0 ? 'bad' : 'good'} />
	</div>

	<section class="card list" aria-label="Розпорядники">
		<h2>Розпорядники</h2>
		{#each data.items as d (d.department)}
			{@const over = d.paid_uah_year > d.limit_uah_year}
			<details class="dep">
				<summary>
					<span class="nm">{d.department}</span>
					<span class="bar" class:over role="img" aria-label="Оплачено {num(d.used_pct_year)} % ліміту">
						<i style="width:{barPct(d.paid_uah_year, d.limit_uah_year)}%"></i>
					</span>
					<b class="pct" class:bad={over}>{d.used_pct_year == null ? '—' : num(d.used_pct_year) + ' %'}</b>
					<span class="bal" class:bad={d.balance_uah_year < 0} class:ok={d.balance_uah_year >= 0}>{sgn(d.balance_uah_year)}</span>
				</summary>
				<div class="more">
					<span>Оплачено {uah(d.paid_uah_year)} з {uah(d.limit_uah_year)}</span>
					<span class:bad={d.paid_uah_month > d.limit_uah_month}>Місяць: {uah(d.paid_uah_month)} / {uah(d.limit_uah_month)}</span>
					<span><Icon name="building" size={14} /> {d.objects} об'єктів, з СЕС {d.with_ses}</span>
					<span>Дефіцит {d.deficit} · надлишок {d.surplus}{d.over_limit > 0 ? ` · перевитрата ${d.over_limit}` : ''}</span>
					<span><Icon name="panel" size={14} /> Вкладено {uah(d.invested_uah)}</span>
					<span><Icon name="clock" size={14} /> Окупність {d.payback_years == null ? '—' : num(d.payback_years, 1) + ' р.'}</span>
					<a href="/objects?department={encodeURIComponent(d.department)}">Об'єкти розпорядника →</a>
				</div>
			</details>
		{/each}
	</section>
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
	.mok {
		padding: 0.15rem 0.6rem;
		border-radius: 999px;
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		background: var(--sun-soft);
		color: var(--sun-ink);
		border: 1px dashed #d08a1c;
		cursor: help;
	}
	.kpis {
		--fs-stat: 1.85rem;
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 11rem), 1fr));
		gap: 0.75rem;
		margin-bottom: 1.1rem;
	}
	.list {
		margin: 0;
		padding: 0.9rem 1rem;
	}
	.list h2 {
		margin: 0 0 0.3rem;
		font-size: 1.08rem;
	}
	.dep {
		border-top: 1px solid var(--line-soft);
	}
	.dep summary {
		display: grid;
		grid-template-columns: minmax(8rem, 1.4fr) minmax(5rem, 2fr) 3.2rem minmax(6.5rem, auto);
		align-items: center;
		gap: 0.3rem 0.9rem;
		padding: 0.7rem 0;
		cursor: pointer;
		list-style: none;
	}
	.dep summary::-webkit-details-marker {
		display: none;
	}
	.nm {
		font-weight: 600;
		color: var(--text);
	}
	.bar {
		height: 10px;
		background: var(--line-soft);
		border-radius: 999px;
		overflow: hidden;
	}
	.bar i {
		display: block;
		height: 100%;
		background: var(--ok);
	}
	.bar.over i {
		background: var(--bad);
	}
	.pct,
	.bal {
		font-variant-numeric: tabular-nums;
		text-align: right;
		white-space: nowrap;
	}
	.bal {
		font-weight: 700;
	}
	.bad {
		color: var(--bad);
	}
	.ok {
		color: var(--ok);
	}
	.more {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 1.2rem;
		padding: 0 0 0.8rem;
		font-size: 0.875rem;
		color: var(--text-2);
	}
	.more span {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
	}
	.more a {
		font-weight: 600;
		color: var(--accent);
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
		.dep summary {
			grid-template-columns: 1fr auto auto;
		}
		.dep summary .nm {
			grid-column: 1 / -1;
		}
		.dep summary .bar {
			grid-column: 1;
		}
	}
</style>
