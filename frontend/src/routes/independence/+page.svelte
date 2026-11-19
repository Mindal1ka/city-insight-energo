<script lang="ts">
	// «Енергонезалежність громади»: скільки електроенергії дає власне сонце, скільки годин заклади
	// тримаються без світла і що поставити насамперед. Карти навмисно немає (безпека критичних об'єктів).
	import { page } from '$app/state';
	import { errMessage } from '#lib/api.ts';
	import {
		independenceApi,
		duration,
		money,
		categoryRank,
		addKw,
		type IndependenceList,
		type IndependenceItem
	} from '#lib/api-independence.ts';
	import { num } from '#lib/format.ts';
	import { viewFrom, withView } from '#lib/view.ts';
	import Status from '#lib/Status.svelte';
	import DemoPill from '#lib/DemoPill.svelte';
	import Icon from '#lib/Icon.svelte';
	import IndexBadge from '#lib/IndexBadge.svelte';
	import Term from '#lib/Term.svelte';

	const view = $derived(viewFrom(page.url));

	let data = $state<IndependenceList | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);

	let seq = 0;
	async function load(v = view) {
		const my = ++seq;
		loading = true;
		error = null;
		try {
			const d = await independenceApi.list(v);
			if (my === seq) data = d;
		} catch (e) {
			if (my === seq) error = errMessage(e);
		} finally {
			if (my === seq) loading = false;
		}
	}
	$effect(() => {
		load(view);
	});

	const c = $derived(data?.community);
	const hasBat = (i: IndependenceItem) => (i.battery_kwh ?? 0) > 0;

	// Критичні заклади без резерву (без акумулятора) — найперше, що треба виправити
	const noReserve = $derived(
		(data?.items ?? [])
			.filter((i) => i.critical && !hasBat(i))
			.sort((a, b) => (b.elec_kwh_year ?? 0) - (a.elec_kwh_year ?? 0))
	);
	let showAllCrit = $state(false);

	// Фільтри рейтингу
	let category = $state('');
	let onlyCritical = $state(false);
	let onlyNoSes = $state(false);
	let query = $state('');
	let sort = $state<'weak' | 'strong' | 'name'>('weak');
	let limit = $state(25);

	const norm = (s: string) => s.toLocaleLowerCase('uk').replace(/[’'"«»]/g, '');
	const cats = $derived(
		[...(data?.categories ?? [])].sort(
			(a, b) => categoryRank(a.category_short) - categoryRank(b.category_short) || b.sites - a.sites
		)
	);
	const filtered = $derived.by(() => {
		const q = norm(query.trim());
		const l = (data?.items ?? []).filter(
			(i) =>
				(!category || i.category_short === category) &&
				(!onlyCritical || i.critical) &&
				(!onlyNoSes || !i.has_ses) &&
				(!q || norm(`${i.name} ${i.address}`).includes(q))
		);
		const byName = (a: IndependenceItem, b: IndependenceItem) => a.name.localeCompare(b.name, 'uk');
		if (sort === 'name') return l.sort(byName);
		if (sort === 'strong') return l.sort((a, b) => b.index - a.index || byName(a, b));
		// найменш захищені спершу: критичні й школи/садки вище при однаковому індексі
		return l.sort(
			(a, b) =>
				a.index - b.index ||
				categoryRank(a.category_short) - categoryRank(b.category_short) ||
				(b.elec_kwh_year ?? 0) - (a.elec_kwh_year ?? 0)
		);
	});
	$effect(() => {
		void category;
		void onlyCritical;
		void onlyNoSes;
		void query;
		void sort;
		limit = 25;
	});
	function reset() {
		category = '';
		onlyCritical = false;
		onlyNoSes = false;
		query = '';
	}
	const maxPct = $derived(
		Math.max(5, ...cats.map((x) => x.self_sufficiency_pct ?? 0), c?.potential_self_sufficiency_pct ?? 0)
	);
	/** Короткий план для рядка рейтингу: «акумулятор + СЕС 25 кВт → 39 %» */
	function todo(i: IndependenceItem): string {
		const p: string[] = [];
		if (!hasBat(i)) p.push('акумулятор');
		if (addKw(i) >= 1)
			p.push(
				`${i.has_ses ? '+' : ''}СЕС ${num(addKw(i), 0)} кВт → ${num(i.potential_self_sufficiency_pct, 0)} % від сонця`
			);
		return p.join(' + ');
	}
	const obj = (id: number) => withView(`/object/${id}`, view);
</script>

<svelte:head><title>Енергонезалежність громади · City Insight Map · Енергія</title></svelte:head>

<div class="head">
	<div>
		<p class="eyebrow">Електрика · сонце · резерв</p>
		<h1><Term key="енергонезалежність">Енергонезалежність</Term> громади</h1>
		<p class="lead">
			Скільки електроенергії заклади отримують від власного сонця, скільки годин протримаються без світла
			і що поставити насамперед. Спершу — лікарні, далі школи й садки.
		</p>
	</div>
	<DemoPill text="Будівлі й річне споживання електроенергії — реальні дані UMUNI 2025; наявні СЕС і акумулятори змодельовані, доки місто не дасть перелік" />
</div>

<Status loading={loading && !data} {error} retry={() => load()} />

{#if data && c}
	<div class:stale={loading}>
		<!-- Головні числа -->
		<section class="hero" aria-label="Стан енергонезалежності громади">
			<div class="h-main">
				<p class="h-l">Власне сонце покриває</p>
				<p class="h-v"><span class="big-num">{num(c.self_sufficiency_pct, 1)}</span><span class="u">%</span></p>
				<p class="h-s">
					електроенергії всіх {num(c.sites)} будівель громади за рік
					({num(c.solar_kwh_year_est / 1000, 0)} з {num(c.elec_kwh_year_2025 / 1000, 0)} МВт·год).
					Решту купуємо з мережі.
				</p>
			</div>
			<ul class="h-tiles">
				<li>
					<span class="t-l"><Icon name="panel" size={18} /> <Term key="СЕС">СЕС</Term> на дахах</span>
					<span class="t-v tnum">{num(c.ses_kw_total, 0)} <small>кВт</small></span>
					<span class="t-s">на {num(c.ses_sites)} з {num(c.sites)} будівель</span>
				</li>
				<li>
					<span class="t-l"><Icon name="battery" size={18} /> <Term key="акумулятор">Акумулятори</Term></span>
					<span class="t-v tnum">{num(c.battery_kwh_total, 0)} <small>кВт·год</small></span>
					<span class="t-s">запас енергії на випадок відключення</span>
				</li>
				<li>
					<span class="t-l"><Icon name="clock" size={18} /> <Term key="автономність">Автономність</Term></span>
					<span class="t-v tnum">{duration(c.autonomy_hours_median)}</span>
					<span class="t-s">типовий заклад з акумулятором тримається вночі</span>
				</li>
				<li class="crit-tile">
					<span class="t-l"><Icon name="alert" size={18} /> Критичні заклади</span>
					<span class="t-v tnum">{c.critical_with_battery} <small>з {c.critical_sites_total} мають акумулятор</small></span>
					<span class="t-s">{c.critical_with_ses} з {c.critical_sites_total} мають СЕС</span>
				</li>
			</ul>
		</section>

		<!-- Потенціал -->
		<section class="panel pot" aria-labelledby="pot-h">
			<div class="pot-txt">
				<p class="eyebrow">Якщо поставити рекомендовані СЕС</p>
				<h2 id="pot-h">
					Енергонезалежність громади зросте з <span class="from tnum">{num(c.self_sufficiency_pct, 1)} %</span>
					до <span class="to tnum">{num(c.potential_self_sufficiency_pct, 0)} %</span>
				</h2>
				<p>
					Потрібно ще <b class="tnum">{num(c.potential_kw, 0)} кВт</b> панелей, підібраних під власне споживання кожної будівлі
					(без надлишку, який не можна продати). Орієнтовна вартість — <b>{money(c.potential_cost_uah)}</b>.
				</p>
			</div>
			<div class="pot-bar" role="img" aria-label="Зараз {num(c.self_sufficiency_pct, 1)} %, з рекомендованими СЕС {num(c.potential_self_sufficiency_pct, 0)} %">
				<div class="pb-row"><span>зараз</span><div class="pb"><span class="now" style="width: {c.self_sufficiency_pct}%"></span></div><b class="tnum">{num(c.self_sufficiency_pct, 1)} %</b></div>
				<div class="pb-row"><span>з новими СЕС</span><div class="pb"><span class="next" style="width: {c.potential_self_sufficiency_pct}%"></span></div><b class="tnum">{num(c.potential_self_sufficiency_pct, 0)} %</b></div>
			</div>
			<a class="btn" href="/solar">Де ставити нові СЕС <Icon name="arrow-right" size={18} /></a>
		</section>

		<!-- Критичні без резерву -->
		<section class="panel alert-list" aria-labelledby="crit-h">
			<div class="panel-head">
				<div>
					<h2 id="crit-h">
						<span class="a-ic" aria-hidden="true">!</span>
						Критичні заклади без резерву: {noReserve.length}
					</h2>
					<p class="muted sub">Немає акумулятора — у разі відключення світла заклад зупиняється одразу. Почати варто з них.</p>
				</div>
			</div>
			{#if noReserve.length}
				<ul class="crit-list">
					{#each showAllCrit ? noReserve : noReserve.slice(0, 6) as i (i.id)}
						<li>
							<a href={obj(i.id)}>
								<span class="cl-name">{i.name}</span>
								<span class="cl-addr">{i.address}</span>
								<span class="cl-do">
									{#if i.has_ses}
										СЕС {num(i.ses_kw, 1)} кВт є — додати акумулятор
									{:else}
										{addKw(i) >= 1 ? `додати акумулятор і СЕС ≈ ${num(addKw(i), 0)} кВт` : 'додати акумулятор'}
									{/if}
									<Icon name="arrow-right" size={16} />
								</span>
							</a>
						</li>
					{/each}
				</ul>
				{#if noReserve.length > 6}
					<button type="button" class="btn btn-secondary" onclick={() => (showAllCrit = !showAllCrit)} aria-expanded={showAllCrit}>
						{showAllCrit ? 'Згорнути' : `Показати всі ${noReserve.length}`}
					</button>
				{/if}
			{:else}
				<p class="ok-msg"><Icon name="check" size={20} /> Усі критичні заклади мають акумулятор. Наступний крок — школи й садки нижче в рейтингу.</p>
			{/if}
		</section>

		<!-- Категорії -->
		<section class="panel" aria-labelledby="cat-h">
			<h2 id="cat-h">За типом закладів</h2>
			<div class="table-wrap">
				<table>
					<thead>
						<tr>
							<th scope="col">Тип</th>
							<th scope="col" class="num">Будівель</th>
							<th scope="col" class="num">З СЕС</th>
							<th scope="col">Сонце покриває</th>
							<th scope="col" class="num">Автономність (медіана)</th>
							<th scope="col" class="num">Рекомендовано СЕС</th>
						</tr>
					</thead>
					<tbody>
						{#each cats as k (k.category_short)}
							<tr>
								<th scope="row">
									<button type="button" class="linkish" onclick={() => { category = k.category_short; document.getElementById('rank-h')?.scrollIntoView({ behavior: 'smooth' }); }}>
										{k.category_short}
									</button>
									{#if categoryRank(k.category_short) === 0}<span class="pill pill-bad">критичні</span>{/if}
								</th>
								<td class="num">{num(k.sites)}</td>
								<td class="num">{num(k.with_ses)}</td>
								<td>
									<span class="cbar"><span style="width: {((k.self_sufficiency_pct ?? 0) / maxPct) * 100}%"></span></span>
									<b class="tnum">{num(k.self_sufficiency_pct, 1)} %</b>
								</td>
								<td class="num">{k.autonomy_hours_median ? duration(k.autonomy_hours_median) : 'немає акумуляторів'}</td>
								<td class="num">{k.potential_kw ? `${num(k.potential_kw, 0)} кВт` : '—'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</section>

		<!-- Рейтинг -->
		<section class="panel" aria-labelledby="rank-h">
			<div class="panel-head">
				<div>
					<h2 id="rank-h">Рейтинг закладів за індексом енергонезалежності</h2>
					<p class="muted sub">Індекс 0–100 враховує частку власного сонця, години без світла й важливість закладу. Натисніть на заклад, щоб побачити, що зробити.</p>
				</div>
			</div>
			<div class="filters">
				<div class="search">
					<label for="iq" class="visually-hidden">Пошук за назвою або адресою</label>
					<Icon name="search" size={18} />
					<input id="iq" type="search" bind:value={query} placeholder="Пошук: «лікарня», «ліцей 3»…" autocomplete="off" />
				</div>
				<label class="chk"><input type="checkbox" bind:checked={onlyCritical} /> лише критичні</label>
				<label class="chk"><input type="checkbox" bind:checked={onlyNoSes} /> лише без СЕС</label>
				<div class="sort">
					<label for="isort">Сортувати</label>
					<select id="isort" bind:value={sort}>
						<option value="weak">найменш захищені спершу</option>
						<option value="strong">найбільш незалежні спершу</option>
						<option value="name">за назвою</option>
					</select>
				</div>
			</div>
			<div class="chips" role="group" aria-label="Тип закладу">
				<button type="button" class="chip" aria-pressed={category === ''} onclick={() => (category = '')}>Усі</button>
				{#each cats as k (k.category_short)}
					<button type="button" class="chip" aria-pressed={category === k.category_short} onclick={() => (category = category === k.category_short ? '' : k.category_short)}>
						{k.category_short} <span class="c">{k.sites}</span>
					</button>
				{/each}
			</div>
			<p class="found" role="status" aria-live="polite">
				Показано <b>{num(Math.min(limit, filtered.length))}</b> з {num(filtered.length)}
				{#if category || onlyCritical || onlyNoSes || query}· <button type="button" class="linkish" onclick={reset}>скинути фільтри</button>{/if}
			</p>

			{#if filtered.length}
				<div class="table-wrap">
					<table class="rank">
						<thead>
							<tr>
								<th scope="col" class="num">№</th>
								<th scope="col">Заклад</th>
								<th scope="col">Індекс</th>
								<th scope="col" class="num">Сонце покриває</th>
								<th scope="col" class="num">Без світла вночі</th>
								<th scope="col">Що зробити</th>
							</tr>
						</thead>
						<tbody>
							{#each filtered.slice(0, limit) as i, n (i.id)}
								<tr class:crit={i.critical}>
									<td class="num muted">{n + 1}</td>
									<td class="name">
										<a href={obj(i.id)}>{i.name}</a>
										<span class="sub2">
											{i.category_short}{#if i.critical} · <b class="crit-t">критичний</b>{/if}
										</span>
									</td>
									<td><IndexBadge index={i.index} cls={i.index_class} size="sm" /></td>
									<td class="num">{i.has_ses ? `${num(i.self_sufficiency_pct, 0)} %` : 'СЕС немає'}</td>
									<td class="num">{hasBat(i) ? duration(i.autonomy_hours) : 'зупиниться одразу'}</td>
									<td class="todo">
										{#if i.data_ok === false}<span class="muted">внести споживання в UMUNI</span>{#if !hasBat(i)}; акумулятор{/if}{:else if todo(i)}{todo(i)}{:else}<span class="muted">усе є — підтримувати</span>{/if}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
				{#if filtered.length > limit}
					<p class="more"><button type="button" class="btn btn-secondary" onclick={() => (limit += 50)}>Показати ще {num(Math.min(50, filtered.length - limit))}</button></p>
				{/if}
			{:else}
				<div class="empty">
					<p><strong>Немає закладів за цими умовами.</strong> Спробуйте зняти фільтр «лише без СЕС» або змінити тип.</p>
					<button type="button" class="btn btn-secondary" onclick={reset}>Скинути фільтри</button>
				</div>
			{/if}
		</section>

		{#if data.notes?.length}
			<ul class="notes muted small">
				{#each data.notes as n, k (k)}<li>{n}</li>{/each}
			</ul>
		{/if}
		<p class="security muted small">
			<Icon name="lock" size={16} /> Карту навмисно не показуємо: розташування закладів із резервним живленням — чутлива
			інформація. Дані доступні лише після входу.
		</p>
	</div>
{/if}

<style>
	.head {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: flex-end;
		gap: 1rem 2rem;
		margin-bottom: 1.25rem;
	}
	.head .eyebrow {
		margin: 0 0 0.2rem;
		color: var(--sun-ink);
	}
	h1 {
		font-size: 2.3rem;
		letter-spacing: -0.02em;
		margin-bottom: 0.3rem;
	}
	.lead {
		margin: 0;
	}
	.stale {
		opacity: 0.55;
		transition: opacity 0.2s;
	}
	section {
		margin-bottom: 1.25rem;
	}

	/* hero */
	.hero {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1.9fr);
		gap: 1.5rem 2rem;
		align-items: center;
		padding: 1.6rem 1.8rem;
		border-radius: var(--radius-lg);
		color: #fff;
		background:
			radial-gradient(600px 260px at 0% 0%, rgba(245, 165, 36, 0.28), transparent 70%),
			linear-gradient(135deg, #0f2f52, #163d68);
		box-shadow: var(--shadow-lg);
	}
	.hero :global(.term),
	.hero :global(button) {
		color: inherit;
	}
	.h-l {
		margin: 0;
		font-weight: 600;
		color: #ffd894;
		font-size: 1.1rem;
	}
	.h-v {
		margin: 0.1rem 0 0.3rem;
	}
	.h-v .big-num {
		font-size: 4.6rem;
	}
	.h-v .u {
		font-size: 2rem;
		font-weight: 700;
		margin-left: 0.15em;
	}
	.h-s {
		margin: 0;
		color: #dbe5f1;
	}
	.h-tiles {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.75rem;
	}
	.h-tiles li {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		padding: 0.85rem 1rem;
		border-radius: 12px;
		background: rgba(255, 255, 255, 0.08);
		border: 1px solid rgba(255, 255, 255, 0.14);
	}
	.t-l {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		font-weight: 600;
		color: #c9d6e6;
		font-size: 0.925rem;
	}
	.t-v {
		font-size: 1.85rem;
		font-weight: 700;
		line-height: 1.15;
	}
	.t-v small {
		font-size: 0.95rem;
		font-weight: 600;
		color: #c9d6e6;
	}
	.t-s {
		font-size: 0.85rem;
		color: #c9d6e6;
	}
	.crit-tile {
		background: rgba(194, 65, 12, 0.22) !important;
		border-color: rgba(255, 170, 130, 0.45) !important;
	}

	/* потенціал */
	.pot {
		display: grid;
		grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr) auto;
		gap: 1rem 2rem;
		align-items: center;
		border-left: 6px solid var(--surplus);
	}
	.pot .eyebrow {
		margin: 0 0 0.2rem;
	}
	.pot h2 {
		font-size: 1.45rem;
	}
	.pot p:last-child {
		margin: 0;
	}
	.from {
		color: var(--muted);
	}
	.to {
		color: var(--surplus-ink);
		font-size: 1.15em;
	}
	.pot-bar {
		display: grid;
		gap: 0.5rem;
	}
	.pb-row {
		display: grid;
		grid-template-columns: 7.5rem minmax(0, 1fr) 3.5rem;
		align-items: center;
		gap: 0.6rem;
		font-size: 0.9rem;
	}
	.pb-row b {
		text-align: right;
	}
	.pb {
		height: 14px;
		border-radius: 999px;
		background: #e8edf3;
		overflow: hidden;
	}
	.pb span {
		display: block;
		height: 100%;
		border-radius: 999px;
	}
	.pb .now {
		background: var(--sun-strong);
	}
	.pb .next {
		background: var(--surplus);
	}

	/* критичні */
	.alert-list {
		border-left: 6px solid var(--deficit);
	}
	.alert-list .panel-head {
		margin-bottom: 0.75rem;
	}
	.alert-list h2 {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		font-size: 1.4rem;
	}
	.a-ic {
		display: grid;
		place-items: center;
		width: 2rem;
		height: 2rem;
		border-radius: 50%;
		background: var(--deficit);
		color: #fff;
		font-weight: 800;
	}
	.sub {
		margin: 0.2rem 0 0;
	}
	.crit-list {
		list-style: none;
		margin: 0 0 0.9rem;
		padding: 0;
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 22rem), 1fr));
		gap: 0.75rem;
	}
	.crit-list a {
		height: 100%;
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		padding: 0.85rem 1rem;
		border-radius: 12px;
		border: 1px solid #f3c3ad;
		background: #fff8f5;
		color: var(--text);
		text-decoration: none;
	}
	.crit-list a:hover {
		border-color: var(--deficit);
		box-shadow: var(--shadow-md);
	}
	.cl-name {
		font-weight: 700;
		line-height: 1.3;
	}
	.cl-addr {
		font-size: 0.85rem;
		color: var(--muted);
	}
	.cl-do {
		margin-top: auto;
		padding-top: 0.35rem;
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		font-weight: 600;
		color: var(--accent);
	}
	.ok-msg {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		color: var(--surplus-ink);
		font-weight: 600;
		margin: 0;
	}

	/* таблиці */
	.cbar {
		display: inline-block;
		width: 8rem;
		height: 10px;
		border-radius: 999px;
		background: #e8edf3;
		margin-right: 0.5rem;
		vertical-align: middle;
		overflow: hidden;
	}
	.cbar span {
		display: block;
		height: 100%;
		background: var(--sun-strong);
	}
	th[scope='row'] {
		font-weight: 600;
		white-space: nowrap;
	}
	th[scope='row'] .pill {
		margin-left: 0.4rem;
	}
	.linkish {
		background: none;
		border: 0;
		padding: 0;
		font: inherit;
		font-weight: inherit;
		color: var(--accent);
		text-decoration: underline;
		cursor: pointer;
	}
	.filters {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.75rem 1.5rem;
		margin-bottom: 0.75rem;
	}
	.search {
		flex: 1 1 18rem;
		position: relative;
		display: flex;
		align-items: center;
	}
	.search :global(.icon) {
		position: absolute;
		left: 0.8rem;
		color: var(--muted);
		pointer-events: none;
	}
	.search input {
		width: 100%;
		padding-left: 2.5rem;
		min-height: 44px;
	}
	.chk {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		font-weight: 500;
		font-size: 0.95rem;
		cursor: pointer;
	}
	.chk input {
		width: 1.2rem;
		height: 1.2rem;
		accent-color: var(--navy-3);
	}
	.sort {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.45rem;
		margin-bottom: 0.75rem;
	}
	.chip {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.35rem 0.8rem;
		min-height: 36px;
		border-radius: 999px;
		border: 1px solid #cfd7e1;
		background: #fff;
		font: inherit;
		font-size: 0.9rem;
		font-weight: 500;
		cursor: pointer;
	}
	.chip[aria-pressed='true'] {
		background: var(--navy);
		border-color: var(--navy);
		color: #fff;
	}
	.chip .c {
		font-size: 0.78rem;
		font-weight: 700;
		padding: 0 0.4rem;
		border-radius: 999px;
		background: #edf1f5;
		color: #3d4857;
	}
	.found {
		color: var(--muted);
		margin: 0 0 0.75rem;
	}
	.rank td {
		vertical-align: middle;
	}
	.rank tr.crit td:first-child {
		box-shadow: inset 4px 0 0 var(--deficit);
	}
	.rank .name a {
		font-weight: 600;
	}
	.sub2 {
		display: block;
		font-size: 0.8rem;
		color: var(--muted);
	}
	.crit-t {
		color: #8f1414;
	}
	.todo {
		font-size: 0.9rem;
	}
	.more {
		text-align: center;
		margin: 1rem 0 0;
	}
	.empty p {
		margin-bottom: 0.6rem;
	}
	.notes {
		margin: 0 0 0.5rem;
		padding-left: 1.2rem;
	}
	.security {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}

	@media (max-width: 1250px) {
		.hero {
			grid-template-columns: 1fr;
		}
		.pot {
			grid-template-columns: 1fr;
		}
		.pot .btn {
			justify-self: start;
		}
	}
	@media (max-width: 600px) {
		.h-tiles {
			grid-template-columns: 1fr;
		}
		h1 {
			font-size: 1.8rem;
		}
		.h-v .big-num {
			font-size: 3.4rem;
		}
	}
</style>
