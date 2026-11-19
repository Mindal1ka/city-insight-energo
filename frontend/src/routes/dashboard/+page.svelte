<script lang="ts">
	// «Дашборд ефективності СЕС»: фільтри (в адресі) → KPI → графіки → топ-списки → повна таблиця.
	// Публічний режим: лише зведені цифри громади й графіки без по-об'єктних даних СЕС.
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { flip } from 'svelte/animate';
	import { errMessage } from '#lib/api.ts';
	import { catLabel, CATEGORY_ORDER } from '#lib/categories.ts';
	import { auth } from '#lib/auth.svelte.ts';
	import { isInternal } from '#lib/roles.ts';
	import { fadeUp, stagger, DUR, isReduced } from '#lib/motion.ts';
	import StatCard from '#lib/StatCard.svelte';
	import Status from '#lib/Status.svelte';
	import DemoPill from '#lib/DemoPill.svelte';
	import Term from '#lib/Term.svelte';
	import Icon from '#lib/Icon.svelte';
	import KBadge from '#lib/KBadge.svelte';
	import Disclosure from '#lib/Disclosure.svelte';
	import {
		loadSes,
		sumTotals,
		histogram,
		kOf,
		toCsv,
		download,
		moneyShort,
		kText,
		PERIODS,
		CLASSES,
		CLASS_BY_SLUG,
		type Period,
		type SesItem,
		type SesList,
		type KClass,
		type TypeRow
	} from '#lib/dash/DashData.ts';
	import DashHistogram from '#lib/dash/DashHistogram.svelte';
	import DashDonut from '#lib/dash/DashDonut.svelte';
	import DashByType from '#lib/dash/DashByType.svelte';
	import DashScatter from '#lib/dash/DashScatter.svelte';
	import DashMonthly from '#lib/dash/DashMonthly.svelte';

	// ---------- Фільтри з адреси ----------
	const sp = $derived(page.url.searchParams);
	const period = $derived<Period>((['day', 'month', 'year'] as const).find((p) => p === sp.get('p')) ?? 'year');
	const cls = $derived((sp.get('c') ?? '').split(',').filter((s) => CLASS_BY_SLUG[s]));
	const type = $derived(sp.get('t') ?? '');
	/** Літній день для день/місяць (взимку все «Не вистачає»): ?d=2026-06-15 */
	const SUMMER = '2026-06-15';
	const day = $derived(/^\d{4}-\d{2}-\d{2}$/.test(sp.get('d') ?? '') ? (sp.get('d') as string) : '');
	const qUrl = $derived(sp.get('q') ?? '');
	let q = $state(page.url.searchParams.get('q') ?? '');

	function setParams(patch: Record<string, string>) {
		const u = new URL(page.url.href);
		for (const [k, v] of Object.entries(patch)) {
			if (v) u.searchParams.set(k, v);
			else u.searchParams.delete(k);
		}
		goto(u.pathname + u.search, { replace: true, reset: false });
	}
	const setPeriod = (p: Period) => setParams({ p: p === 'year' ? '' : p });
	function toggleCls(slug: string) {
		const s = new Set(cls);
		if (s.has(slug)) s.delete(slug);
		else s.add(slug);
		setParams({ c: CLASSES.filter((c) => s.has(c.slug)).map((c) => c.slug).join(',') });
	}
	const setType = (t: string) => setParams({ t });
	let qTimer: ReturnType<typeof setTimeout> | undefined;
	function onSearch() {
		clearTimeout(qTimer);
		qTimer = setTimeout(() => setParams({ q: q.trim() }), 250);
	}
	function resetAll() {
		q = '';
		setParams({ c: '', t: '', q: '' });
	}
	const anyFilter = $derived(cls.length > 0 || !!type || !!qUrl);

	// ---------- Дані ----------
	let data = $state<SesList | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);
	let seq = 0;
	async function load(p: Period, dd = day) {
		const my = ++seq;
		loading = true;
		error = null;
		try {
			const d = await loadSes(p, p === 'year' ? undefined : dd || undefined);
			if (my === seq) data = d;
		} catch (e) {
			if (my === seq) error = errMessage(e);
		} finally {
			if (my === seq) loading = false;
		}
	}
	$effect(() => {
		load(period, day);
	});

	const user = $derived(auth.user);
	const restricted = $derived(!isInternal(user) || !!data?.restricted);
	const isFinance = $derived(user?.role === 'finance');
	const T = $derived(data?.thresholds ?? { low: 0.8, high: 1.2 });
	const all = $derived(data?.items ?? []);

	const norm = (s: string) => s.toLocaleLowerCase('uk').replace(/[’ʼ`´']/g, '');
	const nq = $derived(norm(qUrl.trim()));
	const byText = (i: SesItem) => !nq || norm(`${i.name} ${i.address ?? ''} ${i.id}`).includes(nq);
	const byType = (i: SesItem) => !type || i.category_short === type;
	const byCls = (i: SesItem) => !cls.length || cls.includes(CLASSES.find((c) => c.id === kOf(i))!.slug);

	/** Без фільтра класу — для лічильників на чипах класів */
	const preCls = $derived(all.filter((i) => byType(i) && byText(i)));
	const items = $derived(preCls.filter(byCls));
	const tot = $derived(sumTotals(items));

	const clsCounts = $derived.by(() => {
		const out = Object.fromEntries(CLASSES.map((c) => [c.id, 0])) as Record<KClass, number>;
		if (restricted && data) {
			const t = data.totals;
			out['Ефективно'] = t.effective ?? 0;
			out['Не вистачає'] = t.deficit ?? 0;
			out['Надлишок'] = t.surplus ?? 0;
			out['Без СЕС'] = t.no_ses ?? 0;
			out['Немає даних'] = t.no_data ?? 0;
			return out;
		}
		for (const i of preCls) out[kOf(i)]++;
		return out;
	});
	const donutCounts = $derived.by(() => {
		if (restricted) return clsCounts;
		const out = Object.fromEntries(CLASSES.map((c) => [c.id, 0])) as Record<KClass, number>;
		for (const i of items) out[kOf(i)]++;
		return out;
	});

	const typeCounts = $derived.by(() => {
		const m = new Map<string, number>();
		for (const i of all) if (byText(i) && byCls(i)) m.set(i.category_short, (m.get(i.category_short) ?? 0) + 1);
		return m;
	});
	const typeKeys = $derived(
		[...new Set(all.map((i) => i.category_short).filter(Boolean))].sort(
			(a, b) => (CATEGORY_ORDER.indexOf(a) + 1 || 99) - (CATEGORY_ORDER.indexOf(b) + 1 || 99)
		)
	);

	// ---------- KPI ----------
	const kpi = $derived.by(() => {
		const t = data?.totals;
		if (restricted || !anyFilter) {
			// публічно або без фільтрів — офіційні підсумки бекенду
			const withSes = t?.with_ses ?? tot.with_ses;
			const eff = t?.effective ?? tot.effective;
			const capex = t?.capex_uah ?? tot.capex_uah;
			const saved = t?.saved_uah_year ?? tot.saved_uah_year;
			return {
				withSes,
				k: t?.k ?? tot.k,
				effPct: withSes ? (eff / withSes) * 100 : null,
				capex,
				saved,
				grid: t?.grid_cost_uah_year ?? null,
				payback: capex && saved ? capex / saved : null
			};
		}
		const allCons = all.reduce((s, i) => s + (i.cons_kwh ?? 0), 0);
		const fCons = items.reduce((s, i) => s + (i.cons_kwh ?? 0), 0);
		const grid =
			tot.grid_cost_uah_year > 0
				? tot.grid_cost_uah_year
				: t?.grid_cost_uah_year && allCons
					? (t.grid_cost_uah_year * fCons) / allCons
					: null;
		const paid = items.filter((i) => i.has_ses && (i.saved_uah_year ?? 0) > 0 && (i.capex_uah ?? 0) > 0);
		const pc = paid.reduce((s, i) => s + (i.capex_uah ?? 0), 0);
		const ps = paid.reduce((s, i) => s + (i.saved_uah_year ?? 0), 0);
		return {
			withSes: tot.with_ses,
			k: tot.k,
			effPct: tot.with_ses ? (tot.effective / tot.with_ses) * 100 : null,
			capex: tot.capex_uah,
			saved: tot.saved_uah_year,
			grid,
			payback: ps ? pc / ps : null
		};
	});
	const capexS = $derived(moneyShort(kpi.capex ?? 0));
	const savedS = $derived(moneyShort(kpi.saved ?? 0));
	const gridS = $derived(moneyShort(kpi.grid ?? 0));
	const kTone = $derived(kpi.k == null ? 'neutral' : kpi.k < T.low ? 'warn' : kpi.k > T.high ? 'neutral' : 'good');

	// ---------- Графіки ----------
	const bins = $derived(histogram(items.filter((i) => i.has_ses)));
	const hasHist = $derived(bins.some((b) => b.n > 0));
	const typeRows = $derived.by<TypeRow[]>(() => {
		const src = all.filter((i) => byText(i) && byCls(i));
		return typeKeys.map((key) => {
			const xs = src.filter((i) => i.category_short === key);
			let g = 0,
				c = 0,
				ws = 0;
			for (const i of xs) {
				if (i.has_ses) ws++;
				if (i.has_ses && i.k != null && i.gen_kwh != null && i.cons_kwh) {
					g += i.gen_kwh;
					c += i.cons_kwh;
				}
			}
			return { key, label: catLabel(key), count: xs.length, withSes: ws, k: c > 0 ? g / c : null };
		});
	});
	const monthly = $derived(data?.monthly && data.monthly.length === 12 ? data.monthly : null);
	const consUnit = $derived(period === 'year' ? 'кВт·год/рік' : period === 'month' ? 'кВт·год/міс' : 'кВт·год/добу');

	// ---------- Топи ----------
	const withK = $derived(items.filter((i) => i.has_ses && i.k != null && Number.isFinite(i.k)));
	const topSurplus = $derived([...withK].sort((a, b) => (b.k as number) - (a.k as number)).slice(0, 5));
	const topDeficit = $derived([...withK].sort((a, b) => (a.k as number) - (b.k as number)).slice(0, 5));
	const topPayback = $derived(
		items
			.filter((i) => i.has_ses && (i.payback_years ?? 0) > 0)
			.sort((a, b) => (a.payback_years as number) - (b.payback_years as number))
			.slice(0, 5)
	);
	const openObj = (id: number) => goto(`/object/${id}`);

	// ---------- Таблиця ----------
	type ColKey = 'name' | 'type' | 'class' | 'k' | 'cons_kwh' | 'gen_kwh' | 'ses_kw' | 'battery_kwh' | 'capex_uah' | 'saved_uah_year' | 'payback_years';
	const COLS = $derived(
		(
			[
				{ key: 'name', label: "Об'єкт" },
				{ key: 'type', label: 'Тип' },
				{ key: 'class', label: 'Клас' },
				{ key: 'k', label: 'K', num: true },
				{ key: 'cons_kwh', label: 'Спожито, кВт·год', num: true },
				{ key: 'gen_kwh', label: 'Згенеровано, кВт·год', num: true },
				{ key: 'ses_kw', label: 'СЕС, кВт', num: true },
				{ key: 'battery_kwh', label: 'Акум., кВт·год', num: true },
				{ key: 'capex_uah', label: 'Вкладено, грн', num: true },
				{ key: 'saved_uah_year', label: 'Заощаджено, грн/рік', num: true },
				{ key: 'payback_years', label: 'Окупність, р.', num: true }
			] as { key: ColKey; label: string; num?: boolean }[]
		).filter((c) => !(isFinance && c.key === 'battery_kwh'))
	);
	let sortKey = $state<ColKey>('k');
	let sortDir = $state<1 | -1>(-1);
	let tableOpen = $state(false);
	function sortBy(k: ColKey) {
		if (sortKey === k) sortDir = sortDir === 1 ? -1 : 1;
		else {
			sortKey = k;
			sortDir = k === 'name' || k === 'type' ? 1 : -1;
		}
	}
	const val = (i: SesItem, k: ColKey): string | number | null =>
		k === 'name' ? i.name : k === 'type' ? catLabel(i.category_short) : k === 'class' ? CLASSES.findIndex((c) => c.id === kOf(i)) : (i[k] as number | null);
	const sorted = $derived(
		[...items].sort((a, b) => {
			const x = val(a, sortKey),
				y = val(b, sortKey);
			if (x == null && y == null) return 0;
			if (x == null) return 1;
			if (y == null) return -1;
			return (typeof x === 'string' ? x.localeCompare(y as string, 'uk') : x - (y as number)) * sortDir;
		})
	);
	const nf = (v: number | null | undefined, d = 0) =>
		v == null || !Number.isFinite(v) ? '—' : v.toLocaleString('uk-UA', { maximumFractionDigits: d, minimumFractionDigits: d });

	function exportCsv() {
		const cols = COLS.map((c) => ({ key: (c.key === 'class' ? 'class' : c.key === 'type' ? 'type' : c.key) as keyof SesItem | 'class' | 'type', label: c.label }));
		download(`ses-dashboard-${period}-${new Date().toISOString().slice(0, 10)}.csv`, toCsv(sorted, cols, catLabel));
	}

	// Анімація «рядків» при першій появі
	let shown = $state(false);
	$effect(() => {
		if (data && !shown) shown = true;
	});
</script>

<svelte:head><title>Дашборд ефективності СЕС · Insight Tool</title></svelte:head>

<header class="page-head dh-head">
	<div>
		<h1>Дашборд ефективності <Term key="СЕС" plain>СЕС</Term></h1>
	</div>
	<div class="head-side">
		{#if restricted}
			<a class="lock-chip" href="/login?next={encodeURIComponent(page.url.pathname + page.url.search)}">
				<Icon name="lock" size={15} /> Детально — після входу
			</a>
		{/if}
		{#if data?.demo}
			<DemoPill text={data.mock ? 'Макет: наявність СЕС і K змодельовані на клієнті, доки бекенд не віддає /api/ses.' : 'Дані про СЕС змодельовані (у місті немає реєстру СЕС).'} />
		{/if}
	</div>
</header>

<!-- ---------- Панель фільтрів ---------- -->
<div class="fbar" role="search" aria-label="Фільтри дашборду">
	<div class="seg" role="radiogroup" aria-label="Період">
		{#each PERIODS as p (p.id)}
			<button type="button" role="radio" aria-checked={period === p.id} class:on={period === p.id} onclick={() => setPeriod(p.id)}>{p.label}</button>
		{/each}
	</div>
	{#if period !== 'year'}
		<button type="button" class="chip summer" aria-pressed={!!day} onclick={() => setParams({ d: day ? '' : SUMMER })} title="15 червня">
			<Icon name="sun" size={15} /> Літо
		</button>
	{/if}

	{#if !restricted}
		<div class="chips" role="group" aria-label="Клас">
			{#each CLASSES as c (c.id)}
				<button
					type="button"
					class="chip kc"
					aria-pressed={cls.includes(c.slug)}
					style="--kc:{c.color};--ks:{c.soft};--ki:{c.ink}"
					onclick={() => toggleCls(c.slug)}
				>
					<span class="ksym" aria-hidden="true">{c.sym}</span>{c.short}<span class="kn">{clsCounts[c.id]}</span>
				</button>
			{/each}
		</div>
	{/if}

	<div class="row2">
		<label class="sel">
			<span class="visually-hidden">Тип закладу</span>
			<Icon name="building" size={16} />
			<select value={type} onchange={(e) => setType(e.currentTarget.value)}>
				<option value="">Усі типи</option>
				{#each typeKeys as t (t)}
					<option value={t}>{catLabel(t)} ({typeCounts.get(t) ?? 0})</option>
				{/each}
			</select>
		</label>
		{#if !restricted}
			<label class="search">
				<span class="visually-hidden">Пошук об'єкта</span>
				<Icon name="search" size={16} />
				<input type="search" placeholder="Пошук" bind:value={q} oninput={onSearch} />
			</label>
		{/if}
		{#if anyFilter}
			<button type="button" class="reset" onclick={resetAll}>✕ Скинути</button>
		{/if}
		<span class="found" aria-live="polite"><b>{restricted ? (data?.totals.objects ?? 0) : items.length}</b> об'єктів</span>
	</div>
</div>

<Status loading={loading && !data} {error} retry={() => load(period)} />

{#if data}
	<div class="dash" class:stale={loading}>
		<!-- ---------- KPI ---------- -->
		<div class="kpis" aria-label="Ключові показники">
			<StatCard label="Об'єктів з СЕС" value={kpi.withSes} icon="sun" />
			<StatCard label="Середній K" value={kpi.k} decimals={2} icon="gauge" tone={kTone} />
			<StatCard label="Ефективних" value={kpi.effPct} unit="%" icon="check" />
			<StatCard label="Вкладено в СЕС" value={capexS.v} decimals={capexS.d} unit={capexS.unit} icon="wallet" />
			<StatCard label="Заощаджено" value={savedS.v} decimals={savedS.d} unit="{savedS.unit}/рік" icon="chart" tone="good" toneLabel="економія" />
			<StatCard label="Витрачено на мережу" value={kpi.grid == null ? null : gridS.v} decimals={gridS.d} unit="{gridS.unit}/рік" icon="plug" />
			<StatCard label="Середня окупність" value={kpi.payback} decimals={1} unit="років" icon="clock" />
		</div>

		<!-- ---------- Графіки ---------- -->
		<div class="charts">
			<section class="card ch" aria-labelledby="h-cls">
				<h2 id="h-cls">Класи <Term key="K" plain>K</Term></h2>
				<DashDonut counts={donutCounts} selected={restricted ? [] : cls} ontoggle={restricted ? undefined : toggleCls} center="об'єктів" />
			</section>

			{#if hasHist}
				<section class="card ch" aria-labelledby="h-hist">
					<h2 id="h-hist">Розподіл <Term key="K" plain>K</Term> <span class="u">об'єкти з СЕС</span></h2>
					<DashHistogram {bins} low={T.low} high={T.high} />
				</section>
			{/if}

			<section class="card ch ch-type" aria-labelledby="h-type">
				<h2 id="h-type">За типом закладу <span class="u">{restricted ? "к-сть об'єктів" : 'середній K · к-сть'}</span></h2>
				<DashByType rows={typeRows} low={T.low} high={T.high} showK={!restricted} active={type} onpick={setType} />
			</section>

			{#if monthly}
				<section class="card ch" aria-labelledby="h-mon">
					<h2 id="h-mon">Громада помісячно</h2>
					<DashMonthly months={monthly} />
				</section>
			{/if}

			{#if !restricted}
				<section class="card ch wide" aria-labelledby="h-sc">
					<h2 id="h-sc"><Term key="K" plain>K</Term> × споживання <span class="u">{consUnit}</span></h2>
					<DashScatter items={items.filter((i) => i.has_ses)} low={T.low} high={T.high} unit="кВт·год" onopen={openObj} />
				</section>
			{/if}
		</div>

		{#if !restricted}
			<!-- ---------- Топ-списки ---------- -->
			<div class="tops">
				{#snippet top(title: string, icon: 'sun' | 'alert' | 'clock', rows: SesItem[], mode: 'k' | 'pb')}
					<section class="card top" aria-label={title}>
						<h2><span class="ti" aria-hidden="true"><Icon name={icon} size={17} /></span>{title}</h2>
						{#if rows.length}
							<ol>
								{#each rows as r, i (r.id)}
									<li animate:flip={{ duration: isReduced() ? 0 : DUR.base }} in:fadeUp={{ delay: shown ? 0 : stagger(i) }}>
										<a href="/object/{r.id}">
											<span class="rk">{i + 1}</span>
											<span class="nm"><span class="n1">{r.name}</span><span class="n2">{catLabel(r.category_short)}</span></span>
											{#if mode === 'k'}
												<KBadge k={r.k} cls={kOf(r)} size="sm" showWord={false} />
											{:else}
												<span class="pb"><b>{nf(r.payback_years, 1)}</b> р.</span>
											{/if}
										</a>
									</li>
								{/each}
							</ol>
						{:else}
							<p class="empty">—</p>
						{/if}
					</section>
				{/snippet}
				{@render top('Найбільший надлишок', 'sun', topSurplus, 'k')}
				{@render top('Найбільше не вистачає', 'alert', topDeficit, 'k')}
				{@render top('Найшвидша окупність', 'clock', topPayback, 'pb')}
			</div>

			<!-- ---------- Таблиця ---------- -->
			<section class="card tbl-card" aria-labelledby="h-tbl">
				<div class="tbl-head">
					<h2 id="h-tbl">Усі об'єкти <span class="u">{items.length}</span></h2>
					<button type="button" class="btn-csv" onclick={exportCsv} disabled={!items.length}>
						<Icon name="arrow-right" size={15} /> CSV
					</button>
				</div>
				<Disclosure summary={tableOpen ? 'Згорнути' : 'Показати таблицю'} bind:open={tableOpen} hint="{items.length} рядків">
					<div class="scroll-x tbl-wrap">
						<table class="dtbl">
							<thead>
								<tr>
									{#each COLS as c (c.key)}
										<th class:num={c.num} aria-sort={sortKey === c.key ? (sortDir === 1 ? 'ascending' : 'descending') : 'none'}>
											<button type="button" onclick={() => sortBy(c.key)}>
												{c.label}<span class="sa" aria-hidden="true">{sortKey === c.key ? (sortDir === 1 ? '▲' : '▼') : ''}</span>
											</button>
										</th>
									{/each}
								</tr>
							</thead>
							<tbody>
								{#each sorted as r (r.id)}
									<tr>
										{#each COLS as c (c.key)}
											{#if c.key === 'name'}
												<td class="tn"><a href="/object/{r.id}" title={r.name}>{r.name}</a></td>
											{:else if c.key === 'type'}
												<td>{catLabel(r.category_short)}</td>
											{:else if c.key === 'class'}
												<td><KBadge cls={kOf(r)} size="sm" showK={false} /></td>
											{:else if c.key === 'k'}
												<td class="num"><b>{kText(r.k)}</b></td>
											{:else if c.key === 'payback_years' || c.key === 'ses_kw'}
												<td class="num">{nf(r[c.key], 1)}</td>
											{:else}
												<td class="num">{nf(r[c.key] as number | null)}</td>
											{/if}
										{/each}
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</Disclosure>
			</section>
		{/if}
	</div>
{/if}

<style>
	.dh-head {
		margin-bottom: 1rem;
	}
	.dh-head h1 {
		margin: 0;
	}
	.head-side {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		flex-wrap: wrap;
	}
	.lock-chip {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.35rem 0.8rem;
		border-radius: 999px;
		border: 1px dashed var(--line-strong);
		background: var(--surface);
		color: var(--text-2);
		font-weight: 600;
		font-size: 0.875rem;
		text-decoration: none;
		transition:
			border-color var(--dur-fast),
			background var(--dur-fast);
	}
	.lock-chip:hover {
		border-color: var(--navy);
		background: var(--sun-soft);
		color: var(--navy);
	}

	/* ---------- Панель фільтрів ---------- */
	.fbar {
		position: sticky;
		top: 0;
		z-index: 20;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.6rem 0.9rem;
		margin: 0 calc(-1 * var(--gutter, 1rem)) 1.25rem;
		padding: 0.7rem var(--gutter, 1rem);
		background: color-mix(in srgb, var(--bg) 88%, transparent);
		backdrop-filter: blur(10px);
		-webkit-backdrop-filter: blur(10px);
		border-bottom: 1px solid var(--line-soft);
	}
	.seg {
		display: inline-flex;
		padding: 3px;
		border-radius: 999px;
		background: var(--surface);
		border: 1px solid var(--line);
	}
	.seg button {
		min-height: 32px;
		padding: 0.2rem 0.9rem;
		border: 0;
		border-radius: 999px;
		background: none;
		font: inherit;
		font-size: 0.9rem;
		font-weight: 600;
		color: var(--text-2);
		cursor: pointer;
		transition:
			background var(--dur-base) var(--ease-out),
			color var(--dur-fast);
	}
	.seg button.on {
		background: var(--navy);
		color: #fff;
	}
	.summer[aria-pressed='true'] {
		background: var(--sun-soft);
		border-color: var(--sun-strong);
		color: var(--sun-ink);
	}
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}
	.kc {
		min-height: 34px;
		padding: 0.2rem 0.6rem 0.2rem 0.3rem;
	}
	.kc .ksym {
		display: grid;
		place-items: center;
		width: 1.45rem;
		height: 1.45rem;
		border-radius: 50%;
		background: var(--ks);
		color: var(--ki);
		border: 1.5px solid var(--kc);
		font-weight: 800;
		font-size: 0.8rem;
	}
	.kc .kn {
		font-variant-numeric: tabular-nums;
		color: var(--muted);
		font-weight: 700;
	}
	.kc[aria-pressed='true'] {
		background: var(--ks);
		border-color: var(--kc);
		color: var(--ki);
		box-shadow: inset 0 0 0 1px var(--kc);
	}
	.kc[aria-pressed='true'] .kn {
		color: var(--ki);
	}
	.row2 {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
		flex: 1 1 22rem;
	}
	.sel,
	.search {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		min-height: 36px;
		padding: 0 0.7rem;
		border-radius: 999px;
		border: 1px solid var(--line);
		background: var(--surface);
		color: var(--muted);
	}
	.sel:focus-within,
	.search:focus-within {
		border-color: var(--accent);
		box-shadow: 0 0 0 3px var(--accent-soft);
	}
	.sel select,
	.search input {
		border: 0;
		background: none;
		font: inherit;
		font-size: 0.9rem;
		color: var(--text);
		outline: none;
		min-height: 34px;
	}
	.sel select {
		font-weight: 600;
		cursor: pointer;
		max-width: 13rem;
	}
	.search {
		flex: 1 1 9rem;
		max-width: 16rem;
	}
	.search input {
		width: 100%;
		min-width: 0;
	}
	.reset {
		border: 0;
		background: none;
		font: inherit;
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--accent);
		cursor: pointer;
		padding: 0.3rem 0.4rem;
		border-radius: 6px;
	}
	.reset:hover {
		background: var(--accent-soft);
	}
	.found {
		margin-left: auto;
		color: var(--muted);
		font-size: 0.875rem;
		white-space: nowrap;
	}
	.found b {
		color: var(--ink);
		font-variant-numeric: tabular-nums;
	}

	/* ---------- Сітки ---------- */
	.dash {
		transition: opacity var(--dur-base);
	}
	.dash.stale {
		opacity: 0.6;
	}
	.kpis {
		--fs-stat: 1.85rem;
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 10rem), 1fr));
		gap: 0.75rem;
		margin-bottom: 1.25rem;
	}
	.charts {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 1.1rem;
		margin-bottom: 1.1rem;
	}
	.charts > .card {
		margin: 0;
		min-width: 0;
	}
	.ch.wide {
		grid-column: 1 / -1;
	}
	.ch h2,
	.top h2,
	.tbl-head h2 {
		display: flex;
		align-items: baseline;
		flex-wrap: wrap;
		gap: 0.3rem 0.5rem;
		margin: 0 0 0.85rem;
		font-size: 1.08rem;
	}
	.u {
		font-size: 0.8rem;
		font-weight: 600;
		color: var(--muted);
	}
	@media (min-width: 901px) and (max-width: 1499px) {
		.ch-type {
			grid-column: 1 / -1;
		}
	}
	@media (min-width: 1500px) {
		.charts {
			grid-template-columns: repeat(3, minmax(0, 1fr));
		}
		.ch.wide {
			grid-column: 1 / -1;
		}
	}

	/* ---------- Топи ---------- */
	.tops {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 1.1rem;
		margin-bottom: 1.1rem;
	}
	.tops > .card {
		margin: 0;
		min-width: 0;
	}
	.ti {
		display: inline-grid;
		place-items: center;
		width: 1.75rem;
		height: 1.75rem;
		border-radius: 8px;
		background: var(--accent-soft);
		color: var(--accent);
		align-self: center;
	}
	.top ol {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.15rem;
	}
	.top a {
		display: grid;
		grid-template-columns: 1.5rem minmax(0, 1fr) auto;
		align-items: center;
		gap: 0.6rem;
		padding: 0.45rem 0.5rem;
		border-radius: 10px;
		color: var(--text);
		text-decoration: none;
		transition:
			background var(--dur-fast),
			transform var(--dur-base) var(--ease-out);
	}
	.top a:hover {
		background: var(--neutral-soft);
		transform: translateX(2px);
	}
	.rk {
		display: grid;
		place-items: center;
		width: 1.5rem;
		height: 1.5rem;
		border-radius: 50%;
		background: var(--neutral-soft);
		font-size: 0.78rem;
		font-weight: 800;
		color: var(--text-2);
	}
	.nm {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}
	.n1 {
		font-weight: 600;
		font-size: 0.9rem;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.n2 {
		font-size: 0.78rem;
		color: var(--muted);
	}
	.pb {
		font-variant-numeric: tabular-nums;
		color: var(--muted);
		font-size: 0.85rem;
		white-space: nowrap;
	}
	.pb b {
		color: var(--ok);
		font-size: 1rem;
	}
	.empty {
		color: var(--muted);
		margin: 0;
	}

	/* ---------- Таблиця ---------- */
	.tbl-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
	}
	.tbl-head h2 {
		margin: 0;
	}
	.btn-csv {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		min-height: 36px;
		padding: 0.3rem 0.9rem;
		border-radius: 999px;
		border: 1px solid var(--line);
		background: var(--surface);
		font: inherit;
		font-size: 0.875rem;
		font-weight: 700;
		color: var(--accent);
		cursor: pointer;
	}
	.btn-csv :global(svg) {
		transform: rotate(90deg);
	}
	.btn-csv:hover {
		border-color: var(--accent);
		background: var(--accent-soft);
	}
	.tbl-wrap {
		max-height: 70vh;
		overflow: auto;
		margin-top: 0.5rem;
		border: 1px solid var(--line-soft);
		border-radius: 10px;
	}
	.dtbl {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.875rem;
	}
	.dtbl th {
		padding: 0;
		text-align: left;
	}
	.dtbl th button {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		width: 100%;
		padding: 0.55rem 0.6rem;
		border: 0;
		background: none;
		font: inherit;
		font-weight: 700;
		color: inherit;
		cursor: pointer;
		white-space: nowrap;
		text-align: inherit;
	}
	.dtbl th.num button {
		justify-content: flex-end;
	}
	.sa {
		font-size: 0.65rem;
		width: 0.7rem;
	}
	.dtbl td {
		padding: 0.45rem 0.6rem;
		border-top: 1px solid var(--line-soft);
		white-space: nowrap;
	}
	.dtbl td.num {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}
	.dtbl .tn {
		white-space: normal;
		min-width: 16rem;
		max-width: 24rem;
	}
	.dtbl .tn a {
		display: -webkit-box;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		overflow: hidden;
		font-weight: 600;
		color: var(--text);
	}
	.dtbl .tn a:hover {
		color: var(--accent);
	}

	@media (max-width: 1100px) {
		.tops {
			grid-template-columns: 1fr;
		}
	}
	@media (max-width: 900px) {
		.charts {
			grid-template-columns: 1fr;
		}
	}
	@media (max-width: 768px) {
		.fbar {
			top: calc(var(--header-h) + var(--safe-t, 0px));
			gap: 0.5rem;
			padding-top: 0.55rem;
			padding-bottom: 0.55rem;
		}
		.chips {
			flex-wrap: nowrap;
			overflow-x: auto;
			max-width: 100%;
			scrollbar-width: none;
			margin: 0 calc(-1 * var(--gutter, 1rem));
			padding: 0 var(--gutter, 1rem);
		}
		.chips::-webkit-scrollbar {
			display: none;
		}
		.kc {
			flex: none;
		}
		.kpis {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 0.6rem;
		}
		.sel select {
			max-width: 9.5rem;
		}
		.found {
			display: none;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.dash,
		.top a,
		.seg button {
			transition: none;
		}
		.top a:hover {
			transform: none;
		}
	}
</style>
