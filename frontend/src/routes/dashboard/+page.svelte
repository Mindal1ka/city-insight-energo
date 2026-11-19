<script lang="ts">
	// «Огляд громади»: ефективність міста на одному екрані — 4 головні показники, один графік, три короткі списки дій.
	import { errMessage } from '#lib/api.ts';
	import { fetchSes, uah, kwh, kText, type SesList, type SesItem } from '#lib/api-ses.ts';
	import { fetchDepartments, fetchNetwork, fetchTrend, fetchBudgetReal, type Departments, type Network, type Trend, type BudgetReal } from '#lib/api-v2.ts';
	import { num, MONTHS_FULL } from '#lib/format.ts';
	import SourceTag from '#lib/SourceTag.svelte';
	import { moneyShort } from '#lib/dash/DashData.ts';
	import StatCard from '#lib/StatCard.svelte';
	import Status from '#lib/Status.svelte';
	import DemoPill from '#lib/DemoPill.svelte';
	import CountUp from '#lib/CountUp.svelte';
	import DashMonthly from '#lib/dash/DashMonthly.svelte';

	let ses = $state<SesList | null>(null);
	let dept = $state<Departments | null>(null);
	let net = $state<Network | null>(null);
	let trend = $state<Trend | null>(null);
	let bud = $state<BudgetReal | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);

	async function load() {
		loading = true;
		error = null;
		try {
			// Основні дані обов'язкові; решта (залежить від ролі) — якщо є
			const [s, d, n, tr, br] = await Promise.allSettled([fetchSes('year'), fetchDepartments(), fetchNetwork('year'), fetchTrend(), fetchBudgetReal()]);
			if (s.status === 'rejected') throw s.reason;
			ses = s.value;
			dept = d.status === 'fulfilled' ? d.value : null;
			net = n.status === 'fulfilled' ? n.value : null;
			trend = tr.status === 'fulfilled' ? tr.value : null;
			bud = br.status === 'fulfilled' ? br.value : null;
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

	const surplusKwh = $derived(net?.totals.surplus_kwh ?? null);
	const surplusUah = $derived(net?.totals.surplus_uah ?? null);

	const usedPct = $derived(dept?.totals.used_pct_year ?? null);
	const overLimit = $derived(dept?.totals.over_limit ?? null);
	const limitTone = $derived(overLimit ? 'warn' : 'good');

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
	const needExpand = $derived(
		(ses?.items ?? [])
			.filter((i) => withK(i) && i.k_class === 'Не вистачає')
			.sort((a, b) => (a.k as number) - (b.k as number))
			.slice(0, 5)
	);
	const hasLists = $derived(needExpand.length > 0);
</script>

<svelte:head><title>Огляд · Insight Tool</title></svelte:head>

<header class="page-head">
	<h1>Огляд громади</h1>
	{#if ses?.demo}
		<DemoPill text={ses.mock ? 'Макет: наявність СЕС і K змодельовані на клієнті, доки бекенд не віддає /api/ses.' : 'Дані про СЕС змодельовані (у місті немає реєстру СЕС).'} />
	{/if}
</header>

<Status loading={loading && !ses} {error} retry={load} />

{#if ses}
	<div class="ov">
		<section class="hero" aria-label="Головні показники">
			<div class="card money">
				<div class="m-item">
					<span class="m-label">Вкладено в СЕС</span>
					<span class="m-val"><CountUp value={capexS.v} decimals={capexS.d} /> <small>{capexS.unit}</small></span>
				</div>
				<span class="arrow" aria-hidden="true">→</span>
				<div class="m-item good">
					<span class="m-label">Заощаджує</span>
					<span class="m-val"><CountUp value={savedS.v} decimals={savedS.d} /> <small>{savedS.unit}/рік</small></span>
				</div>
				<span class="arrow" aria-hidden="true">→</span>
				<div class="m-item">
					<span class="m-label">Окупність</span>
					<span class="m-val">{#if payback == null}—{:else}<CountUp value={payback} decimals={1} /> <small>років</small>{/if}</span>
				</div>
			</div>

			<div class="cards">
				<StatCard label="Сонце покриває" value={coverPct} decimals={0} unit="% споживання" icon="sun" tone="good" toneLabel="економія" />
				<StatCard
					label="Не використано надлишку"
					value={surplusKwh == null ? null : surplusKwh / 1000}
					decimals={0}
					unit="тис. кВт·год{surplusUah == null ? '' : ' ≈ ' + uah(surplusUah)}"
					icon="bolt"
					tone={surplusKwh ? 'warn' : 'neutral'}
					href="/network"
				/>
				<StatCard
					label="Ліміти (школи, садки та ін.)"
					value={usedPct}
					decimals={0}
					unit="% використано{overLimit == null ? '' : ' · понад ліміт: ' + overLimit}"
					icon="wallet"
					tone={limitTone}
					href="/finance"
				/>
			</div>
		</section>

		{#if trend || bt}
			<section class="real" aria-label="Реальні дані">
				{#if trend && trend.kwh_2026_est}
					<div class="card rc">
						<div class="rc-h"><span>Споживання 2026</span><SourceTag kind="umuni" /></div>
						<div class="rc-v"><b>{mln(trend.kwh_2026_est)}</b> млн кВт·год
							{#if trendPct != null}<span class="tr" class:down={trendPct < 0} class:up={trendPct > 0}>{trendPct > 0 ? '+' : ''}{num(trendPct, 1)}% до 2025</span>{/if}
						</div>
						<p class="rc-n">оцінка з даних UMUNI до {trend.to_date ? new Date(trend.to_date).toLocaleDateString('uk-UA') : '—'} · ↑ {trend.growing} · ↓ {trend.falling} об’єктів</p>
					</div>
				{/if}
				{#if bt}
					<a class="card rc" href="/finance">
						<div class="rc-h"><span>Бюджет на е/е 2026</span><SourceTag kind="openbudget" /></div>
						<div class="rc-v"><b>{mln(bt.fact_2026)}</b> з {mln(bt.plan_2026)} млн грн сплачено{budMonth ? ` (${MONTHS_FULL[budMonth - 1].toLowerCase()})` : ''}</div>
						<span class="pb"><i style="width:{budPct}%"></i></span>
						{#if bt.price_2025}<p class="rc-n">фактична ціна 2025: <b>{num(bt.price_2025, 2)} грн/кВт·год</b></p>{/if}
					</a>
				{/if}
			</section>
		{/if}

		{#if monthly}
			<section class="card" aria-labelledby="h-mon">
				<h2 id="h-mon">Громада помісячно</h2>
				<DashMonthly months={monthly} />
			</section>
		{/if}

		{#if hasLists}
			<div class="lists">
				{#snippet list(title: string, rows: { href: string; name: string; num: string }[])}
					<section class="card lst" aria-label={title}>
						<h2>{title}</h2>
						{#if rows.length}
							<ul>
								{#each rows as r (r.href + r.name)}
									<li>
										<a href={r.href}><span class="nm">{r.name}</span><b>{r.num}</b></a>
									</li>
								{/each}
							</ul>
						{:else}
							<p class="empty">—</p>
						{/if}
					</section>
				{/snippet}
				{@render list(
					'Потрібне розширення',
					needExpand.map((i) => ({ href: `/object/${i.id}`, name: i.name, num: 'сонце дає ' + kText(i.k) }))
				)}
			</div>
		{/if}
	</div>
{/if}

<style>
	.page-head {
		display: flex;
		align-items: center;
		gap: 0.8rem;
		flex-wrap: wrap;
		margin-bottom: 1.5rem;
	}
	.page-head h1 {
		margin: 0;
	}
	.ov {
		display: grid;
		gap: 1.5rem;
	}
	.hero {
		display: grid;
		gap: 1rem;
	}
	.cards {
		--fs-stat: 2rem;
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 14rem), 1fr));
		gap: 1rem;
	}
	.real {
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 18rem), 1fr));
	}
	.rc {
		display: grid;
		gap: 0.35rem;
		margin: 0;
		min-width: 0;
		align-content: start;
	}
	.rl {
		font-weight: 600;
		color: var(--muted);
	}
	.rv {
		font-family: var(--font-display);
		font-size: 2rem;
		font-weight: 700;
		color: var(--ink);
		line-height: 1.1;
	}
	.rv small {
		font-family: inherit;
		font-size: 0.95rem;
		color: var(--muted);
	}
	.rs {
		font-weight: 700;
		color: var(--text-2);
	}
	.rs.up {
		color: var(--warn);
	}
	.rs.down {
		color: var(--ok);
	}
	.rn {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.3rem 0.5rem;
		font-size: 0.8rem;
		color: var(--muted);
	}
	.pbar {
		height: 0.55rem;
		border-radius: 999px;
		background: var(--neutral-soft);
		overflow: hidden;
	}
	.pbar i {
		display: block;
		height: 100%;
		background: var(--ok);
	}
	.money {
		display: flex;
		align-items: center;
		justify-content: space-around;
		flex-wrap: wrap;
		gap: 1rem 1.5rem;
		margin: 0;
		padding: 1.5rem;
	}
	.m-item {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		min-width: 0;
	}
	.m-label {
		font-size: 0.95rem;
		font-weight: 600;
		color: var(--muted);
	}
	.m-val {
		font-family: var(--font-display);
		font-size: clamp(1.8rem, 4vw, 2.6rem);
		font-weight: 700;
		color: var(--ink);
		font-variant-numeric: tabular-nums;
		line-height: 1.1;
	}
	.m-val small {
		font-family: inherit;
		font-size: 0.95rem;
		font-weight: 600;
		color: var(--muted);
	}
	.m-item.good .m-val {
		color: var(--ok);
	}
	.arrow {
		font-size: 1.6rem;
		color: var(--line-strong);
	}
	.ov > .card,
	.lists > .card {
		margin: 0;
		min-width: 0;
	}
	h2 {
		margin: 0 0 0.9rem;
		font-size: 1.1rem;
	}
	.lists {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 22rem), 1fr));
		gap: 1rem;
	}
	.lst {
		min-width: 0;
	}
	.lst ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: 0.15rem;
	}
	.lst a {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.8rem;
		padding: 0.55rem 0.5rem;
		border-radius: 10px;
		color: var(--text);
		text-decoration: none;
		transition: background var(--dur-fast);
	}
	.lst a:hover {
		background: var(--neutral-soft);
	}
	.nm {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-weight: 600;
		font-size: 0.92rem;
	}
	.lst b {
		flex: none;
		font-variant-numeric: tabular-nums;
		color: var(--text-2);
		font-size: 0.92rem;
	}
	.empty {
		margin: 0;
		color: var(--muted);
	}
	@media (max-width: 1000px) {
		.lists {
			grid-template-columns: 1fr;
		}
	}
	@media (max-width: 600px) {
		.arrow {
			display: none;
		}
		.money {
			flex-direction: column;
			align-items: flex-start;
		}
	}
	.real {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 1rem;
	}
	.rc {
		display: grid;
		gap: 0.45rem;
		color: var(--text);
		text-decoration: none;
	}
	.rc-h {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		color: var(--text-2);
		font-weight: 600;
	}
	.rc-v {
		font-size: 0.95rem;
		color: var(--text-2);
	}
	.rc-v b {
		font-size: 1.9rem;
		color: var(--text);
		font-variant-numeric: tabular-nums;
	}
	.tr {
		margin-left: 0.5rem;
		font-weight: 700;
		font-size: 0.9rem;
	}
	.tr.down {
		color: var(--ok, #1f8a4c);
	}
	.tr.up {
		color: #d9680f;
	}
	.rc-n {
		margin: 0;
		font-size: 0.82rem;
		color: var(--muted);
	}
	.pb {
		display: block;
		height: 8px;
		border-radius: 99px;
		background: var(--neutral-soft, #eef0f3);
		overflow: hidden;
	}
	.pb i {
		display: block;
		height: 100%;
		background: #1f8a4c;
	}
	@media (max-width: 700px) {
		.real {
			grid-template-columns: 1fr;
		}
	}
</style>
