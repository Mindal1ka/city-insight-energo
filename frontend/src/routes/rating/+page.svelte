<script lang="ts">
	// Рейтинг будівель за питомим споживанням електроенергії (кВт·год/м² за рік) у межах категорії.
	// 1 = найбільше споживає на 1 м² — з неї варто почати енергоаудит.
	import { page } from '$app/state';
	import { api, errMessage, type Building } from '#lib/api.ts';
	import { num } from '#lib/format.ts';
	import ClassBadge from '#lib/ClassBadge.svelte';
	import Status from '#lib/Status.svelte';
	import Skeleton from '#lib/Skeleton.svelte';
	import Term from '#lib/Term.svelte';
	import { electricityRating, ratioWords, BASE_YEAR, type ElecRow } from './electricity.ts';

	let buildings = $state<Building[]>([]);
	let error = $state<string | null>(null);
	let loading = $state(true);
	let query = $state('');

	async function load() {
		loading = true;
		error = null;
		try {
			buildings = await api.buildings();
		} catch (e) {
			error = errMessage(e);
		} finally {
			loading = false;
		}
	}
	load();

	const rating = $derived(electricityRating(buildings));
	const categories = $derived(
		Object.entries(rating.byCategory)
			.map(([name, list]) => ({ name, total: list.length, rated: list.filter((r) => !r.excluded).length }))
			.sort((a, b) => b.total - a.total)
	);
	const current = $derived(page.url.searchParams.get('cat') || categories[0]?.name || '');
	const median = $derived(rating.medians[current] ?? null);

	function matches(r: ElecRow, q: string): boolean {
		if (!q) return true;
		const s = q.toLocaleLowerCase('uk');
		return r.b.name.toLocaleLowerCase('uk').includes(s) || r.b.address.toLocaleLowerCase('uk').includes(s);
	}

	const inCat = $derived(rating.byCategory[current] ?? []);
	const rated = $derived(
		inCat.filter((r) => !r.excluded && matches(r, query.trim())).sort((a, b) => a.rank! - b.rank!)
	);
	const excluded = $derived(inCat.filter((r) => r.excluded && matches(r, query.trim())));
	const totalRated = $derived(inCat.filter((r) => !r.excluded).length);
	const totalExcluded = $derived(inCat.length - totalRated);
	// Шкала для міні-барів: найбільше значення в категорії
	const scaleMax = $derived(Math.max(1, ...inCat.filter((r) => !r.excluded).map((r) => r.kwhM2 ?? 0)));
</script>

<svelte:head><title>Рейтинг будівель · City Insight Map · Енергія</title></svelte:head>

<div class="page-head">
	<div>
		<h1>Рейтинг будівель за електроенергією</h1>
		<p class="lead">
			Порівнюємо схожі будівлі (школи зі школами, садочки із садочками) за тим, скільки електроенергії
			вони спожили за {BASE_YEAR} рік на кожен квадратний метр. <strong>Місце 1</strong> — будівля, що
			споживає найбільше на 1 м²: з неї варто почати перевірку.
		</p>
	</div>
</div>

<details class="card how no-print">
	<summary>Як читати рейтинг</summary>
	<ul>
		<li>
			<Term key="питоме споживання">Питоме споживання</Term> = електроенергія за рік ÷ площа будівлі.
			Школа 2 000 м², що спожила 40 000 кВт·год, має 20 кВт·год/м².
		</li>
		<li>
			<Term key="медіана категорії" /> — типове значення для будівель цієї категорії: половина
			споживає більше, половина — менше.
		</li>
		<li>
			<Term key="умовний клас">Умовний клас A–G</Term> показує, наскільки будівля відрізняється від
			медіани: A — значно економніша, D — на рівні, G — більш ніж удвічі більше.
		</li>
		<li>
			Будівлі з неповними чи сумнівними даними не ранжуємо, а показуємо нижче з причиною — щоб їх
			виправили в <Term key="UMUNI" />.
		</li>
	</ul>
</details>

