<script lang="ts">
	// Список усіх комунальних об'єктів: K, генерація/споживання, заощаджено, окупність. Сортування + фільтри.
	import { goto } from '$app/navigation';
	import { revealRows, listIn, listOut, isReduced } from '#lib/motion.ts';
	import { flip } from 'svelte/animate';
	import Icon from '#lib/Icon.svelte';
	import { page } from '$app/state';
	import SesFilters from '#lib/SesFilters.svelte';
	import KBadge from '#lib/KBadge.svelte';
	import CategoryIcon from '#lib/CategoryIcon.svelte';
	import { catLabel } from '#lib/categories.ts';
	import { errMessage } from '#lib/api.ts';
	import { auth } from '#lib/auth.svelte.ts';
	import { matchExtra, seasonDay, kwhMonth, type Season } from '#lib/ses-extra.ts';
	import {
		fetchSes,
		filterItems,
		K_CLASSES,
		uah,
		type KClass,
		type Period,
		type SesItem,
		type SesList
	} from '#lib/api-ses.ts';

	const P0 = page.url.searchParams.get('p');
	let period = $state<Period>(P0 === 'day' || P0 === 'month' ? P0 : 'year');
	let classes = $state<KClass[]>([]);
	let types = $state<string[]>([]);
	let q = $state('');
	let department = $state(page.url.searchParams.get('department') ?? '');
	let need = $state(false);
	let season = $state<Season | null>(null);
	let data = $state<SesList | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);

	type Key = 'name' | 'type' | 'dept' | 'month' | 'k' | 'gen' | 'cons' | 'saved' | 'payback';
	let sortKey = $state<Key>('k');
	let asc = $state(false);

	let reqId = 0;
	async function load(p: Period, s: Season | null) {
		const my = ++reqId;
		loading = true;
		error = null;
		try {
			const day = seasonDay(s);
			const d = day ? await fetchSes('month', day) : await fetchSes(p);
			if (my === reqId) data = d;
		} catch (e) {
			if (my === reqId) error = errMessage(e);
		} finally {
			if (my === reqId) loading = false;
		}
	}
	$effect(() => {
		void auth.user?.token; // перезавантажити після входу / виходу
		load(period, season);
	});

	const restricted = $derived(!!data?.restricted);
	const items = $derived(data?.items ?? []);
	const classOrder = new Map(K_CLASSES.map((c, i) => [c.id, i]));

	function val(i: SesItem, k: Key): number | string | null {
		switch (k) {
			case 'name':
				return i.name;
			case 'type':
				return catLabel(i.category_short);
			case 'dept':
				return i.department ?? null;
			case 'month':
				return i.cons_kwh_month_avg ?? null;
			case 'k':
				return i.k ?? (i.k_class ? -1 - (classOrder.get(i.k_class) ?? 0) : null);
			case 'gen':
				return i.gen_kwh;
			case 'cons':
				return i.cons_kwh;
			case 'saved':
				return i.saved_uah_year;
			case 'payback':
				return i.payback_years;
		}
	}

	const rows = $derived.by(() => {
		const list = filterItems(items, { classes: restricted ? [] : classes, types, q }).filter((i) => matchExtra(i, { department, need }));
		const dir = asc ? 1 : -1;
		return [...list].sort((a, b) => {
			const x = val(a, sortKey);
			const y = val(b, sortKey);
			if (x == null && y == null) return a.name.localeCompare(b.name, 'uk');
			if (x == null) return 1;
			if (y == null) return -1;
			if (typeof x === 'string' || typeof y === 'string') return String(x).localeCompare(String(y), 'uk') * dir;
			return (x - y) * dir;
		});
	});

	// Порційний показ: спершу 40 рядків, далі +40, коли низ списку під'їжджає до екрана (DOM лишається малим)
	const STEP = 40;
	let limit = $state(STEP);
	const shown = $derived(rows.slice(0, limit));
	const flipDur = isReduced() ? 0 : 220;
	function more(node: HTMLElement) {
		const io = new IntersectionObserver((e) => {
			if (e.some((x) => x.isIntersecting)) limit += STEP;
		}, { rootMargin: '600px 0px' });
		io.observe(node);
		return { destroy: () => io.disconnect() };
	}

	function sortBy(k: Key) {
		if (sortKey === k) asc = !asc;
		else {
			sortKey = k;
			asc = k === 'name' || k === 'type' || k === 'dept' || k === 'payback';
		}
	}

	const cols = $derived<{ k: Key; label: string; num?: boolean }[]>([
		{ k: 'name', label: 'Об’єкт' },
		{ k: 'dept', label: 'Розпорядник' },
		{ k: 'month', label: 'кВт·год/міс', num: true },
		...(restricted ? [] : [{ k: 'k' as Key, label: 'Покриття сонцем' }]),
		{ k: 'gen', label: 'Згенеровано', num: true },
		{ k: 'cons', label: 'Спожито', num: true },
		{ k: 'saved', label: 'Заощаджено/рік', num: true },
		{ k: 'payback', label: 'Окупність', num: true }
	]);

	function years(v: number | null): string {
		if (v == null || !isFinite(v)) return '—';
		return `${v.toLocaleString('uk-UA', { maximumFractionDigits: 1 })} р.`;
	}
	const kw = (v: number | null) => (v == null ? '—' : Math.round(v).toLocaleString('uk-UA'));
	const open = (id: number) => goto(`/object/${id}`);
