<script lang="ts">
	// «Огляд громади»: три розділи — ефект СЕС, споживання й бюджет 2026, що зробити.
	import { errMessage } from '#lib/api.ts';
	import { auth } from '#lib/auth.svelte.ts';
	import { canSeeGenerators } from '#lib/roles.ts';
	import { fetchSes, kText, type SesList, type SesItem } from '#lib/api-ses.ts';
	import { fetchDepartments, fetchTrend, fetchBudgetReal, fetchGenerators, type Departments, type Trend, type BudgetReal, type GenSummary } from '#lib/api-v2.ts';
	import { num, MONTHS_FULL } from '#lib/format.ts';
	import SourceTag from '#lib/SourceTag.svelte';
	import { moneyShort } from '#lib/dash/DashData.ts';
	import Status from '#lib/Status.svelte';
	import DemoPill from '#lib/DemoPill.svelte';
	import CountUp from '#lib/CountUp.svelte';
	import DashMonthly from '#lib/dash/DashMonthly.svelte';

	let ses = $state<SesList | null>(null);
	let dept = $state<Departments | null>(null);
	let trend = $state<Trend | null>(null);
	let bud = $state<BudgetReal | null>(null);
	let gens = $state<GenSummary | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);

	async function load() {
		loading = true;
		error = null;
		try {
			// Основні дані обов'язкові; решта (залежить від ролі) — якщо є
			const [s, d, tr, br, gn] = await Promise.allSettled([fetchSes('year'), fetchDepartments(), fetchTrend(), fetchBudgetReal(), canSeeGenerators(auth.user) ? fetchGenerators() : Promise.reject(null)]);
			if (s.status === 'rejected') throw s.reason;
			ses = s.value;
			dept = d.status === 'fulfilled' ? d.value : null;
			trend = tr.status === 'fulfilled' ? tr.value : null;
			bud = br.status === 'fulfilled' ? br.value : null;
			gens = gn.status === 'fulfilled' ? gn.value : null; // 403 для управлінь і закладів
		} catch (e) {
			error = errMessage(e);
		} finally {
			loading = false;
		}
	}
	$effect(() => {
		load();
	});

	const t = $derived(ses?.totals);
	const capex = $derived(t?.capex_uah ?? null);
	const saved = $derived(t?.saved_uah_year ?? null);
	const payback = $derived(capex && saved ? capex / saved : null);
	const capexS = $derived(moneyShort(capex ?? 0));
	const savedS = $derived(moneyShort(saved ?? 0));
	const coverPct = $derived(t?.gen_kwh != null && t?.cons_kwh ? (t.gen_kwh / t.cons_kwh) * 100 : null);

	const usedPct = $derived(dept?.totals.used_pct_year ?? null);
	const overLimit = $derived(dept?.totals.over_limit ?? null);

	const trendPct = $derived(trend?.trend_pct ?? null);
	const bt = $derived(bud?.totals ?? null);
	const budMonth = $derived(bud?.updated_month_2026 ?? null);
	const budPct = $derived(bt && bt.plan_2026 > 0 ? Math.min(100, (bt.fact_2026 / bt.plan_2026) * 100) : 0);
	const mln = (v: number) => num(v / 1e6, 1);

	const monthly = $derived.by(() => {
		const m = ses?.monthly;
		if (!m || m.length !== 12) return null;
		return m.map((r) => ({ month: r.month, gen_kwh: r.gen_kwh ?? 0, cons_kwh: r.cons_kwh ?? 0, k: r.k }));
	});

	const withK = (i: SesItem) => i.has_ses && i.k != null && Number.isFinite(i.k);
	const needAll = $derived((ses?.items ?? []).filter((i) => withK(i) && i.k_class === 'Не вистачає'));
	const needExpand = $derived([...needAll].sort((a, b) => (a.k as number) - (b.k as number)).slice(0, 8));
	const withSes = $derived(t?.with_ses ?? null);
	const gt = $derived(gens?.totals ?? null);
	const gCapex = $derived(moneyShort(gt?.capex_uah ?? 0));
	const gFuel = $derived(moneyShort(gt?.fuel_year_uah ?? 0));
