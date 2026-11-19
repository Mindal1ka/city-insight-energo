<script lang="ts">
	// Сторінка «Якість даних»: замість суцільної таблиці — групи за типом проблеми
	// («що не так → чим заважає → що робити»), а будівлі кожної групи — за розгортанням. CSV — як і раніше.
	import { flip } from 'svelte/animate';
	import { api, errMessage, type Defect } from '#lib/api.ts';
	import { num, plural } from '#lib/format.ts';
	import Status from '#lib/Status.svelte';
	import Skeleton from '#lib/Skeleton.svelte';
	import Term from '#lib/Term.svelte';
	import StatCard from '#lib/StatCard.svelte';
	import Reveal from '#lib/Reveal.svelte';
	import Icon from '#lib/Icon.svelte';
	import { fadeUp, stagger, reducedMotion } from '#lib/motion.ts';
	import { isElecRelevant } from '../rating/electricity.ts';
	import { groupDefects, SEVERITY_LABEL, type Severity } from './groups.ts';

	let defects = $state<Defect[]>([]);
	let error = $state<string | null>(null);
	let loading = $state(true);

	let query = $state('');
	let sev = $state<Severity | ''>('');
	// За замовчуванням ховаємо записи лише про тепло, газ і воду: продукт — про електроенергію
	let showNonElec = $state(false);
	let openGroups = $state<Record<string, boolean>>({});
	let limits = $state<Record<string, number>>({});
	const STEP = 25;

	async function load() {
		loading = true;
		error = null;
		try {
			defects = await api.defects();
		} catch (e) {
			error = errMessage(e);
		} finally {
			loading = false;
		}
	}
	load();

	const scope = $derived(showNonElec ? defects : defects.filter(isElecRelevant));
	const hiddenCount = $derived(defects.length - defects.filter(isElecRelevant).length);
	const allGroups = $derived(groupDefects(scope));
	const q = $derived(query.trim().toLocaleLowerCase('uk'));

	const groups = $derived(
		allGroups
			.filter((g) => !sev || g.severity === sev)
			.map((g) => {
				const items = q ? g.items.filter((d) => String(d.будівля).toLocaleLowerCase('uk').includes(q)) : g.items;
				return { ...g, shown: items };
			})
			.filter((g) => g.shown.length > 0)
	);

	function countSev(s: Severity): number {
		return allGroups.filter((g) => g.severity === s).reduce((n, g) => n + g.items.length, 0);
	}
	const nHigh = $derived(countSev('high'));
	const nMid = $derived(countSev('mid'));
	const nLow = $derived(countSev('low'));
	const nBuildings = $derived(new Set(scope.map((d) => String(d.будівля_id || d.будівля))).size);
	const shownRecords = $derived(groups.reduce((n, g) => n + g.shown.length, 0));

	const flipMs = $derived(reducedMotion.current ? 0 : 360);

	const CHIPS: { key: Severity | ''; label: string }[] = [
		{ key: '', label: 'Усі' },
		{ key: 'high', label: SEVERITY_LABEL.high },
		{ key: 'mid', label: SEVERITY_LABEL.mid },
		{ key: 'low', label: SEVERITY_LABEL.low }
	];
	function chipCount(k: Severity | ''): number {
		return k === 'high' ? nHigh : k === 'mid' ? nMid : k === 'low' ? nLow : scope.length;
	}

	function toggle(key: string) {
		openGroups[key] = !openGroups[key];
	}
	function reset() {
		query = '';
		sev = '';
	}
	function isId(v: number | string): boolean {
		return v !== '' && v !== null && !Number.isNaN(Number(v));
	}
	function val(d: Defect): string {
		return d.значення === '' || d.значення === null ? '' : String(d.значення);
	}
</script>

<svelte:head><title>Якість даних · City Insight Map · Енергія</title></svelte:head>

