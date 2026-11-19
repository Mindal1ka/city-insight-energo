<script lang="ts">
	// «Фінанси»: ліміт vs оплачено (з мережі), заощадження від СЕС, окупність. Ліміти — МОК.
	import { errMessage } from '#lib/api.ts';
	import { auth } from '#lib/auth.svelte.ts';
	import { fetchDepartments, fetchBudgetReal, fetchSpending, type Departments, type BudgetReal, type Spending } from '#lib/api-v2.ts';
	import { uah } from '#lib/api-ses.ts';
	import { num, MONTHS_FULL } from '#lib/format.ts';
	import StatCard from '#lib/StatCard.svelte';
	import Icon from '#lib/Icon.svelte';
	import Skeleton from '#lib/Skeleton.svelte';
	import SourceTag from '#lib/SourceTag.svelte';
	import { MONTHS } from '#lib/format.ts';

	let data = $state<Departments | null>(null);
	let real = $state<BudgetReal | null>(null);
	let sp = $state<Spending | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);

	async function load() {
		loading = true;
		error = null;
		try {
			fetchBudgetReal().then((r) => (real = r), () => (real = null));
			fetchSpending().then((r) => (sp = r), () => (sp = null));
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

	const short = (n: string, max = 40) => (n.length > max ? n.slice(0, max - 1).trimEnd() + '…' : n);
	const pctOf = (a: number | null, b: number | null) => (a != null && b ? Math.min(100, (a / b) * 100) : 0);
	const sumMonths = (k: 'monthly_2025' | 'monthly_2026') =>
		Array.from({ length: 12 }, (_, i) => {
			let any = false;
			let sum = 0;
			for (const p of real?.items ?? []) {
				const v = p[k]?.[i];
				if (v != null) {
					any = true;
					sum += v;
				}
			}
			return any ? sum : null;
		});
	const m25 = $derived(sumMonths('monthly_2025'));
	const m26 = $derived(sumMonths('monthly_2026'));
	const mMax = $derived(Math.max(1, ...m25.map((v) => v ?? 0), ...m26.map((v) => v ?? 0)));
	const hh = (v: number | null) => (v == null ? '0%' : `${Math.max(2, (v / mMax) * 100)}%`);
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

{#if real}
	<section class="card list real" aria-label="Реальний бюджет">
		<h2>Реальний бюджет на електроенергію (КЕКВ {real.kekv ?? 2273}) <SourceTag kind="openbudget" /></h2>
		<div class="scroll-x">
			<table class="rt tnum">
				<thead>
					<tr><th>Програма</th><th>План 2026</th><th>Сплачено 2026</th><th>Факт 2025</th><th>Ціна 2025, грн/кВт·год</th><th>Будівель</th></tr>
				</thead>
				<tbody>
					{#each real.items.filter((x) => x.buildings > 0) as p (p.program)}
						<tr class:muted={!p.allocated}>
							<th scope="row" title={p.name}>
								{short(p.name)}
								{#if !p.allocated}<span class="note" title="будівлі UMUNI покривають програму частково — ліміти будівель МОК"><Icon name="info" size={14} /></span>{/if}
							</th>
							<td>{p.plan_2026 == null ? '—' : uah(p.plan_2026)}</td>
							<td>
								<span class="pb"><i style="width:{pctOf(p.fact_2026, p.plan_2026)}%"></i></span>
								<small>{p.fact_2026 == null ? '—' : uah(p.fact_2026)}{p.plan_2026 ? ` · ${num(pctOf(p.fact_2026, p.plan_2026))} %` : ''}</small>
							</td>
							<td>{p.fact_2025 == null ? '—' : uah(p.fact_2025)}</td>
							<td>{p.price_2025 == null ? '—' : num(p.price_2025, 2)}</td>
							<td>{num(p.buildings)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		{#if real.items.some((x) => x.buildings === 0)}
			{@const rest = real.items.filter((x) => x.buildings === 0)}
			<details class="rest">
				<summary>Інші програми без будівель в UMUNI: {rest.length} · план 2026 {uah(rest.reduce((a, x) => a + (x.plan_2026 ?? 0), 0))}</summary>
				<ul>
					{#each rest as p (p.program)}<li title={p.name}>{short(p.name)} — {p.plan_2026 == null ? '—' : uah(p.plan_2026)}</li>{/each}
				</ul>
			</details>
		{/if}
		<h3>Платежі по місяцях: 2025 vs 2026</h3>
		<div class="bars" role="img" aria-label="Платежі по місяцях, грн">
			{#each MONTHS as m, i (m)}
				<div class="col" title="{m}: 2025 — {m25[i] == null ? '—' : uah(m25[i])}; 2026 — {m26[i] == null ? '—' : uah(m26[i])}">
					<div class="pair">
						<span class="b y25" style="height:{hh(m25[i])}"></span>
						<span class="b y26" style="height:{hh(m26[i])}"></span>
					</div>
					<span class="mn">{m}</span>
				</div>
			{/each}
		</div>
		<p class="lg"><span><i class="sw y25"></i>2025</span><span><i class="sw y26"></i>2026</span></p>
		{#if sp && Object.keys(sp.years).length}
			<div class="spd">
				<h3>Фактичні платежі Департаменту освіти <SourceTag kind="openbudget" label="spending.gov.ua" href="https://spending.gov.ua" /></h3>
				{#each Object.entries(sp.years) as [y, v] (y)}
					{@const last = sp.items.filter((i) => String(i.year) === y).at(-1)?.month}
					<p><b>{y}{last && last < 12 ? ` (січ–${MONTHS[last - 1]})` : ''}:</b> енергія {uah(v['енергія'])} · розподіл (Полтаваобленерго) {uah(v['розподіл'])}{v.distribution_share_pct != null ? ` — ${num(v.distribution_share_pct, 1)} %` : ''}</p>
				{/each}
			</div>
		{/if}
	</section>
{/if}

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
					<span>Не вистачає сонця {d.deficit}{d.over_limit > 0 ? ` · перевитрата ${d.over_limit}` : ''}</span>
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
	.real {
		margin-bottom: 1.1rem;
	}
	.real h2 {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.3rem 0.6rem;
	}
	.real h3 {
		margin: 1rem 0 0.5rem;
		font-size: 0.95rem;
	}
	.scroll-x {
		overflow-x: auto;
	}
	.rt {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.85rem;
	}
	.rt th,
	.rt td {
		padding: 0.45rem 0.5rem;
		text-align: right;
		border-top: 1px solid var(--line-soft);
		white-space: nowrap;
	}
	.rt thead th {
		border-top: 0;
		color: var(--muted);
		font-weight: 600;
		font-size: 0.75rem;
	}
	.rt th:first-child,
	.rt td:first-child {
		text-align: left;
	}
	.rt tbody th {
		font-weight: 600;
		color: var(--text);
	}
	.rt tr.muted {
		opacity: 0.6;
	}
	.note {
		display: inline-flex;
		vertical-align: middle;
		cursor: help;
		color: var(--warn);
	}
	.pb {
		display: block;
		height: 6px;
		min-width: 5rem;
		background: var(--line-soft);
		border-radius: 999px;
		overflow: hidden;
	}
	.pb i {
		display: block;
		height: 100%;
		background: var(--ok);
	}
	.rt small {
		color: var(--muted);
	}
	.bars {
		display: grid;
		grid-template-columns: repeat(12, 1fr);
		gap: 0.25rem;
		height: 120px;
	}
	.col {
		display: grid;
		grid-template-rows: 1fr auto;
		gap: 2px;
		min-width: 0;
	}
	.pair {
		display: flex;
		align-items: flex-end;
		justify-content: center;
		gap: 2px;
	}
	.b {
		flex: 1 1 0;
		max-width: 14px;
		border-radius: 3px 3px 0 0;
	}
	.b.y25,
	.sw.y25 {
		background: var(--line-strong, #b8c0cc);
	}
	.b.y26,
	.sw.y26 {
		background: var(--ok);
	}
	.mn {
		text-align: center;
		font-size: 11px;
		color: var(--muted);
	}
	.lg {
		display: flex;
		gap: 1rem;
		margin: 0.4rem 0 0;
		font-size: 0.75rem;
		color: var(--muted);
	}
	.lg span {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
	}
	.sw {
		width: 0.7rem;
		height: 0.7rem;
		border-radius: 3px;
		display: inline-block;
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
	.rest {
		margin: 0.6rem 0 0.4rem;
		font-size: 0.85rem;
		color: var(--muted);
	}
	.rest summary {
		cursor: pointer;
	}
	.rest ul {
		margin: 0.4rem 0 0;
		padding-left: 1.1rem;
		columns: 2;
	}
	.spd {
		margin-top: 0.8rem;
		padding-top: 0.6rem;
		border-top: 1px solid var(--line, #e3e7ee);
		font-size: 0.88rem;
	}
	.spd h3 {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.spd p {
		margin: 0.2rem 0;
	}
</style>