</script>

<svelte:head><title>Огляд · Insight Tool</title></svelte:head>

<header class="ph">
	<div>
		<h1>Огляд громади</h1>
		<p class="ph-sub">Електроенергія в комунальних закладах Полтавської громади</p>
	</div>
	{#if ses?.demo}
		<DemoPill text="Станції змодельовані: у міста немає відкритого реєстру СЕС. Споживання й бюджет — реальні." />
	{/if}
</header>

<Status loading={loading && !ses} {error} retry={load} />

{#if ses}
	<!-- 1. Ефект СЕС -->
	<section class="sec" aria-labelledby="s1">
		<div class="sec-h">
			<h2 id="s1">Ефект сонячних станцій</h2>
			<span class="sec-note">За рік, {withSes ?? '—'} об’єктів зі станцією</span>
		</div>
		<div class="strip">
			<div class="cell">
				<span class="l">Вкладено</span>
				<span class="v"><CountUp value={capexS.v} decimals={capexS.d} /><small>{capexS.unit}</small></span>
			</div>
			<div class="cell">
				<span class="l">Заощаджує</span>
				<span class="v good"><CountUp value={savedS.v} decimals={savedS.d} /><small>{savedS.unit} на рік</small></span>
			</div>
			<div class="cell">
				<span class="l">Окупність</span>
				<span class="v">{#if payback == null}—{:else}<CountUp value={payback} decimals={1} /><small>років</small>{/if}</span>
			</div>
			<div class="cell">
				<span class="l">Сонце покриває</span>
				<span class="v">{#if coverPct == null}—{:else}<CountUp value={coverPct} decimals={0} /><small>% споживання об’єктів зі СЕС</small>{/if}</span>
			</div>
		</div>
	</section>

	<!-- 2. Споживання і бюджет -->
	<section class="sec" aria-labelledby="s2">
		<div class="sec-h">
			<h2 id="s2">Споживання і бюджет 2026</h2>
		</div>
		<div class="strip three">
			<div class="cell">
				<span class="l">Споживання за рік (оцінка) <SourceTag kind="umuni" /></span>
				{#if trend?.kwh_2026_est}
					<span class="v">{mln(trend.kwh_2026_est)}<small>млн кВт·год</small></span>
					{#if trendPct != null}
						<span class="d" class:down={trendPct < 0} class:up={trendPct > 0}>{trendPct > 0 ? '+' : ''}{num(trendPct, 1)} % до 2025</span>
					{/if}
				{:else}<span class="v">—</span>{/if}
			</div>
			<a class="cell link" href="/finance">
				<span class="l">Бюджет на електроенергію <SourceTag kind="openbudget" /></span>
				{#if bt}
					<span class="v">{mln(bt.fact_2026)}<small>з {mln(bt.plan_2026)} млн грн сплачено</small></span>
					<span class="bar" aria-hidden="true"><i style="width:{budPct}%"></i></span>
					<span class="d">дані по {budMonth ? MONTHS_FULL[budMonth - 1].toLowerCase() : '—'} · ціна 2025: {bt.price_2025 ? num(bt.price_2025, 2) : '—'} грн/кВт·год</span>
				{:else}<span class="v">—</span>{/if}
			</a>
			<a class="cell link" href="/finance">
				<span class="l">Ліміти закладів</span>
				<span class="v">{usedPct == null ? '—' : num(usedPct, 0)}<small>% річного ліміту використано</small></span>
				{#if overLimit != null}
					<span class="d" class:up={overLimit > 0}>{overLimit > 0 ? `${overLimit} об’єктів понад ліміт` : 'усі в межах ліміту'}</span>
				{/if}
			</a>
		</div>
		{#if monthly}
			<div class="panel-x">
				<h3>Помісячно: генерація СЕС і споживання</h3>
				<DashMonthly months={monthly} />
			</div>
		{/if}
	</section>

	<!-- 3. Резервне живлення -->
	{#if gt && gt.count}
		<section class="sec" aria-labelledby="s3">
			<div class="sec-h">
				<h2 id="s3">Резервне живлення: генератори</h2>
				<DemoPill align="left" text="Генератори й витрати на пальне — оцінка (ДЕМО), крім введених вручну фактичних даних." />
				<span class="sec-note">
					{#if gt.capex_real != null && gt.fuel_real != null}
						фактичні дані: вартість — {gt.capex_real} з {gt.count}, пальне — {gt.fuel_real} з {gt.count}; решта — оцінка
					{:else}
						лише грошові суми, без переліку закладів
					{/if}
				</span>
			</div>
			<div class="strip">
				<div class="cell">
					<span class="l">Генераторів</span>
					<span class="v">{gt.count}{#if gt.kw != null}<small>сумарно {num(gt.kw, 0)} кВт</small>{/if}</span>
				</div>
				<div class="cell">
					<span class="l">Вкладено в генератори</span>
					<span class="v">{num(gCapex.v, gCapex.d)}<small>{gCapex.unit}</small></span>
				</div>
				<div class="cell">
					<span class="l">Пальне за {gens?.year}</span>
					<span class="v bad">{num(gFuel.v, gFuel.d)}<small>{gFuel.unit} · {num(gt.fuel_year_l / 1000, 1)} тис. л</small></span>
				</div>
				<div class="cell">
					<span class="l">Для порівняння: сонце заощаджує</span>
					<span class="v good">{num(savedS.v, savedS.d)}<small>{savedS.unit} на рік</small></span>
				</div>
			</div>
		</section>
	{/if}

	<!-- 4. Що зробити -->
	{#if needExpand.length}
		<section class="sec" aria-labelledby="s4">
			<div class="sec-h">
				<h2 id="s4">Що зробити: станції, яким не вистачає потужності</h2>
				<a class="sec-link" href="/objects">Усі об’єкти ({needAll.length}) →</a>
			</div>
			<div class="tbl">
				<table>
					<thead>
						<tr>
							<th>Об’єкт</th>
							<th>Розпорядник</th>
							<th class="r">Споживання, кВт·год/міс</th>
							<th class="r">Сонце дає</th>
						</tr>
					</thead>
					<tbody>
						{#each needExpand as i (i.id)}
							<tr>
								<td><a href="/object/{i.id}">{i.name}</a></td>
								<td class="muted">{i.department ?? '—'}</td>
								<td class="r tnum">{i.cons_kwh_month_avg != null ? num(i.cons_kwh_month_avg, 0) : '—'}</td>
								<td class="r tnum"><b class="low">{kText(i.k)}</b></td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</section>
	{/if}
{/if}

<style>
	.ph {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 1rem;
		flex-wrap: wrap;
		padding-bottom: 1.25rem;
		margin-bottom: 1.5rem;
		border-bottom: 1px solid var(--card-line);
	}
	.ph h1 {
		margin: 0;
	}
	.ph-sub {
		margin: 0.25rem 0 0;
		color: var(--muted);
		font-size: 0.9rem;
	}
	.sec {
		margin-bottom: 2rem;
	}
	.sec-h {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 0.5rem 1rem;
		flex-wrap: wrap;
		margin-bottom: 0.75rem;
	}
	.sec-h h2 {
		margin: 0;
		font-size: 1.1rem;
		display: flex;
		align-items: baseline;
		gap: 0.6rem;
	}
	.sec-note {
		color: var(--muted);
		font-size: 0.85rem;
	}
	.sec-link {
		font-size: 0.9rem;
		font-weight: 600;
	}

	/* смуга показників: одна рамка, комірки розділені лініями */
	.strip {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		background: var(--surface);
		border: 1px solid var(--card-line);
		border-radius: var(--radius-lg);
		overflow: hidden;
	}
	.strip.three {
		grid-template-columns: repeat(3, minmax(0, 1fr));
	}
	.cell {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		padding: 1rem 1.25rem 1.1rem;
		border-left: 1px solid var(--card-line);
		color: inherit;
		text-decoration: none;
		min-width: 0;
	}
	.cell:first-child {
		border-left: 0;
	}
	.cell.link:hover {
		background: var(--surface-2);
	}
	.l {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		font-size: 0.82rem;
		font-weight: 600;
		color: var(--muted);
	}
	.v {
		font-size: 1.9rem;
		font-weight: 700;
		color: var(--ink);
		line-height: 1.1;
		font-variant-numeric: tabular-nums;
		display: flex;
		align-items: baseline;
		gap: 0.4rem;
		flex-wrap: wrap;
	}
	.v small {
		font-size: 0.85rem;
		font-weight: 500;
		color: var(--muted);
	}
	.v.good {
		color: var(--ok);
	}
	.v.bad {
		color: var(--deficit-ink);
	}
	.d {
		font-size: 0.82rem;
		color: var(--muted);
	}
	.d.down {
		color: var(--ok);
		font-weight: 600;
	}
	.d.up {
		color: var(--bad);
		font-weight: 600;
	}
	.bar {
		display: block;
		height: 6px;
		background: var(--neutral-soft);
		border-radius: var(--r-sm);
		overflow: hidden;
	}
	.bar i {
		display: block;
		height: 100%;
		background: var(--ok);
		border-radius: var(--r-sm);
		transform-origin: left;
	}
	@media (prefers-reduced-motion: no-preference) {
		.bar i {
			animation: grow var(--dur-slow) var(--ease-emph) both;
		}
	}
	@keyframes grow {
		from {
			transform: scaleX(0);
		}
	}

	.panel-x {
		margin-top: 0.75rem;
		background: var(--surface);
		border: 1px solid var(--card-line);
		border-radius: var(--radius-lg);
		padding: 1rem 1.25rem;
	}
	.panel-x h3 {
		margin: 0 0 0.5rem;
		font-size: 0.95rem;
		color: var(--text-2);
	}

	.tbl {
		background: var(--surface);
		border: 1px solid var(--card-line);
		border-radius: var(--radius-lg);
		overflow-x: auto;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.9rem;
	}
	th {
		text-align: left;
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--muted);
		background: var(--surface-2);
		padding: 0.6rem 1rem;
		border-bottom: 1px solid var(--card-line);
		white-space: nowrap;
	}
	td {
		padding: 0.6rem 1rem;
		border-bottom: 1px solid var(--line-soft);
		vertical-align: top;
	}
	tr:last-child td {
		border-bottom: 0;
	}
	tbody tr:hover {
		background: var(--surface-2);
	}
	td a {
		color: var(--ink);
		font-weight: 500;
		text-decoration: none;
	}
	td a:hover {
		color: var(--accent);
		text-decoration: underline;
	}
	.r {
		text-align: right;
	}
	.muted {
		color: var(--muted);
		white-space: nowrap;
	}
	.low {
		color: var(--deficit-ink);
	}
	@media (max-width: 1100px) {
		.strip {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
		.strip .cell:nth-child(3) {
			border-left: 0;
		}
		.strip .cell:nth-child(n + 3) {
			border-top: 1px solid var(--card-line);
		}
		.strip.three {
			grid-template-columns: 1fr;
		}
		.strip.three .cell {
			border-left: 0;
		}
		.strip.three .cell + .cell {
			border-top: 1px solid var(--card-line);
		}
	}
	@media (max-width: 560px) {
		.strip {
			grid-template-columns: 1fr;
		}
		.strip .cell {
			border-left: 0;
		}
		.strip .cell + .cell {
			border-top: 1px solid var(--card-line);
		}
		.muted {
			white-space: normal;
		}
	}
</style>
