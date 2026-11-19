<script lang="ts">
	// Рейтинг будівель за питомим споживанням електроенергії (кВт·год/м² за рік) у межах категорії.
	// 1 = найбільше споживає на 1 м² — з неї варто почати енергоаудит.
	// Список, а не широка таблиця: 4 зрозумілі колонки, решта — у розгортанні рядка.
	import { page } from '$app/state';
	import { flip } from 'svelte/animate';
	import { api, errMessage, type Building } from '#lib/api.ts';
	import { num, kwhText, plural } from '#lib/format.ts';
	import { classInfo, CLASSES } from '#lib/classes.ts';
	import { catLabel } from '#lib/categories.ts';
	import ClassBadge from '#lib/ClassBadge.svelte';
	import Status from '#lib/Status.svelte';
	import Skeleton from '#lib/Skeleton.svelte';
	import Term from '#lib/Term.svelte';
	import StatCard from '#lib/StatCard.svelte';
	import Reveal from '#lib/Reveal.svelte';
	import Disclosure from '#lib/Disclosure.svelte';
	import Icon from '#lib/Icon.svelte';
	import { fadeUp, stagger, reducedMotion } from '#lib/motion.ts';
	import { electricityRating, ratioWords, BASE_YEAR, type ElecRow } from './electricity.ts';
	import { grow } from './grow.ts';

	let buildings = $state<Building[]>([]);
	let error = $state<string | null>(null);
	let loading = $state(true);
	let query = $state('');
	type SortKey = 'most' | 'least' | 'name';
	let sort = $state<SortKey>('most');
	let expanded = $state<number | null>(null);
	// Довгий список показуємо не весь одразу: спершу верхівку рейтингу
	const FIRST = 15;
	let showAll = $state(false);

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

	const SORTS: { key: SortKey; label: string }[] = [
		{ key: 'most', label: 'Найбільше на 1 м²' },
		{ key: 'least', label: 'Найменше на 1 м²' },
		{ key: 'name', label: 'За назвою' }
	];

	const inCat = $derived(rating.byCategory[current] ?? []);
	const rated = $derived.by(() => {
		const list = inCat.filter((r) => !r.excluded && matches(r, query.trim()));
		if (sort === 'name') return list.sort((a, b) => a.b.name.localeCompare(b.b.name, 'uk'));
		if (sort === 'least') return list.sort((a, b) => b.rank! - a.rank!);
		return list.sort((a, b) => a.rank! - b.rank!);
	});
	const visible = $derived(showAll || query.trim() ? rated : rated.slice(0, FIRST));
	const excluded = $derived(inCat.filter((r) => r.excluded));
	const totalRated = $derived(inCat.filter((r) => !r.excluded).length);
	const muchMore = $derived(inCat.filter((r) => !r.excluded && (r.ratio ?? 0) > 1.5).length);
	// Шкала для смужок: найбільше значення в категорії
	const scaleMax = $derived(Math.max(1, ...inCat.filter((r) => !r.excluded).map((r) => r.kwhM2 ?? 0)));

	const flipMs = $derived(reducedMotion.current ? 0 : 380);

	function toggle(id: number) {
		expanded = expanded === id ? null : id;
	}

	/** Колір смужки за умовним класом: лише допоміжний, поряд завжди є літера й текст */
	function tone(cls: string | null): string {
		if (!cls) return 'mid';
		if ('AB'.includes(cls)) return 'good';
		if ('CD'.includes(cls)) return 'mid';
		return 'bad';
	}
</script>

<svelte:head><title>Рейтинг будівель · Insight Tool</title></svelte:head>

<div class="page-head">
	<div>
		<h1>Рейтинг будівель</h1>
	</div>
</div>

<Reveal>
	<p class="formula" aria-label="Як рахуємо: електрика за рік поділити на площу будівлі дорівнює кіловат-годин на один квадратний метр">
		<span class="f-part"><Icon name="bolt" size={18} /> електрика за рік</span>
		<span class="f-op" aria-hidden="true">÷</span>
		<span class="f-part"><Icon name="building" size={18} /> площа будівлі</span>
		<span class="f-op" aria-hidden="true">=</span>
		<span class="f-part f-res"><Term key="питоме споживання" plain>кВт·год на 1 м²</Term></span>
	</p>
</Reveal>