{#if loading}
	<Skeleton variant="table" rows={10} />
{/if}
<Status loading={false} {error} retry={load} />

{#if !loading && !error}
	{#if !categories.length}
		<div class="empty">
			<p><strong>Даних поки немає.</strong> Завантажте вивантаження з UMUNI на сторінці «Оновити дані».</p>
			<a class="btn" href="/upload">Оновити дані</a>
		</div>
	{:else}
		<nav class="tabs" aria-label="Категорії будівель">
			{#each categories as c (c.name)}
				<a
					href="?cat={encodeURIComponent(c.name)}"
					aria-current={c.name === current ? 'page' : undefined}
					data-sveltekit-reset="false"
					data-sveltekit-replacestate
					data-sveltekit-noscroll
				>
					{c.name} <span class="count">{c.rated}</span>
				</a>
			{/each}
		</nav>

		<div class="toolbar">
			<div class="field">
				<label for="q">Пошук за назвою або адресою</label>
				<input id="q" type="search" bind:value={query} placeholder="Наприклад: гімназія № 3" size="34" />
			</div>
			<p class="meta">
				<span class="med">
					<Term key="медіана категорії">Медіана</Term> «{current}»:
					<strong>{num(median, 1)} кВт·год/м²</strong>
				</span>
				<span class="muted">Показано {rated.length} з {totalRated} будівель у рейтингу.</span>
			</p>
		</div>

		<div class="table-wrap tall">
			<table>
				<caption>
					{current}, {BASE_YEAR} рік
					<span class="muted">— від найбільшого споживання на 1 м² до найменшого</span>
				</caption>
				<thead>
					<tr>
						<th scope="col" class="num">Місце</th>
						<th scope="col">Будівля</th>
						<th scope="col" class="num">Електроенергія за рік, <span class="unit">кВт·год</span></th>
						<th scope="col" class="num">
							<Term key="питоме споживання">На 1 м²</Term>, <span class="unit">кВт·год/м²</span>
						</th>
						<th scope="col">Порівняно з медіаною</th>
						<th scope="col"><Term key="умовний клас">Клас</Term></th>
					</tr>
				</thead>
				<tbody>
					{#each rated as r (r.b.id)}
						<tr>
							<td class="num rank">{r.rank}<span class="muted small"> / {r.rankOf}</span></td>
							<td class="name">
								<a href="/object/{r.b.id}">{r.b.name}</a>
								<span class="addr">{r.b.address}</span>
							</td>
							<td class="num">{num(r.kwh)}</td>
							<td class="num">
								<span class="bar-cell">
									<strong>{num(r.kwhM2, 1)}</strong>
									<span class="mini" aria-hidden="true">
										<span class="fill cls-{r.cls}" style="width:{((r.kwhM2 ?? 0) / scaleMax) * 100}%"></span>
										{#if median}<span class="tick" style="left:{(median / scaleMax) * 100}%"></span>{/if}
									</span>
								</span>
							</td>
							<td class="nowrap">{ratioWords(r.ratio)}</td>
							<td><ClassBadge cls={r.cls} short /></td>
						</tr>
					{:else}
						<tr><td colspan="6" class="empty-cell">Нічого не знайдено за «{query.trim()}».</td></tr>
					{/each}
				</tbody>
			</table>
		</div>
		<p class="muted small legend">
			Смужка показує споживання на 1 м²; вертикальна риска — медіана категорії. Клас — аналітична
			оцінка відносно схожих будівель, а не офіційний енергосертифікат.
		</p>

		<details class="card excluded">
			<summary>
				Виключено з рейтингу — будівель: {excluded.length}{query.trim() ? ` з ${totalExcluded}` : ''}
				<span class="muted">(показуємо з причиною, а не приховуємо)</span>
			</summary>
			<p class="muted small">
				Ці будівлі не порівнюються з іншими, доки дані в UMUNI не виправлено. Деталі — на сторінці
				<a href="/defects">«Якість даних»</a>.
			</p>
			<div class="table-wrap">
				<table>
					<caption class="visually-hidden">Будівлі, виключені з рейтингу, і причини</caption>
					<thead>
						<tr>
							<th scope="col">Будівля</th>
							<th scope="col">Причина</th>
							<th scope="col" class="num">Електроенергія, <span class="unit">кВт·год</span></th>
							<th scope="col" class="num">Площа, <span class="unit">м²</span></th>
						</tr>
					</thead>
					<tbody>
						{#each excluded as r (r.b.id)}
							<tr>
								<td class="name">
									<a href="/object/{r.b.id}">{r.b.name}</a>
									<span class="addr">{r.b.address}</span>
								</td>
								<td>{r.excluded}</td>
								<td class="num">{num(r.kwh)}</td>
								<td class="num">{num(r.b.heated_area, 1)}</td>
							</tr>
						{:else}
							<tr><td colspan="4" class="empty-cell">Немає виключених будівель.</td></tr>
						{/each}
					</tbody>
				</table>
			</div>
		</details>
	{/if}
{/if}

<style>
	.how {
		padding: 0.9rem 1.25rem;
	}
	.how ul {
		margin: 0.6rem 0 0;
		padding-left: 1.2rem;
		display: grid;
		gap: 0.35rem;
	}
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
		border-radius: 8px 8px 0 0;
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
		display: flex;
		flex-direction: column;
		margin: 0 0 0.2rem;
	}
	.med {
		font-size: 1.05rem;
	}
	.rank {
		font-weight: 700;
	}
	.addr {
		display: block;
		font-size: 0.875rem;
		color: var(--muted);
	}
	.bar-cell {
		display: inline-flex;
		align-items: center;
		gap: 0.6rem;
	}
	.bar-cell strong {
		min-width: 3.2em;
	}
	.mini {
		position: relative;
		display: inline-block;
		width: 7rem;
		height: 0.6rem;
		border-radius: 4px;
		background: #eef2f6;
	}
	.fill {
		position: absolute;
		inset: 0 auto 0 0;
		border-radius: 4px;
		background: var(--c-fg, var(--accent));
		opacity: 0.85;
	}
	.tick {
		position: absolute;
		top: -3px;
		bottom: -3px;
		width: 2px;
		background: var(--text);
	}
	.legend {
		margin-top: 0.5rem;
	}
	.excluded {
		margin-top: 1.25rem;
	}
	.excluded summary {
		margin-bottom: 0.5rem;
	}
	@media (max-width: 760px) {
		.mini {
			display: none;
		}
	}
</style>
