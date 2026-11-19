<script lang="ts">
	// «Оберіть об’єкт»: пошук, фільтри, стан кожного об'єкта за сьогодні + розподіл енергії громади
	import { page } from '$app/state';
	import { api, errMessage, type SitesResponse, type SiteItem } from '#lib/api.ts';
	import { auth, greetingName } from '#lib/auth.svelte.ts';
	import { num, signed, energy } from '#lib/format.ts';
	import { viewFrom, withView } from '#lib/view.ts';
	import Status from '#lib/Status.svelte';
	import StatusTag from '#lib/StatusTag.svelte';
	import DemoPill from '#lib/DemoPill.svelte';
	import ViewSwitch from '#lib/ViewSwitch.svelte';
	import Icon from '#lib/Icon.svelte';
	import CommunityDistribution from '#lib/CommunityDistribution.svelte';
	import IndexBadge from '#lib/IndexBadge.svelte';
	import { independenceApi, duration, type IndependenceList, type IndependenceItem } from '#lib/api-independence.ts';

	const view = $derived(viewFrom(page.url));
	const tab = $derived(page.url.searchParams.get('tab') === 'distribution' ? 'distribution' : 'list');

	let data = $state<SitesResponse | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);

	let seq = 0;
	async function load(v = view) {
		const my = ++seq;
		loading = true;
		error = null;
		try {
			const d = await api.sites(v);
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

	// Індекс енергонезалежності — окремий запит; без нього список працює як раніше
	let ind = $state<IndependenceList | null>(null);
	let iseq = 0;
	async function loadInd(v = view) {
		const my = ++iseq;
		try {
			const d = await independenceApi.list(v);
			if (my === iseq) ind = d;
		} catch {
			if (my === iseq) ind = null;
		}
	}
	$effect(() => {
		loadInd(view);
	});
	const indById = $derived(new Map<number, IndependenceItem>((ind?.items ?? []).map((i) => [i.id, i])));
	const ic = $derived(ind?.community ?? null);
	const critNoReserve = $derived((ind?.items ?? []).filter((i) => i.critical && !(i.battery_kwh ?? 0)).length);

	// Фільтри (живуть у стані сторінки)
	let query = $state('');
	let category = $state<string>('');
	let onlySes = $state(false);
	let onlyCritical = $state(false);
	let sort = $state<'ses' | 'name' | 'balance' | 'weak'>('ses');
	let limit = $state(60);

	const categories = $derived.by(() => {
		const m = new Map<string, number>();
		for (const i of data?.items ?? []) m.set(i.category_short, (m.get(i.category_short) ?? 0) + 1);
		return [...m.entries()].sort((a, b) => b[1] - a[1]);
	});

	const norm = (s: string) => s.toLocaleLowerCase('uk').replace(/[’'"«»]/g, '').replace(/\s+/g, ' ');

	const filtered = $derived.by(() => {
		const q = norm(query.trim());
		let list = (data?.items ?? []).filter(
			(i) =>
				(!category || i.category_short === category) &&
				(!onlySes || i.has_ses) &&
				(!onlyCritical || (indById.get(i.id)?.critical ?? i.category_short.startsWith('Охорона'))) &&
				(!q || norm(`${i.name} ${i.address} ${i.city}`).includes(q))
		);
		const byName = (a: SiteItem, b: SiteItem) => a.name.localeCompare(b.name, 'uk');
		if (sort === 'name') list = list.sort(byName);
		else if (sort === 'weak')
			list = list.sort(
				(a, b) =>
					(indById.get(a.id)?.index ?? 0) - (indById.get(b.id)?.index ?? 0) ||
					Number(indById.get(b.id)?.critical ?? false) - Number(indById.get(a.id)?.critical ?? false) ||
					byName(a, b)
			);
		else if (sort === 'balance')
			list = list.sort(
				(a, b) => (a.balance_kwh_today ?? Infinity) - (b.balance_kwh_today ?? Infinity) || byName(a, b)
			);
		else list = list.sort((a, b) => Number(b.has_ses) - Number(a.has_ses) || byName(a, b));
		return list;
	});
	const shown = $derived(filtered.slice(0, limit));

	// Скидаємо «показати ще», коли змінюються фільтри
	$effect(() => {
		void query;
		void category;
		void onlySes;
		void onlyCritical;
		void sort;
		limit = 60;
	});

	const sesKw = $derived((data?.items ?? []).reduce((a, i) => a + (i.ses_kw ?? 0), 0));
	const balance = $derived(
		(data?.items ?? []).reduce((a, i) => a + (i.balance_kwh_today ?? 0), 0)
	);
	const gen = $derived(energy(data?.totals.generated_today_kwh));
	const cover = $derived(
		data && data.totals.consumed_today_kwh > 0
			? (data.totals.generated_today_kwh / data.totals.consumed_today_kwh) * 100
			: null
	);

	function tabHref(t: 'list' | 'distribution'): string {
		return withView('/', view, t === 'distribution' ? { tab: 'distribution' } : {});
	}
	function reset() {
		query = '';
		category = '';
		onlySes = false;
		onlyCritical = false;
	}
</script>

<svelte:head><title>Об’єкти · City Insight Map · Енергія</title></svelte:head>

<div class="head">
	<div>
		{#if auth.user}<p class="hello">Добрий день, {greetingName(auth.user.full_name)}</p>{/if}
		<h1>Оберіть об’єкт</h1>
		<p class="lead">Школа, садок, лікарня чи будь-яка інша будівля громади — стан енергії на сьогодні.</p>
	</div>
	<div class="head-side">
		<ViewSwitch now={data?.now ?? null} />
	</div>
</div>

<Status loading={loading && !data} {error} retry={() => load()} />

{#if ic}
	<a class="ind-banner" href={withView('/independence', view)}>
		<span class="ib-main">
			<span class="ib-l">Енергонезалежність громади зараз</span>
			<span class="ib-v"><b class="tnum">{num(ic.self_sufficiency_pct, 1)} %</b> електроенергії дає власне сонце</span>
		</span>
		<span class="ib-fact"><b class="tnum">{duration(ic.autonomy_hours_median)}</b> типовий заклад протримається без світла</span>
		<span class="ib-fact" class:warn={critNoReserve > 0}>
			<b class="tnum">{ic.critical_with_battery} з {ic.critical_sites_total}</b> критичних закладів мають резерв
		</span>
		<span class="ib-go">Що робити <Icon name="arrow-right" size={18} /></span>
	</a>
{/if}

{#if data}
	<section class="totals" class:stale={loading} aria-label="Підсумки по громаді">
		<div class="tile">
			<span class="t-ic navy"><Icon name="building" size={22} /></span>
			<p class="t-label">Об’єктів</p>
			<p class="t-val big-num">{num(data.totals.sites)}</p>
			<p class="t-sub">будівлі громади · дані UMUNI</p>
		</div>
		<div class="tile">
			<span class="t-ic sun"><Icon name="panel" size={22} /></span>
			<p class="t-label">З СЕС <DemoPill /></p>
			<p class="t-val big-num">{num(data.totals.with_ses)}</p>
			<p class="t-sub">сумарно {num(sesKw, 1)} кВт потужності</p>
		</div>
		<div class="tile">
			<span class="t-ic sun"><Icon name="sun" size={22} /></span>
			<p class="t-label">Згенеровано сьогодні <DemoPill /></p>
			<p class="t-val big-num">{gen.v}<span class="unit-s">{gen.u}</span></p>
			<p class="t-sub">
				{#if cover !== null}покриває {num(cover, 1)} % споживання громади{:else}&nbsp;{/if}
			</p>
		</div>
		<div class="tile bal {balance >= 0 ? 'pos' : 'neg'}">
			<span class="t-ic sign" aria-hidden="true">{balance >= 0 ? '+' : '−'}</span>
			<p class="t-label">Баланс громади <DemoPill /></p>
			<p class="t-val big-num">{signed(balance, 0)}<span class="unit-s">кВт·год</span></p>
			<p class="t-sub">
				<span class="ok-t">+ {data.totals.surplus_sites} у надлишку</span> ·
				<span class="bad-t">− {data.totals.deficit_sites} у дефіциті</span>
			</p>
		</div>
	</section>

	<nav class="seg tabs" aria-label="Режим перегляду">
		<a href={tabHref('list')} aria-current={tab === 'list' ? 'page' : undefined} data-sveltekit-reset="false" data-sveltekit-replacestate>
			<Icon name="building" size={18} /> Список об’єктів
		</a>
		<a href={tabHref('distribution')} aria-current={tab === 'distribution' ? 'page' : undefined} data-sveltekit-reset="false" data-sveltekit-replacestate>
			<Icon name="bolt" size={18} /> Розподілення енергії громади
		</a>
	</nav>

	{#if tab === 'list'}
		<section class="panel filters" aria-label="Пошук і фільтри">
			<div class="row1">
				<div class="search">
					<label for="q" class="visually-hidden">Пошук за назвою або адресою</label>
					<Icon name="search" size={20} />
					<input id="q" type="search" bind:value={query} placeholder="Пошук за назвою або адресою, напр. «ліцей 3»" autocomplete="off" />
				</div>
				<label class="switch">
					<input type="checkbox" role="switch" bind:checked={onlySes} />
					<span class="track" aria-hidden="true"><span class="knob"></span></span>
					<span>лише з СЕС</span>
				</label>
				<label class="switch">
					<input type="checkbox" role="switch" bind:checked={onlyCritical} />
					<span class="track" aria-hidden="true"><span class="knob"></span></span>
					<span>критичні заклади</span>
				</label>
				<div class="sort">
					<label for="sort">Сортувати</label>
					<select id="sort" bind:value={sort}>
						<option value="ses">спершу з СЕС</option>
						<option value="weak">найменш захищені спершу</option>
						<option value="balance">за балансом (дефіцит угорі)</option>
						<option value="name">за назвою</option>
					</select>
				</div>
			</div>
			<div class="chips" role="group" aria-label="Категорія">
				<button type="button" class="chip" aria-pressed={category === ''} onclick={() => (category = '')}>
					Усі <span class="c">{data.items.length}</span>
				</button>
				{#each categories as [name, count] (name)}
					<button type="button" class="chip" aria-pressed={category === name} onclick={() => (category = category === name ? '' : name)}>
						{name} <span class="c">{count}</span>
					</button>
				{/each}
			</div>
		</section>

		<p class="found" role="status" aria-live="polite">
			Знайдено <strong>{num(filtered.length)}</strong>
			{#if filtered.length !== data.items.length}з {num(data.items.length)}{/if}
			{#if query || category || onlySes || onlyCritical}
				· <button type="button" class="linkish" onclick={reset}>скинути фільтри</button>
			{/if}
		</p>

		{#if filtered.length}
			<ul class="cards" class:stale={loading}>
				{#each shown as it (it.id)}
					<li>
						<a class="site {it.status}" href={withView(`/object/${it.id}`, view)}>
							<span class="top">
								<span class="cat">{it.category_short}{#if indById.get(it.id)?.critical}<span class="crit-t"> · критичний</span>{/if}</span>
								{#if it.has_ses}
									<span class="ses"><Icon name="sun" size={15} stroke={2} /> СЕС {num(it.ses_kw, 1)} кВт</span>
								{/if}
							</span>
							<span class="name" title={it.name}>{it.name}</span>
							<span class="addr"><Icon name="pin" size={15} />{it.city && !it.address.includes(it.city) ? `${it.city}, ` : ''}{it.address}</span>
							{#if indById.get(it.id)}
								{@const x = indById.get(it.id)!}
								<span class="indep">
									<IndexBadge index={x.index} cls={x.index_class} size="sm" />
									<span class="aut tnum">{(x.battery_kwh ?? 0) > 0 ? `без світла ${duration(x.autonomy_hours)}` : 'без резерву'}</span>
								</span>
							{/if}
							<span class="bottom">
								<StatusTag status={it.status} kwh={it.balance_kwh_today} size="sm" />
								{#if it.generated_today_kwh !== null}
									<span class="gen tnum"><Icon name="sun" size={14} /> {num(it.generated_today_kwh, 1)} кВт·год</span>
								{/if}
							</span>
						</a>
					</li>
				{/each}
			</ul>
			{#if filtered.length > limit}
				<p class="more">
					<button type="button" class="btn btn-secondary" onclick={() => (limit += 60)}>
						Показати ще {num(Math.min(60, filtered.length - limit))} з {num(filtered.length - limit)}
					</button>
				</p>
			{/if}
		{:else}
			<div class="panel empty">
				<p><strong>Нічого не знайдено.</strong> Спробуйте іншу назву, номер закладу або вулицю.</p>
				<button type="button" class="btn btn-secondary" onclick={reset}>Скинути фільтри</button>
			</div>
		{/if}
	{:else}
		<CommunityDistribution items={data.items} {view} now={data.now} />
	{/if}
{/if}

<style>
	.head {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: flex-end;
		gap: 1rem 2rem;
		margin-bottom: 1.5rem;
	}
	.hello {
		margin: 0 0 0.2rem;
		color: var(--sun-ink);
		font-weight: 600;
	}
	h1 {
		font-size: 2.3rem;
		letter-spacing: -0.02em;
		margin-bottom: 0.3rem;
	}
	.lead {
		margin: 0;
	}
	.head-side {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 0.5rem;
	}
	.stale {
		opacity: 0.55;
		transition: opacity 0.2s;
	}

	/* Підсумки */
	.totals {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 1.25rem;
		margin-bottom: 1.75rem;
	}
	.tile {
		position: relative;
		background: var(--surface);
		border: 1px solid #e3e8ef;
		border-radius: var(--radius-lg);
		box-shadow: var(--shadow-md);
		padding: 1.25rem 1.35rem 1.15rem;
	}
	.t-ic {
		position: absolute;
		top: 1.15rem;
		right: 1.15rem;
		display: grid;
		place-items: center;
		width: 2.6rem;
		height: 2.6rem;
		border-radius: 12px;
	}
	.t-ic.navy {
		background: #e6eef8;
		color: var(--navy-3);
	}
	.t-ic.sun {
		background: var(--sun-soft);
		color: var(--sun-ink);
	}
	.t-ic.sign {
		font-size: 1.9rem;
		font-weight: 800;
		color: #fff;
		line-height: 1;
		padding-bottom: 0.15rem;
	}
	.pos .t-ic.sign {
		background: var(--surplus);
	}
	.neg .t-ic.sign {
		background: var(--deficit);
	}
	.t-label {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.3rem 0.5rem;
		padding-right: 3.1rem;
		margin: 0 0 0.35rem;
		font-weight: 600;
		color: #3d4857;
		min-height: 1.6rem;
	}
	.t-val {
		margin: 0;
		font-size: 2.6rem;
	}
	.t-val .unit-s {
		font-size: 1.15rem;
	}
	.pos .t-val {
		color: var(--surplus-ink);
	}
	.neg .t-val {
		color: var(--deficit-ink);
	}
	.t-sub {
		margin: 0.35rem 0 0;
		font-size: 0.875rem;
		color: var(--muted);
	}
	.ok-t {
		color: var(--surplus-ink);
		font-weight: 600;
	}
	.bad-t {
		color: var(--deficit-ink);
		font-weight: 600;
	}

	.tabs {
		margin-bottom: 1.25rem;
	}

	/* Фільтри */
	.filters {
		padding: 1rem 1.25rem;
		margin-bottom: 0.9rem;
	}
	.row1 {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.75rem 1.5rem;
		margin-bottom: 0.9rem;
	}
	.search {
		flex: 1 1 24rem;
		position: relative;
		display: flex;
		align-items: center;
	}
	.search :global(.icon) {
		position: absolute;
		left: 0.9rem;
		color: var(--muted);
		pointer-events: none;
	}
	.search input {
		width: 100%;
		min-height: 48px;
		padding-left: 2.75rem;
		font-size: 1.05rem;
		border-radius: 12px;
		background: #f7f9fc;
	}
	.search input:focus-visible {
		background: #fff;
	}
	.switch {
		display: inline-flex;
		align-items: center;
		gap: 0.6rem;
		font-size: 0.95rem;
		cursor: pointer;
		user-select: none;
	}
	.switch input {
		position: absolute;
		opacity: 0;
		width: 1px;
		height: 1px;
	}
	.track {
		position: relative;
		width: 2.75rem;
		height: 1.6rem;
		border-radius: 999px;
		background: #c3ccd7;
		transition: background 0.2s;
	}
	.knob {
		position: absolute;
		top: 0.2rem;
		left: 0.2rem;
		width: 1.2rem;
		height: 1.2rem;
		border-radius: 50%;
		background: #fff;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
		transition: transform 0.2s var(--ease);
	}
	.switch input:checked + .track {
		background: var(--sun-strong);
	}
	.switch input:checked + .track .knob {
		transform: translateX(1.15rem);
	}
	.switch input:focus-visible + .track {
		outline: 3px solid var(--focus);
		outline-offset: 2px;
		box-shadow: 0 0 0 5px var(--text);
	}
	.sort {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.sort label {
		font-weight: 500;
		color: var(--muted);
	}
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}
	.chip {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		padding: 0.4rem 0.85rem;
		min-height: 38px;
		border-radius: 999px;
		border: 1px solid #cfd7e1;
		background: #fff;
		color: #2b3645;
		font: inherit;
		font-size: 0.925rem;
		font-weight: 500;
		cursor: pointer;
		transition:
			background 0.15s,
			border-color 0.15s;
	}
	.chip:hover {
		border-color: var(--navy-3);
		background: #f3f6fa;
	}
	.chip[aria-pressed='true'] {
		background: var(--navy);
		border-color: var(--navy);
		color: #fff;
	}
	.chip .c {
		font-size: 0.8rem;
		font-weight: 700;
		padding: 0 0.45rem;
		border-radius: 999px;
		background: #edf1f5;
		color: #3d4857;
	}
	.chip[aria-pressed='true'] .c {
		background: rgba(255, 255, 255, 0.18);
		color: #fff;
	}
	.found {
		margin: 0 0 0.9rem;
		color: var(--muted);
	}
	.linkish {
		background: none;
		border: 0;
		padding: 0;
		font: inherit;
		color: var(--accent);
		text-decoration: underline;
		cursor: pointer;
	}

	/* Картки об'єктів */
	.cards {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 19rem), 1fr));
		gap: 1rem;
		transition: opacity 0.2s;
	}
	.site {
		position: relative;
		height: 100%;
		display: flex;
		flex-direction: column;
		gap: 0.45rem;
		padding: 1rem 1.1rem 1rem 1.3rem;
		background: var(--surface);
		border: 1px solid #e3e8ef;
		border-radius: 14px;
		box-shadow: var(--shadow);
		color: var(--text);
		text-decoration: none;
		overflow: hidden;
		transition:
			transform 0.18s var(--ease),
			box-shadow 0.18s var(--ease),
			border-color 0.18s;
	}
	.site::before {
		content: '';
		position: absolute;
		inset: 0 auto 0 0;
		width: 5px;
		background: #d6dce4;
	}
	.site.surplus::before {
		background: var(--surplus);
	}
	.site.deficit::before {
		background: var(--deficit);
	}
	.site:hover {
		color: var(--text);
		border-color: #c8d2de;
		box-shadow: var(--shadow-lg);
		transform: translateY(-2px);
	}
	.site:focus-visible {
		border-radius: 14px;
	}
	.top {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
	}
	.cat {
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--muted);
	}
	.ses {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		padding: 0.12rem 0.55rem;
		border-radius: 999px;
		background: var(--sun-soft);
		color: var(--sun-ink);
		font-size: 0.8125rem;
		font-weight: 700;
		white-space: nowrap;
		font-variant-numeric: tabular-nums;
	}
	.name {
		font-size: 1.05rem;
		font-weight: 650;
		line-height: 1.3;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
	.addr {
		display: flex;
		gap: 0.35rem;
		align-items: flex-start;
		font-size: 0.875rem;
		color: var(--muted);
		line-height: 1.35;
	}
	.addr :global(.icon) {
		margin-top: 0.05rem;
	}
	.bottom {
		margin-top: auto;
		padding-top: 0.5rem;
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: center;
		gap: 0.4rem;
	}
	.gen {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		font-size: 0.8125rem;
		color: var(--muted);
	}
	.ind-banner {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.75rem 2rem;
		margin: 0 0 1.25rem;
		padding: 1rem 1.4rem;
		border-radius: var(--radius-lg);
		color: #fff;
		text-decoration: none;
		background:
			radial-gradient(500px 200px at 0% 0%, rgba(245, 165, 36, 0.3), transparent 70%),
			linear-gradient(135deg, #0f2f52, #163d68);
		box-shadow: var(--shadow-md);
	}
	.ind-banner:hover {
		color: #fff;
		box-shadow: var(--shadow-lg);
	}
	.ib-main {
		display: flex;
		flex-direction: column;
		flex: 1 1 20rem;
	}
	.ib-l {
		font-size: 0.85rem;
		font-weight: 600;
		color: #ffd894;
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.ib-v {
		font-size: 1.2rem;
	}
	.ib-v b {
		font-size: 1.9rem;
		margin-right: 0.2rem;
	}
	.ib-fact {
		display: flex;
		flex-direction: column;
		font-size: 0.875rem;
		color: #c9d6e6;
		max-width: 15rem;
	}
	.ib-fact b {
		font-size: 1.25rem;
		color: #fff;
	}
	.ib-fact.warn b {
		color: #ffb48f;
	}
	.ib-go {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0.55rem 1rem;
		border-radius: 10px;
		background: var(--sun);
		color: #2b1a00;
		font-weight: 700;
	}
	.indep {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.3rem 0.6rem;
	}
	.aut {
		font-size: 0.8125rem;
		color: #3d4857;
	}
	.crit-t {
		color: #8f1414;
	}
	.more {
		text-align: center;
		margin-top: 1.25rem;
	}
	.empty p {
		margin-bottom: 0.75rem;
	}

	@media (max-width: 1200px) {
		.totals {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
	@media (max-width: 560px) {
		.totals {
			grid-template-columns: 1fr;
		}
		h1 {
			font-size: 1.8rem;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.site,
		.site:hover {
			transition: none;
			transform: none;
		}
	}
</style>