</script>

<svelte:head><title>Об’єкти — Енергоменеджмент Полтави</title></svelte:head>

<div class="pg">
	<header class="hd">
		<h1>Об’єкти <span class="n">{rows.length}{#if data && rows.length !== items.length}<small> з {items.length}</small>{/if}</span></h1>
		<div class="side">
			{#if data?.demo || data?.mock}<span class="demo" title={data?.mock ? 'Тимчасовий макет: K випадкові' : 'Реєстр СЕС — демо-дані'}>ДЕМО</span>{/if}
			{#if restricted}<a class="lock" href="/login?next=/objects">🔒 Ефективність СЕС — після входу</a>{/if}
			<a class="tomap" href="/">← Мапа</a>
		</div>
	</header>

	<div class="filters">
		<SesFilters {items} bind:period bind:classes bind:types bind:q bind:department bind:need bind:season {restricted} />
	</div>

	{#if error && !data}
		<div class="state err" role="alert">{error} <button type="button" onclick={() => load(period, season)}>Повторити</button></div>
	{:else if !data}
		<div class="skel" aria-busy="true" aria-label="Завантаження">
			{#each Array(8) as _, i (i)}<div style="animation-delay: {i * 80}ms"></div>{/each}
		</div>
	{:else}
		<p class="unit" aria-hidden="true">кВт·год {period === 'day' ? 'за день' : period === 'month' ? 'за місяць' : 'за рік'}</p>
		<div class="tbl-wrap" class:dim={loading}>
			<table>
				<thead>
					<tr>
						{#each cols as c (c.k)}
							<th
								class:num={c.num}
								aria-sort={sortKey === c.k ? (asc ? 'ascending' : 'descending') : undefined}
								scope="col"
							>
								<button type="button" onclick={() => sortBy(c.k)}>
									{c.label}{#if c.k === 'gen' || c.k === 'cons'}<small> кВт·год</small>{/if}
									<span class="ar" class:on={sortKey === c.k} aria-hidden="true">{sortKey === c.k && asc ? '▲' : '▼'}</span>
								</button>
							</th>
						{/each}
					</tr>
				</thead>
				<tbody use:revealRows>
					{#each shown as r (r.id)}
						<tr onclick={() => open(r.id)} animate:flip={{ duration: flipDur }} in:listIn out:listOut>
							<td class="name">
								<a href="/object/{r.id}" onclick={(e) => e.stopPropagation()}>{r.name}</a>
								<span class="type"><CategoryIcon category={r.category_short} size={13} />{catLabel(r.category_short)}</span>
							</td>
							<td class="dept">{r.department ?? '—'}</td>
							<td class="num">{kwhMonth(r.cons_kwh_month_avg)}</td>
							{#if !restricted}<td class="kc"><KBadge k={r.k} cls={r.k_class} size="sm" /></td>{/if}
							<td class="num">{kw(r.gen_kwh)}</td>
							<td class="num">{kw(r.cons_kwh)}</td>
							<td class="num">{uah(r.saved_uah_year)}</td>
							<td class="num">{years(r.payback_years)}</td>
						</tr>
					{:else}
						<tr class="empty"><td colspan={cols.length}>Нічого не знайдено</td></tr>
					{/each}
				</tbody>
			</table>
		</div>

		<!-- Телефон: компактні рядки -->
		<ul class="cards" class:dim={loading} use:revealRows>
			{#each shown as r (r.id)}
				<li animate:flip={{ duration: flipDur }} in:listIn out:listOut>
					<a href="/object/{r.id}">
						<span class="t1">
							<span class="nm">{r.name}</span>
							{#if !restricted}<KBadge k={r.k} cls={r.k_class} size="sm" showWord={false} />{/if}
						</span>
						<span class="t2">
							<span class="type"><CategoryIcon category={r.category_short} size={12} />{catLabel(r.category_short)}</span>
							<span class="nn"><i aria-hidden="true">≈</i>{kwhMonth(r.cons_kwh_month_avg)}/міс <i title="Генерація"><Icon name="sun" size={12} /><span class="visually-hidden">генерація</span></i>{kw(r.gen_kwh)} <i title="Споживання"><Icon name="bolt" size={12} /><span class="visually-hidden">споживання</span></i>{kw(r.cons_kwh)}</span>
						</span>
					</a>
				</li>
			{:else}
				<li class="empty">Нічого не знайдено</li>
			{/each}
		</ul>
		{#if rows.length > limit}
			<div class="more" use:more>
				<button type="button" class="press" onclick={() => (limit += STEP)}>Показати ще ({rows.length - limit})</button>
			</div>
		{/if}
	{/if}
</div>

<style>
	.pg {
		padding: 0 0 32px;
	}
	.more {
		display: flex;
		justify-content: center;
		padding: 12px 0;
	}
	.more button {
		border: 1px solid var(--line);
		background: var(--surface);
		border-radius: var(--radius-sm);
		padding: 0.45rem 1rem;
		font: inherit;
		color: var(--text-2);
		cursor: pointer;
	}
	.more button:hover {
		border-color: var(--card-line-hover);
	}
	.hd {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		flex-wrap: wrap;
		margin-bottom: 12px;
	}
	h1 {
		margin: 0;
		font-size: 1.6rem;
		color: #0f1b2d;
		display: flex;
		align-items: baseline;
		gap: 10px;
	}
	.n {
		font-size: 1rem;
		font-weight: 700;
		color: #fff;
		background: #0f2f52;
		padding: 2px 10px;
		border-radius: var(--r-pill);
		font-variant-numeric: tabular-nums;
	}
	.n small {
		font-weight: 500;
		opacity: 0.8;
	}
	.side {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: 0.85rem;
	}
	.tomap {
		font-weight: 700;
		color: var(--accent, #0b5cad);
		text-decoration: none;
	}
	.lock {
		padding: 4px 10px;
		border-radius: var(--r-pill);
		background: #0f2f52;
		color: #fff;
		text-decoration: none;
		font-weight: 600;
		font-size: 0.8rem;
	}
	.demo {
		padding: 2px 8px;
		border-radius: var(--r-pill);
		background: #fdf1df;
		color: #8a4b00;
		font-weight: 700;
		font-size: 0.7rem;
	}
	.filters {
		position: sticky;
		top: var(--sticky-top, 0px);
		z-index: 5;
		background: #fff;
		border-radius: var(--r-card);
		padding: 8px;
		box-shadow: 0 1px 2px rgba(15, 35, 65, 0.05), 0 8px 24px -14px rgba(15, 35, 65, 0.2);
		margin-bottom: 8px;
	}
	.unit {
		margin: 6px 4px;
		font-size: 0.75rem;
		color: #4f5b6b;
		text-align: right;
	}
	.tbl-wrap {
		background: #fff;
		border-radius: var(--r-card);
		box-shadow: 0 1px 2px rgba(15, 35, 65, 0.05), 0 8px 24px -14px rgba(15, 35, 65, 0.2);
		overflow: hidden;
		transition: opacity 0.4s;
	}
	.dim {
		opacity: 0.55;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.88rem;
	}
	th {
		text-align: left;
		background: #f6f8fb;
		border-bottom: 1px solid #e6ebf1;
		padding: 0;
		font-weight: 700;
		position: sticky;
		top: 0;
	}
	th button {
		all: unset;
		box-sizing: border-box;
		display: flex;
		gap: 4px;
		align-items: center;
		width: 100%;
		padding: 10px 12px;
		cursor: pointer;
		color: #36425a;
		font-size: 0.78rem;
		white-space: nowrap;
	}
	th.num button {
		justify-content: flex-end;
	}
	th button:focus-visible {
		outline: 3px solid var(--focus, #ffbf47);
		outline-offset: -3px;
	}
	th small {
		font-weight: 500;
		color: #4f5b6b;
	}
	.ar {
		font-size: 0.6rem;
		opacity: 0.25;
	}
	.ar.on {
		opacity: 1;
		color: #0b5cad;
	}
	td {
		padding: 8px 12px;
		border-bottom: 1px solid #eef1f5;
		vertical-align: middle;
	}
	tbody tr {
		cursor: pointer;
		transition: background var(--dur-fast) var(--ease-out);
	}
	tbody tr:hover {
		background: #f3f7fc;
	}
	tbody tr:active {
		background: #e8f0fa;
	}
	.num {
		text-align: right;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
		font-weight: 600;
		color: #1a2433;
	}
	.name a {
		color: #0f1b2d;
		font-weight: 650;
		text-decoration: none;
	}
	.name a:hover {
		text-decoration: underline;
	}
	.name a:focus-visible,
	.cards a:focus-visible {
		outline: 3px solid var(--focus, #ffbf47);
		outline-offset: 2px;
		border-radius: var(--r-sm);
	}
	.type {
		display: flex;
		align-items: center;
		gap: 4px;
		font-size: 0.72rem;
		color: #4f5b6b;
		margin-top: 2px;
	}
	.dept {
		font-size: 0.78rem;
		color: #36425a;
		max-width: 180px;
	}
	.kc {
		white-space: nowrap;
	}
	.empty td,
	li.empty {
		text-align: center;
		color: #4f5b6b;
		padding: 28px;
		cursor: default;
	}
	.cards {
		display: none;
		list-style: none;
		margin: 0;
		padding: 0;
		background: #fff;
		border-radius: var(--r-card);
		overflow: hidden;
		box-shadow: 0 1px 2px rgba(15, 35, 65, 0.05), 0 8px 24px -14px rgba(15, 35, 65, 0.2);
	}
	.cards li {
		border-bottom: 1px solid #eef1f5;
	}
	.cards a {
		display: flex;
		flex-direction: column;
		gap: 3px;
		padding: 10px 12px;
		text-decoration: none;
		color: inherit;
	}
	.cards a:active {
		background: #f3f7fc;
	}
	.t1,
	.t2 {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 8px;
	}
	.nm {
		font-weight: 650;
		font-size: 0.9rem;
		color: #0f1b2d;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
	}
	.nn {
		font-size: 0.75rem;
		color: #36425a;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
	.nn i {
		font-style: normal;
		margin: 0 2px 0 6px;
	}
	.state {
		padding: 20px;
		background: #fbe9e8;
		color: #a3201c;
		border-radius: var(--r-card);
	}
	.skel {
		display: grid;
		gap: 6px;
	}
	.skel div {
		height: 44px;
		border-radius: var(--r-card);
		background: linear-gradient(90deg, #eef1f5, #f8fafc, #eef1f5);
		background-size: 200% 100%;
		animation: sh 1.2s infinite linear;
	}
	@keyframes sh {
		to {
			background-position: -200% 0;
		}
	}
	@media (max-width: 760px) {
		.tbl-wrap {
			display: none;
		}
		.cards {
			display: block;
		}
		h1 {
			font-size: 1.3rem;
		}
		.unit {
			display: none;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		tbody tr,
		.cards li,
		.skel div {
			animation: none;
		}
	}
</style>