{#if loading}
	<Skeleton variant="page" count={3} rows={10} />
{/if}
<Status loading={false} {error} retry={load} />

{#if !loading && !error}
	{#if !categories.length}
		<div class="empty">
			<p><strong>Даних поки немає.</strong> Завантажте вивантаження з UMUNI на сторінці «Оновити дані».</p>
			<a class="btn" href="/upload">Оновити дані</a>
		</div>
	{:else}
		<nav class="seg cats" aria-label="Тип будівель">
			{#each categories as c (c.name)}
				<a
					href="?cat={encodeURIComponent(c.name)}"
					aria-current={c.name === current ? 'page' : undefined}
					data-sveltekit-reset="false"
					data-sveltekit-replacestate
					onclick={() => {
						expanded = null;
						showAll = false;
						query = '';
					}}
				>
					<span title={c.name}>{catLabel(c.name)}</span> <span class="count">{c.rated}</span>
				</a>
			{/each}
		</nav>

		<section aria-label="Головне про категорію «{current}»" class="stats">
			<Reveal>
				<StatCard
					label="Будівель у рейтингу"
					value={totalRated}
					icon="building"
					hint="«{current}», {BASE_YEAR} рік."
				/>
			</Reveal>
			<Reveal delay={70}>
				<StatCard
					label="Типово для категорії"
					value={median}
					decimals={1}
					unit="кВт·год/м²"
					icon="gauge"
					hint="Половина будівель цієї категорії витрачає більше, половина — менше."
				/>
			</Reveal>
			<Reveal delay={140}>
				<StatCard
					label="Витрачають набагато більше"
					value={muchMore}
					icon="alert"
					tone={muchMore ? 'bad' : 'good'}
					toneLabel={muchMore ? 'потрібна перевірка' : 'таких немає'}
					hint="У півтора раза й більше понад типове — перші кандидати на енергоаудит."
				/>
			</Reveal>
			{#if excluded.length}
				<Reveal delay={210}>
					<StatCard
						label="Не потрапили в рейтинг"
						value={excluded.length}
						icon="info"
						tone="warn"
						toneLabel="помилки в даних"
						href="#excluded"
						hint="Неповні чи сумнівні дані."
					/>
				</Reveal>
			{/if}
		</section>

		<div class="toolbar">
			<div class="field search">
				<label for="q">Знайти будівлю</label>
				<input id="q" type="search" bind:value={query} placeholder="Назва або адреса" />
			</div>
			<div class="field">
				<span class="lbl" id="sort-l">Порядок</span>
				<div class="seg" role="group" aria-labelledby="sort-l">
					{#each SORTS as s (s.key)}
						<button type="button" aria-pressed={sort === s.key} onclick={() => (sort = s.key)}>
							{s.label}
						</button>
					{/each}
				</div>
			</div>
			<p class="muted shown" aria-live="polite">
				Показано {visible.length} з {totalRated}
			</p>
		</div>

		<div class="list-card">
			<div class="list-head" aria-hidden="true">
				<span>№ у черзі</span>
				<span>Будівля</span>
				<span>Витрачає на 1 м² за рік</span>
				<span>Порівняно з типовою</span>
				<span></span>
			</div>
			{#key current}
				<ol class="rows" {@attach grow} aria-label="{current}: рейтинг за споживанням на 1 м²">
					{#each visible as r, i (r.b.id)}
						{@const open = expanded === r.b.id}
						{@const info = classInfo(r.cls)}
						<li
							class="row"
							class:open
							animate:flip={{ duration: flipMs }}
							in:fadeUp|global={{ delay: stagger(i, 22, 450) }}
						>
							<span class="rank tnum" title="№ {r.rank} з {r.rankOf} у черзі на перевірку">
								<span class="visually-hidden">№ у черзі на перевірку</span>{r.rank}
							</span>
							<span class="name">
								<a href="/building/{r.b.id}">{r.b.name}</a>
							</span>
							<span class="val">
								<span class="v tnum"><strong>{num(r.kwhM2, 1)}</strong> <span class="unit">кВт·год/м²</span></span>
								<span class="mini" aria-hidden="true">
									<span class="fill t-{tone(r.cls)}" style="width:{((r.kwhM2 ?? 0) / scaleMax) * 100}%; --i:{Math.min(i, 14)}"></span>
									{#if median}<span class="tick" style="left:{(median / scaleMax) * 100}%"></span>{/if}
								</span>
							</span>
							<span class="cmp">
								<ClassBadge cls={r.cls} short />
								<span class="cmp-txt">{ratioWords(r.ratio)}</span>
							</span>
							<button
								type="button"
								class="more"
								aria-expanded={open}
								aria-controls="det-{r.b.id}"
								onclick={() => toggle(r.b.id)}
							>
								<span class="visually-hidden">Детальніше про «{r.b.name}»</span>
								<svg width="16" height="16" viewBox="0 0 14 14" aria-hidden="true"
									><path d="M3 5.25 7 9.25l4-4" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" /></svg
								>
							</button>
							{#if open}
								<div class="details" id="det-{r.b.id}" in:fadeUp={{ y: -6 }}>
									<dl>
										<div><dt>Адреса</dt><dd>{r.b.address || '—'}</dd></div>
										<div><dt>Електрика за {BASE_YEAR} рік</dt><dd>{kwhText(r.kwh)}</dd></div>
										<div><dt>Площа</dt><dd>{num(r.b.heated_area, 0)} м²</dd></div>
										<div class="only-phone"><dt>Порівняно з типовою</dt><dd>{ratioWords(r.ratio)}</dd></div>
										<div>
											<dt><Term key="умовний клас">Клас</Term></dt>
											<dd>{info ? `${info.letter} — ${info.text}` : '—'}</dd>
										</div>
									</dl>
									<p class="det-links">
										<a href="/building/{r.b.id}">Паспорт даних →</a>
										<a href="/object/{r.b.id}">Картка об’єкта →</a>
									</p>
								</div>
							{/if}
						</li>
					{:else}
						<li class="none">Нічого не знайдено за «{query.trim()}». <button type="button" class="linkish" onclick={() => (query = '')}>Очистити пошук</button></li>
					{/each}
				</ol>
			{/key}
			{#if rated.length > FIRST && !query.trim()}
				<div class="list-foot">
					<button type="button" class="btn btn-secondary" aria-expanded={showAll} onclick={() => (showAll = !showAll)}>
						{showAll ? `Згорнути до перших ${FIRST}` : `Показати всі ${rated.length} ${plural(rated.length, ['будівлю', 'будівлі', 'будівель'])}`}
					</button>
				</div>
			{/if}
		</div>
		<p class="muted small legend">
			<span class="lg-tick" aria-hidden="true"></span> типово: {num(median, 1)} кВт·год/м²
		</p>

		{#if excluded.length}
			<section id="excluded" class="card excl" aria-labelledby="excl-h">
				<h2 id="excl-h">Поза рейтингом: {excluded.length}</h2>
				<Disclosure summary="Показати будівлі й причини" hint={String(excluded.length)}>
					<ul class="excl-list">
						{#each excluded as r (r.b.id)}
							<li>
								<a href="/building/{r.b.id}">{r.b.name}</a>
								<span class="muted small">{r.excluded}</span>
							</li>
						{/each}
					</ul>
				</Disclosure>
			</section>
		{/if}

		<Disclosure summary="Як рахуємо" class="card soft">
			<ul class="small muted how">
				<li>Порівнюємо лише схожі будівлі (школи зі школами) за електрикою на 1 м² площі. Напр.: 2 000 м² і 40 000 кВт·год → 20 кВт·год/м².</li>
				<li>№ 1 у черзі на перевірку — найбільше на 1 м². Риска на смузі — типове (медіана) для категорії.</li>
				<li>Будівлі з неповними даними в <Term key="UMUNI" plain /> не ранжуємо — після виправлення з’являться самі.</li>
				<li>Клас — аналітична оцінка відносно схожих будівель, а не офіційний енергосертифікат:</li>
			</ul>
			<ul class="classes">
				{#each CLASSES as c (c.letter)}
					<li><ClassBadge cls={c.letter} short /> <span>{c.text}</span> <span class="muted small">({c.range})</span></li>
				{/each}
			</ul>
		</Disclosure>
	{/if}
{/if}

<style>
	.formula {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem 0.6rem;
		margin: 0 0 1.25rem;
		padding: 0.75rem 1rem;
		background: var(--surface);
		border: 1px solid #e3e8ef;
		border-radius: var(--radius);
		box-shadow: var(--shadow);
	}
	.f-part {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0.3rem 0.7rem;
		border-radius: 999px;
		background: var(--neutral-soft);
		font-weight: 600;
		font-size: 0.95rem;
	}
	.f-res {
		background: var(--sun-soft);
		color: var(--sun-ink);
	}
	.f-op {
		font-size: 1.25rem;
		font-weight: 700;
		color: var(--muted);
	}
	.f-ex {
		flex-basis: 100%;
	}
	@media (min-width: 1100px) {
		.f-ex {
			flex-basis: auto;
			margin-left: auto;
		}
	}
	.cats {
		display: flex;
		flex-wrap: wrap;
		margin-bottom: 1.25rem;
	}
	.count {
		display: inline-block;
		min-width: 1.6em;
		margin-left: 0.25rem;
		padding: 0 0.35em;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.7);
		border: 1px solid var(--line);
		font-size: 0.8rem;
		text-align: center;
	}
	.stats {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 270px), 1fr));
		gap: 1rem;
		margin-bottom: 1.5rem;
	}
	.stats > :global(.reveal) {
		display: grid;
	}
	.search {
		flex: 1 1 18rem;
		max-width: 26rem;
	}
	.search input {
		width: 100%;
	}
	.lbl {
		font-weight: 600;
		font-size: 0.9rem;
	}
	.toolbar .seg {
		display: flex;
		flex-wrap: wrap;
	}
	.shown {
		margin: 0 0 0.6rem auto;
	}
	.list-card {
		background: var(--surface);
		border: 1px solid #e3e8ef;
		border-radius: var(--radius);
		box-shadow: var(--shadow);
		overflow: hidden;
	}
	.list-head,
	.row {
		display: grid;
		grid-template-columns: 3.5rem minmax(0, 2.2fr) minmax(12rem, 1.3fr) minmax(11rem, 1fr) 2.75rem;
		gap: 0.5rem 1rem;
		align-items: center;
		padding: 0.6rem 1rem;
	}
	.list-head {
		background: var(--neutral-soft);
		font-size: 0.85rem;
		font-weight: 600;
		color: #2b3645;
		border-bottom: 1px solid var(--line);
	}
	.rows {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.row {
		position: relative;
		border-bottom: 1px solid #edf0f4;
		background: var(--surface);
		transition: background 0.15s;
	}
	.row:last-child {
		border-bottom: 0;
	}
	.row:hover,
	.row.open {
		background: #f7fafd;
	}
	.rank {
		display: grid;
		place-items: center;
		width: 2.2rem;
		height: 2.2rem;
		border-radius: 50%;
		background: var(--neutral-soft);
		font-weight: 700;
	}
	.name a {
		font-weight: 600;
	}
	.val {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
	}
	.v {
		white-space: nowrap;
	}
	.mini {
		position: relative;
		display: block;
		height: 0.55rem;
		border-radius: 999px;
		background: var(--neutral-soft);
	}
	.fill {
		position: absolute;
		inset: 0 auto 0 0;
		border-radius: 999px;
		transform-origin: left center;
	}
	.t-good {
		background: var(--cls-A);
	}
	.t-mid {
		background: var(--cls-D);
	}
	.t-bad {
		background: var(--cls-G);
	}
	@media (prefers-reduced-motion: no-preference) {
		.fill {
			transform: scaleX(0);
			transition: transform 0.7s var(--ease) calc(var(--i, 0) * 30ms + 150ms);
		}
		:global(.grown) .fill {
			transform: none;
		}
	}
	.tick {
		position: absolute;
		top: -4px;
		bottom: -4px;
		width: 2px;
		margin-left: -1px;
		background: var(--text);
		border-radius: 1px;
	}
	.cmp {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.25rem 0.5rem;
	}
	.cmp-txt {
		font-size: 0.9375rem;
	}
	.more {
		display: grid;
		place-items: center;
		width: 2.5rem;
		height: 2.5rem;
		border-radius: 50%;
		border: 1px solid var(--line);
		background: var(--surface);
		color: var(--accent);
		cursor: pointer;
		transition:
			transform 0.24s var(--ease),
			background 0.15s;
	}
	.more:hover {
		background: var(--accent-soft);
	}
	.open .more {
		transform: rotate(180deg);
		background: var(--accent-soft);
	}
	.details {
		grid-column: 2 / -1;
		padding: 0.25rem 0 0.4rem;
	}
	.details dl {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
		gap: 0.6rem 1.25rem;
		margin: 0 0 0.6rem;
	}
	.details dt {
		font-size: 0.85rem;
		color: var(--muted);
		font-weight: 600;
	}
	.details dd {
		margin: 0;
	}
	.det-links {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem 1.5rem;
		margin: 0;
		font-weight: 600;
	}
	.list-foot {
		display: flex;
		justify-content: center;
		padding: 0.85rem 1rem;
		border-top: 1px solid var(--line);
		background: #fafbfd;
	}
	.none {
		padding: 2rem 1rem;
		text-align: center;
		color: var(--muted);
	}
	.linkish {
		border: 0;
		background: none;
		padding: 0;
		font: inherit;
		color: var(--accent);
		text-decoration: underline;
		cursor: pointer;
	}
	.legend {
		margin: 0.6rem 0 1.25rem;
	}
	.lg-tick {
		display: inline-block;
		width: 2px;
		height: 0.9em;
		background: var(--text);
		vertical-align: -0.1em;
		margin-right: 0.25rem;
	}
	:global(.disc.card.soft) {
		padding: 0.25rem 1.25rem;
		margin: 0 0 1.25rem;
	}
	.classes {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.45rem;
	}
	.excl {
		scroll-margin-top: 5rem;
	}
	.excl-list {
		list-style: none;
		margin: 0 0 0.75rem;
		padding: 0;
		display: grid;
		gap: 0.65rem;
	}
	.excl-list li {
		display: flex;
		flex-direction: column;
	}
	@media (max-width: 900px) {
		.list-head {
			display: none;
		}
		.row {
			grid-template-columns: 2.6rem minmax(0, 1fr) 2.75rem;
			gap: 0.4rem 0.75rem;
			padding: 0.75rem 0.85rem;
			align-items: start;
		}
		.rank {
			grid-row: 1 / span 3;
		}
		.name {
			grid-column: 2;
		}
		.more {
			grid-column: 3;
			grid-row: 1;
		}
		.val,
		.cmp {
			grid-column: 2 / -1;
		}
		.details {
			grid-column: 1 / -1;
		}
	}
	/* Телефон: компактні ряди «місце · назва (2 рядки) | значення + смужка · клас»,
	   категорії й сортування — одна лінія з горизонтальною прокруткою */
	@media (max-width: 640px) {
		.formula {
			gap: 0.35rem 0.4rem;
			padding: 0.6rem 0.75rem;
			margin-bottom: 1rem;
		}
		.f-part {
			padding: 0.2rem 0.55rem;
			font-size: 0.8125rem;
		}
		.f-op {
			font-size: 1rem;
		}
		.f-ex {
			display: none;
		}
		.cats,
		.toolbar .seg {
			flex-wrap: nowrap;
			overflow-x: auto;
			overscroll-behavior-x: contain;
			scrollbar-width: none;
			max-width: 100%;
		}
		.cats::-webkit-scrollbar,
		.toolbar .seg::-webkit-scrollbar {
			display: none;
		}
		.cats > a,
		.toolbar .seg > button {
			flex: none;
			white-space: nowrap;
		}
		.cats {
			margin-bottom: 1rem;
		}
		.stats {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 0.625rem;
			margin-bottom: 1rem;
		}
		.stats > :global(:last-child:nth-child(odd)) {
			grid-column: 1 / -1;
		}
		.search {
			max-width: none;
		}
		.shown {
			margin: 0;
			font-size: 0.875rem;
		}
		.row {
			grid-template-columns: 2rem minmax(0, 1fr) auto;
			gap: 0.35rem 0.6rem;
			padding: 0.6rem 0.75rem;
			align-items: center;
		}
		.rank {
			grid-row: 1 / span 2;
			align-self: start;
			width: 2rem;
			height: 2rem;
			font-size: 0.875rem;
		}
		.name {
			grid-column: 2;
			grid-row: 1;
			min-width: 0;
		}
		.name a {
			display: -webkit-box;
			-webkit-box-orient: vertical;
			-webkit-line-clamp: 2;
			line-clamp: 2;
			overflow: hidden;
			line-height: 1.3;
			font-size: 0.9375rem;
		}
		.more {
			grid-column: 3;
			grid-row: 1;
			width: 2.5rem;
			height: 2.5rem;
		}
		.val {
			grid-column: 2;
			grid-row: 2;
			flex-direction: row;
			align-items: center;
			gap: 0.6rem;
			min-width: 0;
		}
		.v {
			font-size: 0.875rem;
		}
		.mini {
			flex: 1 1 auto;
			min-width: 2.5rem;
		}
		.cmp {
			grid-column: 3;
			grid-row: 2;
			justify-content: center;
		}
		.cmp-txt {
			display: none;
		}
		.details {
			grid-column: 1 / -1;
			grid-row: auto;
		}
		.details dl {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 0.5rem 1rem;
		}
		.details dl > div:first-child {
			grid-column: 1 / -1;
		}
		.list-card {
			border-radius: 14px;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.more,
		.row {
			transition: none;
		}
	}
</style>
