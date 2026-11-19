<script lang="ts">
	// «Мапа об'єктів»: усі комунальні будівлі громади на мапі + пошук, фільтри й синхронний список.
	// Правило безпеки: тут немає жодних даних про СЕС, акумулятори, генератори чи резервне живлення.
	import { onMount, tick } from 'svelte';
	import { page } from '$app/state';
	import { errMessage } from '#lib/api.ts';
	import { num } from '#lib/format.ts';
	import Icon from '#lib/Icon.svelte';
	import Term from '#lib/Term.svelte';
	import CityMap from '#lib/CityMap.svelte';
	import {
		loadMap,
		buildScale,
		pointStyle,
		categoryMeta,
		keyFigure,
		hasCoords,
		isApprox,
		normApos,
		CATEGORIES,
		PRECISION_TEXT,
		type MapData,
		type MapPoint,
		type ColorBy,
		type Precision
	} from '#lib/api-map.ts';

	let data = $state<MapData | null>(null);
	let error = $state<string | null>(null);

	async function load() {
		error = null;
		try {
			data = await loadMap();
		} catch (e) {
			error = errMessage(e);
		}
	}

	// Вибір через посилання /map?id=123 (наприклад, з головної сторінки)
	const urlId = Number(page.url.searchParams.get('id'));

	let query = $state('');
	let cats = $state<string[]>([]);
	let onlySolar = $state(false);
	let colorBy = $state<ColorBy>('category');
	let selectedId = $state<number | null>(Number.isFinite(urlId) && urlId > 0 ? urlId : null);
	let hoverId = $state<number | null>(null);
	let legendOpen = $state(true);

	const MODES: { key: ColorBy; label: string; icon: 'building' | 'bolt' | 'sun' }[] = [
		{ key: 'category', label: 'За типом', icon: 'building' },
		{ key: 'consumption', label: 'За споживанням', icon: 'bolt' },
		{ key: 'potential', label: 'За потенціалом сонця', icon: 'sun' }
	];

	const all = $derived(data?.points ?? []);
	const scale = $derived(buildScale(all, colorBy));

	const catCounts = $derived.by(() => {
		const m = new Map<string, number>();
		for (const p of all) {
			const k = categoryMeta(p.category_short).key;
			m.set(k, (m.get(k) ?? 0) + 1);
		}
		return m;
	});
	const catList = $derived([
		...CATEGORIES.filter((c) => catCounts.has(c.key)),
		...[...catCounts.keys()].filter((k) => !CATEGORIES.some((c) => c.key === k)).map((k) => categoryMeta(k))
	]);

	function norm(s: string): string {
		return normApos(s.toLocaleLowerCase('uk')).replace(/\s+/g, ' ').trim();
	}

	const filtered = $derived.by(() => {
		const q = norm(query);
		return all.filter((p) => {
			if (cats.length && !cats.includes(categoryMeta(p.category_short).key)) return false;
			if (onlySolar && !(p.solar_potential_kw && p.solar_potential_kw > 0)) return false;
			if (q && !norm(`${p.name} ${p.address} ${p.category_short}`).includes(q)) return false;
			return true;
		});
	});

	const collator = new Intl.Collator('uk');
	function byMode(a: MapPoint, b: MapPoint): number {
		const va = colorBy === 'consumption' ? a.elec_kwh_2025 : colorBy === 'potential' ? a.solar_potential_kw : null;
		const vb = colorBy === 'consumption' ? b.elec_kwh_2025 : colorBy === 'potential' ? b.solar_potential_kw : null;
		if (colorBy !== 'category' && va !== vb) {
			if (va === null) return 1;
			if (vb === null) return -1;
			return vb - va;
		}
		return collator.compare(a.name, b.name);
	}
	const onMapList = $derived(filtered.filter(hasCoords).sort(byMode));
	const offMapList = $derived(filtered.filter((p) => !hasCoords(p)).sort(byMode));

	const total = $derived(data?.counts.total ?? all.length);
	const onMapTotal = $derived(data?.counts.on_map ?? all.filter(hasCoords).length);
	const filtersOn = $derived(!!query || cats.length > 0 || onlySolar);

	const sortHint = $derived(
		colorBy === 'consumption'
			? 'спершу найбільші споживачі'
			: colorBy === 'potential'
				? 'спершу найбільший потенціал сонця'
				: 'за абеткою'
	);

	function toggleCat(k: string) {
		cats = cats.includes(k) ? cats.filter((c) => c !== k) : [...cats, k];
	}
	function resetFilters() {
		query = '';
		cats = [];
		onlySolar = false;
	}

	// --- Синхронізація список ↔ мапа ---
	let listEl = $state<HTMLElement>();
	let mapBox = $state<HTMLElement>();
	const reduced =
		typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
	const isMobile = () => typeof matchMedia !== 'undefined' && matchMedia('(max-width: 767px)').matches;

	function pickFromList(id: number) {
		selectedId = selectedId === id ? null : id;
		const p = all.find((x) => x.id === id);
		// На телефоні мапа над списком — повертаємося до неї, щоб побачити переліт
		// (мапа «липка», тому її власна позиція не годиться — беремо верх усього блоку)
		if (selectedId !== null && p && hasCoords(p) && isMobile() && root) {
			const top = root.getBoundingClientRect().top + window.scrollY;
			window.scrollTo({ top, behavior: reduced ? 'auto' : 'smooth' });
		}
	}

	async function pickFromMap(id: number | null) {
		selectedId = id;
		if (id === null || isMobile()) return;
		await tick();
		listEl
			?.querySelector(`[data-id="${id}"]`)
			?.scrollIntoView({ block: 'nearest', behavior: reduced ? 'auto' : 'smooth' });
	}

	// Якщо вибраний об'єкт відфільтровано — знімаємо вибір
	$effect(() => {
		if (selectedId !== null && data && !filtered.some((p) => p.id === selectedId)) selectedId = null;
	});

	// --- Висота: мапа заповнює екран під шапкою ---
	let root = $state<HTMLElement>();
	let topPx = $state(150);
	function measure() {
		if (root) topPx = Math.round(root.getBoundingClientRect().top + window.scrollY);
	}

	onMount(() => {
		load();
		measure();
		window.addEventListener('resize', measure);
		return () => window.removeEventListener('resize', measure);
	});

	const precOrder: Precision[] = ['UMUNI', 'будинок', 'вулиця', 'населений пункт'];

	function swatch(p: MapPoint) {
		return pointStyle(p, colorBy, scale);
	}
