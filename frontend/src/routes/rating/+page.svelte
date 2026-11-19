<script lang="ts">
	// Сторінка «Рейтинг будівель»: у межах категорії, 1 = найменш ефективна (найбільше кВт·год/м²)
	import { page } from '$app/state';
	import { api, errMessage, type Building, type Summary } from '#lib/api.ts';
	import { num } from '#lib/format.ts';
	import ClassBadge from '#lib/ClassBadge.svelte';
	import Status from '#lib/Status.svelte';

	let buildings = $state<Building[]>([]);
	let summary = $state<Summary | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);
	let query = $state('');

	async function load() {
		loading = true;
		error = null;
		try {
			// Беремо всі будівлі одним запитом і фільтруємо категорію на клієнті — вкладки перемикаються миттєво
			[buildings, summary] = await Promise.all([api.buildings(), api.summary()]);
		} catch (e) {
			error = errMessage(e);
		} finally {
			loading = false;
		}
	}
	load();

	const baseYear = $derived(summary?.base_year ? String(summary.base_year) : '2025');
	// Категорії: найбільші першими
	const categories = $derived(
		summary ? Object.entries(summary.categories).sort((a, b) => b[1].count - a[1].count) : []
	);
	// Активна вкладка зберігається в адресі (?cat=…), щоб працювала кнопка «Назад»
	const current = $derived(page.url.searchParams.get('cat') || categories[0]?.[0] || '');
	const median = $derived(summary?.categories[current]?.median_kwh_m2 ?? null);

	function matches(b: Building, q: string): boolean {
		if (!q) return true;
		const s = q.toLocaleLowerCase('uk');
		return b.name.toLocaleLowerCase('uk').includes(s) || b.address.toLocaleLowerCase('uk').includes(s);
	}

	const inCat = $derived(buildings.filter((b) => b.category_short === current));
	const rated = $derived(
		inCat
			.filter((b) => b.in_rating && matches(b, query.trim()))
			.sort((a, b) => (a.rank ?? 1e9) - (b.rank ?? 1e9))
	);
	const excluded = $derived(inCat.filter((b) => !b.in_rating && matches(b, query.trim())));
	const totalRated = $derived(inCat.filter((b) => b.in_rating).length);
	const totalExcluded = $derived(inCat.filter((b) => !b.in_rating).length);
</script>

<svelte:head><title>Рейтинг будівель · City Insight Map · Енергія</title></svelte:head>

<div class="page-head">
	<div>
		<h1>Рейтинг будівель</h1>
		<p class="lead">
			Порівнюємо будівлі однієї категорії за питомим споживанням енергії за {baseYear} рік (тепло,
			електроенергія й газ на 1 м² опалюваної площі). Місце <strong>1 — найменш ефективна</strong> будівля:
			з неї варто почати енергоаудит.
		</p>
	</div>
</div>

<Status {loading} {error} retry={load} />