<div class="page-head">
	<div>
		<h1>Якість даних</h1>
		<p class="lead">
			Помилки й пропуски в даних <Term key="UMUNI" plain />, які система знайшла сама. Ми згрупували їх
			за типом і підказали, що зробити: виправите в UMUNI — і рейтинг та розрахунки стануть точнішими.
		</p>
	</div>
	<a class="btn btn-secondary" href="/api/defects.csv" download="data-defects.csv">
		<svg width="18" height="18" viewBox="0 0 20 20" aria-hidden="true"
			><path d="M10 3v9m-4-4 4 4 4-4M4 15.5h12" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" /></svg
		>
		Завантажити повний перелік (CSV)
	</a>
</div>

{#if loading}<Skeleton variant="page" count={4} rows={6} />{/if}
<Status loading={false} {error} retry={load} />

{#if !loading && !error}
	<section class="stats" aria-label="Головне в цифрах">
		<Reveal>
			<StatCard
				label="Проблем знайдено"
				value={scope.length}
				icon="search"
				hint="На {num(nBuildings)} {plural(nBuildings, ['будівлі', 'будівлях', 'будівлях'])}. Кожну можна виправити в UMUNI."
			/>
		</Reveal>
		<Reveal delay={70}>
			<StatCard
				label="Заважають рейтингу"
				value={nHigh}
				icon="alert"
				tone={nHigh ? 'bad' : 'good'}
				toneLabel={nHigh ? 'виправити в першу чергу' : 'немає'}
				hint="Через них будівлю не можна чесно порівняти з іншими. Почніть з них."
			/>
		</Reveal>
		<Reveal delay={140}>
			<StatCard
				label="Варто перевірити"
				value={nMid}
				icon="chart"
				tone={nMid ? 'warn' : 'good'}
				toneLabel={nMid ? 'перевірити' : 'немає'}
				hint="Незвичні зміни споживання: може бути реальне зростання, а може — помилка."
			/>
		</Reveal>
		<Reveal delay={210}>
			<StatCard
				label="Довідкові"
				value={nLow}
				icon="info"
				hint="Порожні довідкові поля й координати. На розрахунок електрики не впливають."
			/>
		</Reveal>
	</section>

	<div class="toolbar filters">
		<div class="chips" role="group" aria-label="Показати за важливістю">
			{#each CHIPS as c (c.key)}
				<button type="button" class="sev-chip" aria-pressed={sev === c.key} onclick={() => (sev = c.key)}>
					{#if c.key}<span class="dot dot-{c.key}" aria-hidden="true"></span>{/if}
					{c.label} <span class="n tnum">{num(chipCount(c.key))}</span>
				</button>
			{/each}
		</div>
		<div class="field search">
			<label for="f-q">Знайти будівлю</label>
			<input id="f-q" type="search" bind:value={query} placeholder="Частина назви" />
		</div>
		<label class="toggle">
			<input type="checkbox" bind:checked={showNonElec} />
			Показати також тепло, газ і воду ({num(hiddenCount)})
		</label>
	</div>

	<p class="muted found" aria-live="polite">
		{#if q || sev}
			Знайдено {num(shownRecords)} {plural(shownRecords, ['запис', 'записи', 'записів'])} у {groups.length}
			{plural(groups.length, ['групі', 'групах', 'групах'])}.
			<button type="button" class="linkish" onclick={reset}>Скинути фільтри</button>
		{:else}
			{groups.length} {plural(groups.length, ['тип', 'типи', 'типів'])} проблем — від найважливіших до довідкових.
		{/if}
	</p>

	<ul class="groups">
		{#each groups as g, gi (g.key)}
			{@const open = !!openGroups[g.key] || (!!q && g.shown.length <= 40)}
			{@const limit = limits[g.key] ?? STEP}
			<li class="group sev-{g.severity}" class:open animate:flip={{ duration: flipMs }} in:fadeUp|global={{ delay: stagger(gi, 60) }}>
				<div class="g-head">
					<span class="g-ico" aria-hidden="true">
						<Icon name={g.severity === 'high' ? 'alert' : g.severity === 'mid' ? 'chart' : 'info'} size={20} />
					</span>
					<div class="g-main">
						<p class="g-sev"><span class="pill pill-{g.severity}">{SEVERITY_LABEL[g.severity]}</span></p>
						<h2 class="g-title">{g.title}</h2>
						<p class="g-why">{g.why}</p>
						<p class="g-todo"><Icon name="check" size={18} /> <span><strong>Що робити:</strong> {g.todo}</span></p>
					</div>
					<div class="g-count">
						<span class="g-n tnum">{num(g.shown.length)}</span>
						<span class="muted small">
							{plural(g.shown.length, ['запис', 'записи', 'записів'])}{#if g.buildings !== g.items.length}{' · '}{num(g.buildings)}
								{plural(g.buildings, ['будівля', 'будівлі', 'будівель'])}{/if}
						</span>
					</div>
				</div>
				<button type="button" class="g-toggle" aria-expanded={open} aria-controls="g-{gi}" onclick={() => toggle(g.key)}>
					<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"
						><path d="M3 5.25 7 9.25l4-4" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" /></svg
					>
					{open ? 'Сховати будівлі' : `Показати будівлі (${num(g.shown.length)})`}
				</button>
				{#if open}
					<div class="g-body" id="g-{gi}" in:fadeUp={{ y: -6 }}>
						<ul class="items">
							{#each g.shown.slice(0, limit) as d, i (i)}
								<li in:fadeUp={{ delay: i >= limit - STEP ? stagger(i - (limit - STEP), 15, 300) : 0 }}>
									<span class="it-name">
										{#if isId(d.будівля_id)}<a href="/building/{d.будівля_id}">{d.будівля}</a>{:else}{d.будівля || '—'}{/if}
									</span>
									<span class="it-meta muted small">
										{d.поле}{#if val(d)}: <span class="it-val">{val(d)}</span>{/if} · {d.набір}
									</span>
								</li>
							{/each}
						</ul>
						{#if g.shown.length > limit}
							<button type="button" class="btn btn-secondary btn-more" onclick={() => (limits[g.key] = limit + STEP * 4)}>
								Показати ще {num(Math.min(STEP * 4, g.shown.length - limit))} з {num(g.shown.length - limit)}
							</button>
						{/if}
					</div>
				{/if}
			</li>
		{:else}
			<li class="empty">
				<p><strong>За цими фільтрами нічого не знайдено.</strong></p>
				<button type="button" class="btn btn-secondary" onclick={reset}>Скинути фільтри</button>
			</li>
		{/each}
	</ul>
{/if}

<style>
	.stats {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 270px), 1fr));
		gap: 1rem;
		margin-bottom: 1.5rem;
	}
	.stats > :global(.reveal) {
		display: grid;
	}
	.filters {
		align-items: flex-end;
	}
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}
	.sev-chip {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		min-height: 42px;
		padding: 0.4rem 0.85rem;
		border-radius: 999px;
		border: 1px solid var(--line-strong);
		background: var(--surface);
		color: var(--text);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
		transition:
			background 0.15s,
			border-color 0.15s,
			transform 0.15s;
	}
	.sev-chip:hover {
		border-color: var(--text);
	}
	.sev-chip:active {
		transform: scale(0.97);
	}
	.sev-chip[aria-pressed='true'] {
		background: var(--navy);
		border-color: var(--navy);
		color: #fff;
	}
	.n {
		font-weight: 500;
		opacity: 0.8;
	}
	.dot {
		width: 0.65rem;
		height: 0.65rem;
		border-radius: 50%;
		border: 1.5px solid #fff;
		box-shadow: 0 0 0 1px currentColor;
	}
	.dot-high {
		background: var(--bad);
	}
	.dot-mid {
		background: var(--sun);
	}
	.dot-low {
		background: var(--line-strong);
	}
	.search {
		flex: 1 1 14rem;
		max-width: 22rem;
	}
	.search input {
		width: 100%;
	}
	.toggle {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		font-weight: 500;
		min-height: 42px;
		cursor: pointer;
	}
	.toggle input {
		width: 1.1rem;
		height: 1.1rem;
	}
	.found {
		margin: 0 0 0.9rem;
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
	.groups {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.9rem;
	}
	.group {
		--g: var(--line-strong);
		--g-soft: var(--neutral-soft);
		--g-ink: var(--muted);
		background: var(--surface);
		border: 1px solid #e3e8ef;
		border-left: 5px solid var(--g);
		border-radius: var(--radius);
		box-shadow: var(--shadow);
		padding: 1rem 1.25rem 0.5rem;
		transition: box-shadow 0.2s;
	}
	.group:hover,
	.group.open {
		box-shadow: var(--shadow-md);
	}
	.sev-high {
		--g: var(--bad);
		--g-soft: var(--bad-soft);
		--g-ink: var(--bad);
	}
	.sev-mid {
		--g: var(--sun-strong);
		--g-soft: var(--sun-soft);
		--g-ink: var(--sun-ink);
	}
	.g-head {
		display: grid;
		grid-template-columns: 2.5rem minmax(0, 1fr) auto;
		gap: 0.25rem 1rem;
		align-items: start;
	}
	.g-ico {
		display: grid;
		place-items: center;
		width: 2.5rem;
		height: 2.5rem;
		border-radius: 12px;
		background: var(--g-soft);
		color: var(--g-ink);
	}
	.g-main p {
		margin: 0 0 0.35rem;
	}
	.g-sev {
		line-height: 1;
	}
	.pill-high {
		background: var(--bad-soft);
		border-color: var(--bad);
		color: var(--bad);
	}
	.pill-mid {
		background: var(--sun-soft);
		border-color: var(--sun-ink);
		color: var(--sun-ink);
	}
	.g-title {
		font-size: 1.15rem;
		margin: 0.35rem 0 0.25rem;
	}
	.g-why {
		color: var(--muted);
	}
	.g-todo {
		display: flex;
		gap: 0.4rem;
		align-items: flex-start;
		color: var(--ok);
	}
	.g-todo span {
		color: var(--text);
	}
	.g-todo :global(svg) {
		flex: none;
		margin-top: 0.15rem;
	}
	.g-count {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		text-align: right;
	}
	.g-n {
		font-size: 1.9rem;
		font-weight: 700;
		line-height: 1.1;
	}
	.g-toggle {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		margin: 0.35rem 0 0.4rem 3.5rem;
		padding: 0.45rem 0.25rem;
		border: 0;
		background: none;
		font: inherit;
		font-weight: 600;
		color: var(--accent);
		cursor: pointer;
		border-radius: 8px;
		min-height: 40px;
	}
	.g-toggle svg {
		transition: transform 0.24s var(--ease);
	}
	.open .g-toggle svg {
		transform: rotate(180deg);
	}
	.g-body {
		margin: 0 0 0.75rem 3.5rem;
		border-top: 1px solid var(--line);
		padding-top: 0.5rem;
	}
	.items {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 22rem), 1fr));
		gap: 0 1.5rem;
	}
	.items li {
		display: flex;
		flex-direction: column;
		padding: 0.45rem 0;
		border-bottom: 1px solid #edf0f4;
		min-width: 0;
	}
	.it-val {
		word-break: break-word;
	}
	.btn-more {
		margin-top: 0.75rem;
	}
	@media (max-width: 640px) {
		.g-head {
			grid-template-columns: 2.5rem minmax(0, 1fr);
		}
		.g-count {
			grid-column: 2;
			flex-direction: row;
			align-items: baseline;
			gap: 0.4rem;
		}
		.g-n {
			font-size: 1.3rem;
		}
		.g-toggle,
		.g-body {
			margin-left: 0;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.sev-chip,
		.g-toggle svg,
		.group {
			transition: none;
		}
	}
</style>