</script>

<svelte:head>
	<title>Мапа об’єктів · City Insight Map</title>
</svelte:head>

{#snippet legend(where: string)}
	<fieldset class="mp-mode">
		<legend class="mp-label">Колір на мапі</legend>
		<div class="mp-seg">
			{#each MODES as m (m.key)}
				<label class:on={colorBy === m.key}>
					<input type="radio" name="colorby-{where}" value={m.key} bind:group={colorBy} />
					<Icon name={m.icon} size={16} />
					<span>{m.label}</span>
				</label>
			{/each}
		</div>

		{#if where === 'map'}
			<button type="button" class="mp-collapse" aria-expanded={legendOpen} onclick={() => (legendOpen = !legendOpen)}>
				{legendOpen ? 'Сховати пояснення' : 'Що означають кольори?'}
			</button>
		{/if}
		<div class="mp-legend" aria-live="polite" hidden={where === 'map' && !legendOpen}>
			{#if colorBy === 'category' || !scale}
				<p class="mp-legend-title">Колір і значок у кружечку — тип закладу</p>
				<ul class="mp-legend-cats">
					{#each catList as c (c.key)}
						<li>
							<span class="mp-sw" style="--c:{c.color};--ink:{c.ink}"><svg viewBox="0 0 10 10" aria-hidden="true"><path d={c.glyph} /></svg></span>
							{c.label}
						</li>
					{/each}
				</ul>
			{:else}
				<p class="mp-legend-title">{scale.title}</p>
				<ul class="mp-steps">
					{#each scale.stops as s (s.label)}
						<li>
							<span class="mp-step" style="--c:{s.color}"></span>
							<span class="mp-step-l">{s.label}</span>
						</li>
					{/each}
				</ul>
				<p class="mp-legend-unit">
					{scale.unitText}
				</p>
				<p class="mp-legend-explain">{scale.explain}</p>
				<p class="mp-legend-row"><span class="mp-sw" style="--c:{scale.noData.color}"></span>{scale.noData.label}</p>
			{/if}
			<p class="mp-legend-row">
				<span class="mp-sw mp-sw-approx"><span class="mp-sw" style="--c:#6b7685"></span></span>
				пунктирне коло — розташування приблизне (відома лише вулиця чи село)
			</p>
		</div>
	</fieldset>
{/snippet}

{#snippet itemRow(p: MapPoint)}
	{@const st = swatch(p)}
	{@const fig = keyFigure(p, colorBy)}
	{@const sel = selectedId === p.id}
	<li
		data-id={p.id}
		class="mp-item"
		class:sel
		class:hl={hoverId === p.id}
		onmouseenter={() => (hoverId = p.id)}
		onmouseleave={() => (hoverId = null)}
	>
		<button
			type="button"
			class="mp-item-btn"
			aria-pressed={sel}
			onclick={() => pickFromList(p.id)}
			onfocus={() => (hoverId = p.id)}
			onblur={() => (hoverId = null)}
		>
			<span class="mp-sw mp-sw-lg" class:mp-approx={isApprox(p)} style="--c:{st.color};--ink:{st.ink}">
				<svg viewBox="0 0 10 10" aria-hidden="true"><path d={st.glyph} /></svg>
			</span>
			<span class="mp-item-main">
				<span class="mp-item-name">{p.name}</span>
				<span class="mp-item-addr">
					{p.address || 'адреса не вказана'}
					{#if !hasCoords(p)}<span class="mp-tag">немає на мапі</span>{:else if isApprox(p)}<span class="mp-tag mp-tag-approx" title="Розташування приблизне">≈ приблизно</span>{/if}
				</span>
			</span>
			<span class="mp-item-fig">
				{#if fig.unit}<strong>{fig.value}</strong> <span>{fig.unit}</span>{:else}<span class="muted">—</span>{/if}
			</span>
		</button>
		{#if sel}
			<div class="mp-item-more">
				<p>
					{p.category_short} · {fig.label}
				</p>
				{#if p.precision}<p class="muted">Розташування: {PRECISION_TEXT[p.precision]}</p>{:else}<p class="muted">Адресу не вдалося знайти на мапі.</p>{/if}
				{#if p.defects_count > 0 || !p.data_ok}
					<p class="mp-warn"><Icon name="alert" size={14} /> {p.defects_count > 0 ? `${p.defects_count} зауваж. до даних в UMUNI` : 'Є зауваження до даних'}</p>
				{/if}
				<a class="btn btn-sm" href="/object/{p.id}">Відкрити об’єкт <Icon name="arrow-right" size={16} /></a>
			</div>
		{/if}
	</li>
{/snippet}

<div class="mp" bind:this={root} style="--top:{topPx}px">
	<aside class="mp-panel" aria-label="Пошук і список об’єктів">
		<div class="mp-handle" aria-hidden="true"></div>
		<header class="mp-head">
			<h1>Мапа об’єктів</h1>
			{#if data}
				<p class="mp-counts">
					<strong>{onMapTotal === total ? `Усі ${num(total)} об’єктів на мапі` : `На мапі ${num(onMapTotal)} з ${num(total)}`}</strong>
					{#if total - onMapTotal > 0}<span class="muted"> · {num(total - onMapTotal)} без адреси (є в списку нижче)</span>{/if}
				</p>
				{#if data.mock}
					<p class="mp-mock" role="note">
						<span class="dot" aria-hidden="true"></span>Тимчасові координати: розташування поки умовні, справжні з’являться після геокодування.
					</p>
				{/if}
			{:else if !error}
				<p class="mp-counts muted">Завантажуємо об’єкти…</p>
			{/if}
		</header>

		<div class="mp-controls">
			<label class="mp-search">
				<span class="visually-hidden">Пошук за назвою або адресою</span>
				<Icon name="search" size={18} />
				<input type="search" bind:value={query} placeholder="Назва або адреса, напр. «школа 3»" autocomplete="off" />
			</label>

			<div class="mp-legend-inpanel">{@render legend('panel')}</div>

			<fieldset class="mp-cats">
				<legend class="mp-label">Тип закладу</legend>
				<div class="mp-chips">
					<button type="button" class="chip" aria-pressed={cats.length === 0} onclick={() => (cats = [])}>Усі</button>
					{#each catList as c (c.key)}
						<button type="button" class="chip mp-chip" aria-pressed={cats.includes(c.key)} onclick={() => toggleCat(c.key)} title="Категорія UMUNI: {c.key}">
							<span class="mp-sw" style="--c:{c.color};--ink:{c.ink}"><svg viewBox="0 0 10 10" aria-hidden="true"><path d={c.glyph} /></svg></span>
							{c.label}
							<span class="mp-chip-n">{catCounts.get(c.key) ?? 0}</span>
						</button>
					{/each}
				</div>
			</fieldset>

			<div class="mp-check">
				<label>
					<input type="checkbox" bind:checked={onlySolar} />
					<span>Показати лише з потенціалом</span>
				</label>
				<Term key="СЕС" />
			</div>

			<p class="mp-safe">
				<Icon name="lock" size={16} />
				<span>Резервне живлення на мапі не показуємо — правило безпеки.</span>
			</p>
		</div>

		<div class="mp-list-head">
			<span>
				<strong>{filtersOn ? `Знайдено ${num(filtered.length)}` : `Усі ${num(filtered.length)}`}</strong>
				<span class="muted"> · {sortHint}</span>
			</span>
			{#if filtersOn}<button type="button" class="mp-link" onclick={resetFilters}>Скинути фільтри</button>{/if}
		</div>

		<div class="mp-list" bind:this={listEl}>
			{#if error}
				<div class="mp-empty" role="alert">
					<p>{error}</p>
					<button type="button" class="btn btn-secondary btn-sm" onclick={load}>Спробувати ще раз</button>
				</div>
			{:else if !data}
				<ul class="mp-ul" aria-hidden="true">
					{#each Array(8) as _, i (i)}
						<li class="mp-skel"><span class="skeleton"></span><span class="skeleton"></span></li>
					{/each}
				</ul>
			{:else if filtered.length === 0}
				<div class="mp-empty">
					<p>За цими умовами об’єктів немає.</p>
					<button type="button" class="btn btn-secondary btn-sm" onclick={resetFilters}>Скинути фільтри</button>
				</div>
			{:else}
				<ul class="mp-ul" aria-label="Об’єкти на мапі">
					{#each onMapList as p (p.id)}
						{@render itemRow(p)}
					{/each}
				</ul>
				{#if offMapList.length}
					<h2 class="mp-group">Без точної адреси — немає на мапі ({offMapList.length})</h2>
					<ul class="mp-ul" aria-label="Об’єкти без адреси">
						{#each offMapList as p (p.id)}
							{@render itemRow(p)}
						{/each}
					</ul>
				{/if}
				{#if data.counts.by_precision && Object.keys(data.counts.by_precision).length}
					<details class="mp-how">
						<summary>Як ми визначили розташування</summary>
						<ul>
							{#each precOrder as k (k)}
								{#if data.counts.by_precision[k]}
									<li>{PRECISION_TEXT[k][0].toUpperCase() + PRECISION_TEXT[k].slice(1)}: <strong>{num(data.counts.by_precision[k])}</strong></li>
								{/if}
							{/each}
							{#if total - onMapTotal > 0}<li>Адресу не знайдено: <strong>{num(total - onMapTotal)}</strong></li>{/if}
						</ul>
						{#if data.note}<p>{data.note}</p>{/if}
					</details>
				{/if}
			{/if}
		</div>
	</aside>

	<div class="mp-map" bind:this={mapBox}>
		{#if data}
			<CityMap
				points={filtered}
				{scale}
				{colorBy}
				{selectedId}
				highlightId={hoverId}
				bounds={data.bounds}
				onselect={pickFromMap}
				onhover={(id) => (hoverId = id)}
			/>
		{:else}
			<div class="mp-map-loading" aria-hidden="true"></div>
		{/if}
		<div class="mp-legend-onmap">{@render legend('map')}</div>
	</div>
</div>

<style>
	.mp {
		--panel-w: 400px;
		display: grid;
		grid-template-columns: var(--panel-w) minmax(0, 1fr);
		height: max(560px, calc(100dvh - var(--top) - 1.25rem));
		margin-top: -0.5rem;
		border: 1px solid var(--line);
		border-radius: var(--radius-lg);
		background: var(--surface);
		box-shadow: var(--shadow-md);
		overflow: hidden;
		animation: mp-in 0.45s var(--ease-out, ease) both;
	}
	@keyframes mp-in {
		from {
			opacity: 0;
			transform: translateY(6px);
		}
	}
	@media (max-width: 1280px) {
		.mp {
			--panel-w: 360px;
		}
	}
	@media (max-width: 960px) {
		.mp {
			--panel-w: 320px;
		}
	}

	/* ---------- Ліва панель ---------- */
	.mp-panel {
		display: flex;
		flex-direction: column;
		min-height: 0;
		overflow-y: auto;
		border-right: 1px solid var(--line);
		background: var(--surface);
		scrollbar-gutter: stable;
	}
	.mp-handle {
		display: none;
	}
	.mp-head {
		padding: 1.1rem 1.1rem 0.4rem;
	}
	.mp-head h1 {
		font-size: 1.45rem;
		margin: 0 0 0.25rem;
	}
	.mp-counts {
		margin: 0;
		font-size: 0.9rem;
	}
	.mp-mock {
		display: flex;
		gap: 0.45rem;
		align-items: baseline;
		margin: 0.5rem 0 0;
		padding: 0.4rem 0.6rem;
		border-radius: 8px;
		border: 1px dashed #d08a1c;
		background: var(--sun-soft);
		color: var(--sun-ink);
		font-size: 0.8rem;
		line-height: 1.35;
	}
	.mp-mock .dot {
		flex: none;
		width: 0.45rem;
		height: 0.45rem;
		border-radius: 50%;
		background: var(--sun-strong);
		transform: translateY(-1px);
	}
	.mp-controls {
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
		padding: 0.7rem 1.1rem 0.9rem;
		border-bottom: 1px solid var(--line);
	}
	.mp-search {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0 0.75rem;
		min-height: 44px;
		border: 1px solid var(--line-strong);
		border-radius: 11px;
		background: var(--surface);
		color: var(--muted);
		transition:
			border-color 0.15s,
			box-shadow 0.15s;
	}
	.mp-search:focus-within {
		border-color: var(--accent);
		box-shadow: 0 0 0 3px var(--accent-soft);
	}
	.mp-search input {
		flex: 1;
		min-width: 0;
		border: 0;
		outline: 0;
		background: none;
		font: inherit;
		color: var(--text);
		padding: 0.55rem 0;
	}
	.mp-search input:focus-visible {
		box-shadow: none;
		outline: none;
	}
	fieldset {
		border: 0;
		margin: 0;
		padding: 0;
		min-width: 0;
	}
	.mp-label {
		padding: 0;
		margin-bottom: 0.4rem;
		font-size: 0.78rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--muted);
	}
	.mp-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}
	.mp-chips :global(.chip) {
		min-height: 34px;
		padding: 0.25rem 0.7rem;
		font-size: 0.85rem;
	}
	.mp-chip-n {
		font-weight: 500;
		color: var(--muted);
		font-variant-numeric: tabular-nums;
	}
	.mp-check {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		flex-wrap: wrap;
		font-weight: 600;
		font-size: 0.92rem;
	}
	.mp-check label {
		display: inline-flex;
		align-items: center;
		gap: 0.55rem;
		cursor: pointer;
		font-weight: 600;
		font-size: 0.92rem;
	}
	.mp-check input {
		width: 1.15rem;
		height: 1.15rem;
		accent-color: var(--sun-strong);
	}
	.mp-safe {
		display: flex;
		gap: 0.5rem;
		align-items: flex-start;
		margin: 0;
		padding: 0.5rem 0.65rem;
		border-radius: 9px;
		background: var(--neutral-soft);
		color: var(--text-2, var(--text));
		font-size: 0.8rem;
		line-height: 1.4;
	}
	.mp-safe :global(svg) {
		flex: none;
		margin-top: 1px;
	}

	/* ---------- Перемикач кольору й легенда ---------- */
	.mp-seg {
		display: flex;
		padding: 3px;
		gap: 3px;
		border-radius: 12px;
		background: #e6ebf2;
		border: 1px solid #dbe2ea;
	}
	.mp-seg label {
		flex: 1 1 0;
		min-width: 0;
		position: relative;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.15rem;
		min-height: 44px;
		padding: 0.35rem 0.35rem;
		border-radius: 9px;
		font-size: 0.8rem;
		font-weight: 600;
		line-height: 1.15;
		text-align: center;
		color: var(--text-2, var(--text));
		cursor: pointer;
		transition:
			background 0.2s,
			color 0.2s,
			box-shadow 0.2s;
	}
	.mp-seg label:hover {
		background: rgba(255, 255, 255, 0.6);
	}
	.mp-seg label.on {
		background: #fff;
		color: var(--accent-dark);
		box-shadow: 0 1px 3px rgba(16, 24, 40, 0.15);
	}
	.mp-seg input {
		position: absolute;
		opacity: 0;
		pointer-events: none;
	}
	.mp-seg label:has(input:focus-visible) {
		outline: 3px solid var(--focus);
		outline-offset: 1px;
	}
	.mp-seg :global(svg) {
		flex: none;
	}
	.mp-collapse {
		position: absolute;
		top: 0.7rem;
		right: 0.85rem;
		border: 0;
		background: none;
		padding: 0.1rem 0.2rem;
		font: inherit;
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--accent);
		text-decoration: underline;
		cursor: pointer;
	}
	.mp-legend[hidden] {
		display: none;
	}
	.mp-legend {
		margin-top: 0.6rem;
		font-size: 0.8125rem;
		animation: mp-fade 0.3s ease both;
	}
	@keyframes mp-fade {
		from {
			opacity: 0;
		}
	}
	.mp-legend p {
		margin: 0;
	}
	.mp-legend-title {
		font-weight: 650;
		margin-bottom: 0.4rem !important;
	}
	.mp-legend-cats {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.25rem 0.75rem;
		list-style: none;
		margin: 0 0 0.45rem;
		padding: 0;
	}
	.mp-legend-cats li {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}
	.mp-steps {
		display: grid;
		grid-template-columns: repeat(5, 1fr);
		gap: 2px;
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.mp-steps li {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		min-width: 0;
	}
	.mp-step {
		height: 10px;
		background: var(--c);
	}
	.mp-steps li:first-child .mp-step {
		border-radius: 5px 0 0 5px;
	}
	.mp-steps li:last-child .mp-step {
		border-radius: 0 5px 5px 0;
	}
	.mp-step-l {
		font-size: 0.7rem;
		line-height: 1.2;
		color: var(--muted);
		font-variant-numeric: tabular-nums;
	}
	.mp-legend-unit {
		margin-top: 0.25rem !important;
		font-size: 0.72rem;
		color: var(--muted);
	}
	.mp-legend-explain {
		margin: 0.35rem 0 0.4rem !important;
		color: var(--text-2, var(--text));
	}
	.mp-legend-row {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		margin-top: 0.25rem !important;
		color: var(--text-2, var(--text));
	}
	.mp-sw {
		display: inline-grid;
		place-items: center;
		flex: none;
		width: 14px;
		height: 14px;
		border-radius: 50%;
		background: var(--c);
		color: var(--ink, #fff);
		box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.18);
	}
	.mp-sw svg {
		width: 64%;
		height: 64%;
		fill: currentColor;
	}
	.mp-sw-approx {
		width: 20px;
		height: 20px;
		background: rgba(255, 255, 255, 0.5);
		border: 1.5px dashed #4f5b6b;
		box-shadow: none;
	}
	.mp-sw-approx .mp-sw {
		width: 10px;
		height: 10px;
		box-shadow: 0 0 0 1.5px #fff;
	}

	/* На широкому екрані легенда — поверх мапи, у вузькому — у панелі */
	.mp-legend-inpanel {
		display: none;
	}
	.mp-legend-onmap {
		position: absolute;
		z-index: 800;
		top: 12px;
		left: 12px;
		width: 360px;
		padding: 0.75rem 0.85rem 0.7rem;
		border-radius: 14px;
		background: rgba(255, 255, 255, 0.95);
		backdrop-filter: blur(6px);
		box-shadow: var(--shadow-lg);
		border: 1px solid rgba(214, 220, 228, 0.8);
	}
	@media (max-width: 1099px) {
		.mp-legend-inpanel {
			display: block;
		}
		.mp-legend-onmap {
			display: none;
		}
	}

	/* ---------- Список ---------- */
	.mp-list-head {
		position: sticky;
		top: 0;
		z-index: 2;
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 0.5rem;
		padding: 0.6rem 1.1rem;
		background: rgba(255, 255, 255, 0.96);
		backdrop-filter: blur(4px);
		border-bottom: 1px solid var(--line);
		font-size: 0.85rem;
	}
	.mp-link {
		border: 0;
		background: none;
		padding: 0;
		font: inherit;
		color: var(--accent);
		text-decoration: underline;
		cursor: pointer;
		white-space: nowrap;
	}
	.mp-list {
		padding: 0.35rem 0.5rem 1rem;
	}
	.mp-ul {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.mp-item {
		border-radius: 10px;
		transition: background 0.15s;
	}
	.mp-item.hl {
		background: var(--accent-soft);
	}
	.mp-item.sel {
		background: #eef4fb;
		box-shadow: inset 3px 0 0 var(--accent);
	}
	.mp-item-btn {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr) auto;
		align-items: start;
		gap: 0.65rem;
		width: 100%;
		padding: 0.55rem 0.6rem;
		border: 0;
		background: none;
		font: inherit;
		color: inherit;
		text-align: left;
		cursor: pointer;
		border-radius: 10px;
	}
	.mp-sw-lg {
		width: 18px;
		height: 18px;
		margin-top: 2px;
		border: 1.5px solid #fff;
		box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.25);
		transition: background-color 0.4s;
	}
	.mp-sw-lg.mp-approx {
		outline: 1.5px dashed var(--c);
		outline-offset: 2px;
	}
	.mp-item-main {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}
	.mp-item-name {
		font-weight: 600;
		font-size: 0.9rem;
		line-height: 1.3;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
	.mp-item-addr {
		font-size: 0.78rem;
		color: var(--muted);
		margin-top: 0.1rem;
	}
	.mp-tag {
		display: inline-block;
		margin-left: 0.3rem;
		padding: 0 0.4rem;
		border-radius: 999px;
		background: var(--neutral-soft);
		color: var(--text-2, var(--text));
		font-size: 0.7rem;
		font-weight: 600;
		white-space: nowrap;
	}
	.mp-tag-approx {
		background: transparent;
		border: 1px dashed var(--line-strong);
	}
	.mp-item-fig {
		font-size: 0.8rem;
		text-align: right;
		white-space: nowrap;
		font-variant-numeric: tabular-nums;
		color: var(--muted);
		padding-top: 1px;
	}
	.mp-item-fig strong {
		color: var(--text);
		font-size: 0.9rem;
	}
	.mp-item-more {
		padding: 0 0.75rem 0.75rem 2.35rem;
		font-size: 0.82rem;
		animation: mp-open 0.25s var(--ease-out, ease) both;
	}
	@keyframes mp-open {
		from {
			opacity: 0;
			transform: translateY(-4px);
		}
	}
	.mp-item-more p {
		margin: 0 0 0.3rem;
	}
	.mp-item-more .btn {
		margin-top: 0.3rem;
	}
	.mp-warn {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		color: var(--warn);
	}
	.mp-group {
		margin: 1rem 0.6rem 0.3rem;
		font-size: 0.78rem;
		font-weight: 700;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--muted);
	}
	.mp-empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.6rem;
		padding: 2rem 1rem;
		text-align: center;
		color: var(--muted);
	}
	.mp-skel {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		padding: 0.7rem 0.6rem;
	}
	.mp-skel span {
		height: 0.8rem;
	}
	.mp-skel span:last-child {
		width: 60%;
	}
	.mp-how {
		margin: 1rem 0.6rem 0;
		font-size: 0.82rem;
		color: var(--text-2, var(--text));
	}
	.mp-how summary {
		cursor: pointer;
		color: var(--accent);
		font-weight: 600;
	}
	.mp-how ul {
		margin: 0.4rem 0;
		padding-left: 1.1rem;
	}

	/* ---------- Мапа ---------- */
	.mp-map {
		position: relative;
		min-width: 0;
		min-height: 0;
	}
	.mp-map-loading {
		position: absolute;
		inset: 0;
		background: linear-gradient(100deg, #eef1f4 30%, #f6f8fa 50%, #eef1f4 70%);
		background-size: 200% 100%;
		animation: mp-shim 1.4s linear infinite;
	}
	@keyframes mp-shim {
		from {
			background-position: 150% 0;
		}
		to {
			background-position: -50% 0;
		}
	}

	/* ---------- Телефон: мапа зверху, список — «шторкою» знизу ---------- */
	@media (max-width: 767px) {
		.mp {
			display: flex;
			flex-direction: column-reverse;
			height: auto;
			margin: -0.75rem -2rem 0;
			border: 0;
			border-radius: 0;
			box-shadow: none;
			overflow: visible;
			background: none;
		}
		.mp-map {
			position: sticky;
			top: 0;
			z-index: 0;
			height: 56dvh;
			min-height: 320px;
		}
		.mp-panel {
			position: relative;
			z-index: 1;
			overflow: visible;
			margin-top: -20px;
			border-right: 0;
			border-radius: 20px 20px 0 0;
			box-shadow: 0 -10px 30px -12px rgba(15, 23, 42, 0.35);
			min-height: 60dvh;
		}
		.mp-handle {
			display: block;
			width: 44px;
			height: 5px;
			margin: 0.6rem auto 0;
			border-radius: 3px;
			background: var(--line-strong);
		}
		.mp-head {
			padding-top: 0.6rem;
		}
		.mp-legend-cats {
			grid-template-columns: 1fr 1fr;
		}
	}
	@media (max-width: 700px) {
		.mp {
			margin-inline: -1rem;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.mp,
		.mp-legend,
		.mp-item-more,
		.mp-map-loading {
			animation: none;
		}
	}
</style>