{#if summary && !loading}
	<nav class="tabs" aria-label="Категорії будівель">
		{#each categories as [name, c] (name)}
			<a
				href="?cat={encodeURIComponent(name)}"
				aria-current={name === current ? 'page' : undefined}
				data-sveltekit-reset="false"
				data-sveltekit-replacestate
			>
				{name} <span class="count">{c.in_rating}</span>
			</a>
		{/each}
	</nav>

	<div class="toolbar">
		<div class="field">
			<label for="q">Пошук за назвою або адресою</label>
			<input id="q" type="search" bind:value={query} placeholder="Наприклад: школа № 1" size="34" />
		</div>
		<p class="muted meta">
			Медіана категорії «{current}»: <strong>{num(median, 1)} кВт·год/м²</strong>.
			Показано {rated.length} з {totalRated} будівель у рейтингу.
		</p>
	</div>

	<div class="table-wrap">
		<table>
			<caption>
				Рейтинг: {current}, {baseYear} рік
				<span class="muted">— відсортовано від найбільшого питомого споживання до найменшого</span>
			</caption>
			<thead>
				<tr>
					<th scope="col" class="num">Місце</th>
					<th scope="col">Назва</th>
					<th scope="col">Адреса</th>
					<th scope="col" class="num">Питоме, <span class="unit">кВт·год/м²</span></th>
					<th scope="col" class="num">× медіани</th>
					<th scope="col">Клас (умовний)</th>
					<th scope="col" class="num">Дефекти даних</th>
				</tr>
			</thead>
			<tbody>
				{#each rated as b (b.id)}
					<tr>
						<td class="num">{b.rank}<span class="muted small"> / {b.rank_of}</span></td>
						<td class="name"><a href="/building/{b.id}">{b.name}</a></td>
						<td>{b.address}</td>
						<td class="num">{num(b.years[baseYear]?.kwh_m2, 1)}</td>
						<td class="num">{num(b.ratio_to_median, 2)}</td>
						<td><ClassBadge cls={b.eff_class} /></td>
						<td class="num">
							{#if b.defects_count}
								<span class="pill pill-warn">{b.defects_count}</span>
							{:else}
								<span class="muted">0</span>
							{/if}
						</td>
					</tr>
				{:else}
					<tr><td colspan="7" class="muted">Нічого не знайдено.</td></tr>
				{/each}
			</tbody>
		</table>
	</div>

	<details class="card excluded">
		<summary>
			Виключено з рейтингу — будівель: {excluded.length}{query.trim() ? ` з ${totalExcluded}` : ''}
			<span class="muted">(показуємо з причиною, а не приховуємо)</span>
		</summary>
		<p class="muted small">
			Ці будівлі не порівнюються з іншими, доки не виправлено дані в UMUNI. Причини й поради — у
			картці будівлі та на сторінці <a href="/defects">«Якість даних»</a>.
		</p>
		<div class="table-wrap">
			<table>
				<caption class="visually-hidden">Будівлі, виключені з рейтингу, і причини</caption>
				<thead>
					<tr>
						<th scope="col">Назва</th>
						<th scope="col">Адреса</th>
						<th scope="col">Причина виключення</th>
						<th scope="col" class="num">Дефекти даних</th>
					</tr>
				</thead>
				<tbody>
					{#each excluded as b (b.id)}
						<tr>
							<td class="name"><a href="/building/{b.id}">{b.name}</a></td>
							<td>{b.address}</td>
							<td>{b.excluded_reason ?? '—'}</td>
							<td class="num">{b.defects_count ?? 0}</td>
						</tr>
					{:else}
						<tr><td colspan="4" class="muted">Немає виключених будівель.</td></tr>
					{/each}
				</tbody>
			</table>
		</div>
	</details>
{/if}

<style>
	.tabs {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		margin-bottom: 1rem;
		border-bottom: 2px solid var(--line);
	}
	.tabs a {
		padding: 0.55rem 0.9rem;
		border: 1px solid var(--line);
		border-bottom: none;
		border-radius: 6px 6px 0 0;
		background: #eef2f6;
		color: var(--text);
		text-decoration: none;
		font-weight: 500;
		margin-bottom: -2px;
	}
	.tabs a:hover {
		background: var(--accent-soft);
	}
	.tabs a[aria-current='page'] {
		background: var(--surface);
		border-color: var(--accent);
		border-bottom: 2px solid var(--surface);
		font-weight: 700;
		color: var(--accent-dark);
	}
	.count {
		display: inline-block;
		min-width: 1.6em;
		padding: 0 0.35em;
		border-radius: 999px;
		background: #fff;
		border: 1px solid var(--line-strong);
		font-size: 0.8rem;
		text-align: center;
	}
	.meta {
		margin: 0 0 0.4rem;
	}
	.excluded {
		margin-top: 1.25rem;
	}
	.excluded summary {
		margin-bottom: 0.5rem;
	}
</style>
