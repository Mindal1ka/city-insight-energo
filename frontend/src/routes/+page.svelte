<script lang="ts">
	// Головна: «як справи з енергією в громаді і куди дивитися» за 5 секунд.
	// Угорі — одне речення простою мовою + 4 картки-показники; нижче — будівлі громади (плитки або мапа).
	// Другорядні цифри сховано в «Детальніше»; подробиці кожної будівлі — на сторінці об'єкта.
	import { page } from '$app/state';
	import { flip } from 'svelte/animate';
	import type { MapPoint } from '#lib/api-map.ts';
	import { api, errMessage, type SitesResponse, type SiteItem } from '#lib/api.ts';
	import { auth, greetingName } from '#lib/auth.svelte.ts';
	import { num, signed, energy, longDate } from '#lib/format.ts';
	import { viewFrom, withView } from '#lib/view.ts';
	import { fadeUp, stagger, DUR, reducedMotion } from '#lib/motion.ts';
	import Status from '#lib/Status.svelte';
	import ViewSwitch from '#lib/ViewSwitch.svelte';
	import Icon from '#lib/Icon.svelte';
	import StatCard from '#lib/StatCard.svelte';
	import Disclosure from '#lib/Disclosure.svelte';
	import DemoPill from '#lib/DemoPill.svelte';
	import CategoryIcon from '#lib/CategoryIcon.svelte';
	import IndexBadge from '#lib/IndexBadge.svelte';
	import CommunityDistribution from '#lib/CommunityDistribution.svelte';
	import {
		independenceApi,
		duration,
		type IndependenceList,
		type IndependenceItem
	} from '#lib/api-independence.ts';

	const view = $derived(viewFrom(page.url));
	const show = $derived(page.url.searchParams.get('show') === 'map' ? 'map' : 'grid');

	// --- Дані: будівлі на момент перегляду ---
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

	// --- Енергонезалежність (резерв, індекс). Без неї сторінка працює, картки показують менше ---
	let ind = $state<IndependenceList | null>(null);
	let indState = $state<'loading' | 'ok' | 'error'>('loading');
	let iseq = 0;
	async function loadInd(v = view) {
		const my = ++iseq;
		try {
			const d = await independenceApi.list(v);
			if (my === iseq) {
				ind = d;
				indState = 'ok';
			}
		} catch {
			if (my === iseq) indState = ind ? 'ok' : 'error';
		}
	}
	$effect(() => {
		loadInd(view);
	});
	const indById = $derived(new Map<number, IndependenceItem>((ind?.items ?? []).map((i) => [i.id, i])));
	const ic = $derived(ind?.community ?? null);

	// --- Головне речення ---
	const plural = (n: number, one: string, few: string, many: string) => {
		const a = Math.abs(n) % 100;
		const b = a % 10;
		if (a > 10 && a < 20) return many;
		if (b === 1) return one;
		if (b >= 2 && b <= 4) return few;
		return many;
	};
	const sharePct = $derived(ic ? ic.self_sufficiency_pct : null);
	const shareText = $derived(sharePct === null ? '' : num(sharePct, sharePct < 10 ? 1 : 0));
	const critShare = $derived(
		ic && ic.critical_sites_total > 0 ? ic.critical_with_battery / ic.critical_sites_total : null
	);

	// --- Фільтри ---
	const SHORT: Record<string, string> = {
		'Заклади освіти': 'Школи',
		'Дошкільні заклади': 'Садочки',
		"Охорона здоров'я": 'Медзаклади',
		'Громадські будівлі': 'Громадські',
		'Житлові будинки': 'Житлові',
		'Спортивні споруди': 'Спорт'
	};
	const short = (c: string) => SHORT[c] ?? c;

	let query = $state('');
	let category = $state('');
	let onlyCritical = $state(false);
	let sort = $state<'attention' | 'best' | 'name'>('best');
	let limit = $state(48);
	const STEP = 48;

	// Посилання з картки «Медзаклади з резервом»: ?critical=1 вмикає фільтр
	$effect(() => {
		if (page.url.searchParams.get('critical') === '1') {
			onlyCritical = true;
			sort = 'attention';
		}
	});

	const categories = $derived.by(() => {
		const m = new Map<string, number>();
		for (const i of data?.items ?? []) m.set(i.category_short, (m.get(i.category_short) ?? 0) + 1);
		return [...m.entries()].sort((a, b) => b[1] - a[1]).map(([c]) => c);
	});

	const isCritical = (it: SiteItem) =>
		indById.get(it.id)?.critical ?? it.category_short.startsWith('Охорона');
	const hasBattery = (x: IndependenceItem | undefined) => (x?.battery_kwh ?? 0) > 0;

	const norm = (s: string) =>
		s.toLocaleLowerCase('uk').replace(/[’'"«»]/g, '').replace(/\s+/g, ' ');

	function rank(it: SiteItem): number {
		const x = indById.get(it.id);
		const crit = isCritical(it);
		if (crit && !hasBattery(x)) return 0;
		if (crit) return 1;
		if (hasBattery(x)) return 2;
		if (x?.data_ok === false) return 4;
		return 3;
	}

	const filtered = $derived.by(() => {
		const q = norm(query.trim());
		let list = (data?.items ?? []).filter(
			(i) =>
				(!category || i.category_short === category) &&
				(!onlyCritical || isCritical(i)) &&
				(!q || norm(`${i.name} ${i.address} ${i.city}`).includes(q))
		);
		const byName = (a: SiteItem, b: SiteItem) => a.name.localeCompare(b.name, 'uk');
		const idx = (i: SiteItem) => indById.get(i.id)?.index ?? 0;
		const aut = (i: SiteItem) => indById.get(i.id)?.autonomy_hours ?? 0;
		if (sort === 'name') list = list.sort(byName);
		else if (sort === 'best') list = list.sort((a, b) => idx(b) - idx(a) || aut(b) - aut(a) || byName(a, b));
		else list = list.sort((a, b) => rank(a) - rank(b) || idx(b) - idx(a) || byName(a, b));
		return list;
	});
	const shown = $derived(filtered.slice(0, limit));
	const filtersOn = $derived(!!(query || category || onlyCritical));

	// Скидаємо «показати ще», коли змінюються фільтри
	$effect(() => {
		void query;
		void category;
		void onlyCritical;
		void sort;
		limit = STEP;
	});

	function reset() {
		query = '';
		category = '';
		onlyCritical = false;
	}

	/** Коротко для картки: 0,5-годинна точність, бо змодельоване значення не має бути «точним до хвилини» */
	function hours(h: number): string {
		if (h < 1) return `${Math.max(10, Math.round((h * 60) / 10) * 10)} хв`;
		if (h > 72) return 'понад 3 доби';
		return `${num(Math.round(h * 2) / 2, Number.isInteger(Math.round(h * 2) / 2) ? 0 : 1)} год`;
	}

	// --- Рядок стану на картці: одне речення словами + значок (колір — лише підсилення) ---
	type Tone = 'good' | 'warn' | 'bad' | 'none' | 'nodata' | 'wait';
	interface Line {
		tone: Tone;
		text: string;
	}
	function lineOf(it: SiteItem): Line {
		const x = indById.get(it.id);
		if (!x) {
			if (indState === 'loading') return { tone: 'wait', text: 'Перевіряємо резерв…' };
			return { tone: 'nodata', text: 'Дані про резерв недоступні' };
		}
		if (hasBattery(x)) {
			const h = x.autonomy_hours;
			if (h === null || h === undefined) return { tone: 'good', text: 'Резерв на випадок відключення є' };
			return { tone: Math.round(h * 2) / 2 >= 6 ? 'good' : 'warn', text: `Протримається ${hours(h)} без світла` };
		}
		if (x.critical) return { tone: 'bad', text: 'Критичний: резерв не зафіксовано' };
		if (x.data_ok === false) return { tone: 'nodata', text: 'Немає даних про споживання' };
		return { tone: 'none', text: 'Резерв не зафіксовано' };
	}

	// --- Детальніше про громаду ---
	const balance = $derived((data?.items ?? []).reduce((a, i) => a + (i.balance_kwh_today ?? 0), 0));
	const sesKw = $derived((data?.items ?? []).reduce((a, i) => a + (i.ses_kw ?? 0), 0));
	const gen = $derived(data?.totals.generated_today_kwh ?? null);
	const coverToday = $derived(
		data && data.totals.consumed_today_kwh > 0
			? (data.totals.generated_today_kwh / data.totals.consumed_today_kwh) * 100
			: null
	);
	const genScaled = $derived(energy(gen));
	let distOpen = $state(page.url.searchParams.get('tab') === 'distribution');

	// --- Мапа: Leaflet важкий, тому компонент і дані вантажимо лише коли мапу відкрили ---
	// Правило безпеки: на мапу йдуть лише MapPoint з api-map.ts (тип, адреса, споживання, потенціал),
	// без станцій/акумуляторів; власну картку зі «скільки протримається» тут НЕ показуємо.
	let CityMap = $state<typeof import('#lib/CityMap.svelte').default | null>(null);
	let mapPoints = $state<MapPoint[] | null>(null);
	let mapError = $state<string | null>(null);
	let selectedId = $state<number | null>(null);

	async function loadMap() {
		if (CityMap && mapPoints) return;
		mapError = null;
		try {
			const [cm, am] = await Promise.all([import('#lib/CityMap.svelte'), import('#lib/api-map.ts')]);
			const d = await am.loadMap();
			mapPoints = d.points;
			CityMap = cm.default;
		} catch (e) {
			mapError = errMessage(e);
		}
	}
	$effect(() => {
		if (show === 'map') loadMap();
	});
	// На мапі — ті самі фільтри, що й у плитках
	const visibleIds = $derived(new Set(filtered.map((i) => i.id)));
	const mapShown = $derived((mapPoints ?? []).filter((p) => visibleIds.has(p.id)));
	const offMap = $derived(mapShown.filter((p) => p.lat === null || p.lon === null).length);

	function showHref(s: 'grid' | 'map'): string {
		const extra: Record<string, string> = {};
		if (s === 'map') extra.show = 'map';
		return withView('/', view, extra);
	}

	const flipDur = (d: number) => (reducedMotion.current ? 0 : Math.min(DUR.slow, Math.sqrt(d) * 22));
	const today = $derived(data ? longDate(data.now) : '');
</script>

<svelte:head><title>Енергія громади · City Insight Map</title></svelte:head>

<!-- 1. Головне: одне речення + перемикач моменту -->
<header class="hero">
	<div class="hero-text">
		<p class="eyebrow-line">
			{#if auth.user}<span class="hello">Добрий день, {greetingName(auth.user.full_name)}</span><span
					class="dot"
					aria-hidden="true">·</span
				>{/if}
			<span>Енергія громади{#if today}, {today}{/if}</span>
			<DemoPill
				align="left"
				text="Сонячні станції й акумулятори змодельовані: перелік від міста ще не надано. Будівлі та річне споживання — реальні дані UMUNI 2025."
			/>
		</p>
		<h1>
			{#if ic}
				<span in:fadeUp|global={{ duration: DUR.slow }}>
					Сонце дає громаді {sharePct !== null && sharePct < 20 ? 'лише ' : ''}<mark class="hl"
						>{shareText} %</mark
					> електроенергії{#if critShare !== null}, а резерв на випадок відключення зафіксовано{critShare < 0.5 ? ' лише' : ''} в
						<mark class="hl {critShare < 0.5 ? 'bad' : ''}"
							>{ic.critical_with_battery} з {ic.critical_sites_total}</mark
						>
						{plural(ic.critical_sites_total, 'медзакладу', 'медзакладів', 'медзакладів')}{/if}.
				</span>
			{:else if data}
				<span in:fadeUp|global>Стан енергії {num(data.totals.sites)} будівель громади</span>
			{:else}
				Енергія громади
			{/if}
		</h1>
		<p class="lead">
			Нижче — кожна будівля і скільки вона протримається без світла. Натисніть на будівлю, щоб побачити
			подробиці й що варто покращити.
		</p>
	</div>
	<div class="hero-side">
		<ViewSwitch now={data?.now ?? null} />
	</div>
</header>

<!-- 2. Чотири головні показники -->
<section class="stats" aria-label="Головні показники громади">
	<div class="stat" in:fadeUp|global={{ delay: 0 }}>
		<StatCard
			label="Електроенергії дає сонце"
			value={sharePct}
			decimals={sharePct !== null && sharePct < 10 ? 1 : 0}
			unit="%"
			icon="panel"
			tone={sharePct === null ? 'neutral' : sharePct < 10 ? 'bad' : sharePct < 30 ? 'warn' : 'good'}
			hint="Решту електроенергії громада бере з мережі."
			href={withView('/independence', view)}
			demo
		/>
	</div>
	<div class="stat" in:fadeUp|global={{ delay: 70 }}>
		<StatCard
			label="Медзаклади з резервом"
			value={ic?.critical_with_battery ?? null}
			unit={ic ? `з ${ic.critical_sites_total}` : ''}
			icon="alert"
			tone={critShare === null ? 'neutral' : critShare < 0.5 ? 'bad' : critShare < 0.9 ? 'warn' : 'good'}
			hint="Лікарні й амбулаторії, де зафіксовано акумулятор на випадок відключення."
			href={withView('/', view, { critical: '1' }) + '#buildings'}
			demo
		/>
	</div>
	<div class="stat" in:fadeUp|global={{ delay: 140 }}>
		<StatCard
			label={view === 'summer' ? 'Сонце дало в літній день' : 'Сонце дало сьогодні'}
			value={gen}
			decimals={0}
			unit="кВт·год"
			icon="sun"
			hint={coverToday !== null
				? `Це ${num(coverToday, coverToday < 10 ? 1 : 0)} % того, що будівлі спожили з початку доби.`
				: 'Скільки енергії дали сонячні станції з початку доби.'}
			demo
		/>
	</div>
	<div class="stat" in:fadeUp|global={{ delay: 210 }}>
		<StatCard
			label="Можна досягти"
			value={ic?.potential_self_sufficiency_pct ?? null}
			decimals={1}
			unit="%"
			icon="chart"
			tone={ic ? 'good' : 'neutral'}
			toneLabel="можливість"
			hint={ic
				? `Стільки дасть сонце, якщо поставити станції ще на ${num(ic.potential_sites ?? 0)} ${plural(ic.potential_sites ?? 0, 'будівлі', 'будівлях', 'будівлях')}.`
				: 'Скільки дасть сонце з новими станціями.'}
			href="/solar"
		/>
	</div>
</section>

<Status loading={false} {error} retry={() => load()} />

<!-- Другорядні цифри — лише на вимогу -->
{#if data}
	<div class="more-wrap">
		<Disclosure summary="Більше цифр про громаду" hint="станції, баланс, автономність">
			<dl class="facts">
				<div>
					<dt>Будівель у переліку</dt>
					<dd><b class="tnum">{num(data.totals.sites)}</b> <span>дані UMUNI</span></dd>
				</div>
				<div>
					<dt>Сонячну станцію зафіксовано</dt>
					<dd><b class="tnum">{num(data.totals.with_ses)}</b> <span>разом {num(sesKw, 1)} кВт</span></dd>
				</div>
				{#if ic}
					<div>
						<dt>Акумулятор зафіксовано</dt>
						<dd><b class="tnum">{num(ic.battery_sites ?? 0)}</b> <span>разом {num(ic.battery_kwh_total, 0)} кВт·год</span></dd>
					</div>
					<div>
						<dt>Типова будівля з акумулятором протримається</dt>
						<dd><b class="tnum">{duration(ic.autonomy_hours_median)}</b> <span>без світла</span></dd>
					</div>
				{/if}
				<div>
					<dt>Сонце дало {view === 'summer' ? 'в літній день' : 'сьогодні'}</dt>
					<dd><b class="tnum">{genScaled.v} {genScaled.u}</b></dd>
				</div>
				<div>
					<dt>Баланс станцій за добу</dt>
					<dd>
						<b class="tnum">{signed(balance, 0)} кВт·год</b>
						<span>{data.totals.surplus_sites} з надлишком, {data.totals.deficit_sites} з нестачею</span>
					</dd>
				</div>
			</dl>
			<p class="facts-note">
				Сонячні станції й акумулятори змодельовані (ДЕМО); будівлі та річне споживання — реальні дані
				UMUNI 2025. <a href={withView('/independence', view)}>Детальний розбір енергонезалежності →</a>
			</p>
		</Disclosure>
		<Disclosure
			summary="Якби будівлі ділилися сонячною енергією"
			hint="зведення по всіх станціях громади"
			bind:open={distOpen}
		>
			{#if distOpen}
				<CommunityDistribution items={data.items} {view} now={data.now} />
			{/if}
		</Disclosure>
	</div>
{/if}

<!-- 3. Будівлі громади -->
<section id="buildings" class="buildings" aria-labelledby="b-h">
	<div class="b-head">
		<div class="b-title">
			<h2 id="b-h">Будівлі громади</h2>
			{#if show === 'grid'}
				<DemoPill
					align="left"
					text="Рядок про резерв і індекс розраховано на змодельованих станціях та акумуляторах. «Резерв не зафіксовано» означає, що в даних його немає, а не що його точно немає в закладі."
				/>
			{/if}
		</div>
		<div class="b-tools">
			<div class="sort" hidden={show === 'map'}>
				<label for="sort">Порядок</label>
				<select id="sort" bind:value={sort}>
					<option value="best">Спершу найкраще захищені</option>
					<option value="attention">Спершу критичні без резерву</option>
					<option value="name">За назвою (А–Я)</option>
				</select>
			</div>
			<nav class="seg seg-sm" aria-label="Як показати будівлі">
				<a
					href={showHref('grid')}
					aria-current={show === 'grid' ? 'page' : undefined}
					data-sveltekit-reset="false"
					data-sveltekit-replacestate
					data-sveltekit-noscroll
				>
					<svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" fill="currentColor"
						><rect x="1.5" y="1.5" width="5.5" height="5.5" rx="1.3" /><rect x="9" y="1.5" width="5.5" height="5.5" rx="1.3" /><rect
							x="1.5"
							y="9"
							width="5.5"
							height="5.5"
							rx="1.3"
						/><rect x="9" y="9" width="5.5" height="5.5" rx="1.3" /></svg
					> Плитки
				</a>
				<a
					href={showHref('map')}
					aria-current={show === 'map' ? 'page' : undefined}
					data-sveltekit-reset="false"
					data-sveltekit-replacestate
					data-sveltekit-noscroll
				>
					<Icon name="pin" size={16} /> Мапа
				</a>
			</nav>
		</div>
	</div>

	<div class="filters" role="search" aria-label="Пошук і фільтри будівель">
		<div class="search">
			<label for="q" class="visually-hidden">Пошук за назвою або адресою</label>
			<Icon name="search" size={19} />
			<input
				id="q"
				type="search"
				bind:value={query}
				placeholder="Пошук: «ліцей 3», «Шевченка»…"
				autocomplete="off"
			/>
		</div>
		<div class="chips" role="group" aria-label="Тип будівлі">
			<button type="button" class="chip" aria-pressed={category === ''} onclick={() => (category = '')}>
				Усі
			</button>
			{#each categories as c (c)}
				<button
					type="button"
					class="chip"
					aria-pressed={category === c}
					title={c}
					onclick={() => (category = category === c ? '' : c)}
				>
					<CategoryIcon category={c} size={17} />
					{short(c)}
				</button>
			{/each}
		</div>
		<button
			type="button"
			class="chip crit"
			aria-pressed={onlyCritical}
			onclick={() => (onlyCritical = !onlyCritical)}
			title="Лише лікарні й амбулаторії — заклади, які не можна залишати без світла"
		>
			<Icon name="alert" size={17} /> Лише критичні
		</button>
	</div>

	{#if data}
		<p class="found" role="status" aria-live="polite">
			{#if filtered.length}
				{#if show === 'grid' && filtered.length > shown.length}
					Показано <strong class="tnum">{num(shown.length)}</strong> з {num(filtered.length)}
				{:else}
					<strong class="tnum">{num(filtered.length)}</strong>
					{plural(filtered.length, 'будівля', 'будівлі', 'будівель')}
				{/if}
				{#if filtersOn}
					· <button type="button" class="linkish" onclick={reset}>скинути фільтри</button>
				{/if}
			{/if}
		</p>
	{/if}

	{#if !data && loading}
		<ul class="cards" aria-hidden="true">
			{#each { length: 8 } as _, i (i)}
				<li class="sk-card">
					<span class="skeleton sk-a"></span>
					<span class="skeleton sk-b"></span>
					<span class="skeleton sk-c"></span>
					<span class="skeleton sk-d"></span>
				</li>
			{/each}
		</ul>
		<p class="visually-hidden" role="status">Завантаження будівель…</p>
	{:else if data && !filtered.length}
		<div class="nothing" in:fadeUp>
			<span class="nothing-ic" aria-hidden="true"><Icon name="search" size={28} /></span>
			<div>
				<p class="empty-t">
					{#if query}Не знайшли нічого за запитом «{query}».{:else}Таких будівель немає.{/if}
				</p>
				<p class="empty-s">
					Спробуйте коротше слово, номер закладу або назву вулиці — або приберіть фільтри.
				</p>
				<button type="button" class="btn btn-secondary" onclick={reset}>Показати всі будівлі</button>
			</div>
		</div>
	{:else if data && show === 'map'}
		<div class="map-wrap" in:fadeUp>
			{#if CityMap && mapPoints}
				<div class="map-box">
					<CityMap
						points={mapShown}
						{selectedId}
						colorBy="category"
						compact
						height="min(62vh, 560px)"
						onselect={(id) => (selectedId = id)}
						label="Мапа будівель громади за типом закладу"
					/>
				</div>
				<p class="map-note">
					Колір і форма значка — тип будівлі. Натисніть на значок, щоб відкрити будівлю.
					{#if offMap}{offMap} {plural(offMap, 'будівля', 'будівлі', 'будівель')} без точної адреси — їх видно в плитках.{/if}
				</p>
			{:else if mapError}
				<Status error={mapError} retry={() => loadMap()} />
			{:else}
				<div class="map-ph" role="status"><span class="spinner" aria-hidden="true"></span> Завантажуємо мапу…</div>
			{/if}
		</div>
	{:else if data}
		<ul class="cards" class:stale={loading}>
			{#each shown as it, i (it.id)}
				{@const x = indById.get(it.id)}
				{@const ln = lineOf(it)}
				<li animate:flip={{ duration: flipDur }} in:fadeUp|global={{ delay: stagger(i % STEP, 25, 350) }}>
					<a class="site t-{ln.tone}" href={withView(`/object/${it.id}`, view)}>
						<span class="top">
							<span class="type">
								<span class="type-ic"><CategoryIcon category={it.category_short} size={20} /></span>
								<span class="type-t">{short(it.category_short)}</span>
							</span>
							{#if x && x.data_ok !== false && x.index_class !== 'відсутня'}
								<IndexBadge index={x.index} cls={x.index_class} size="sm" />
							{/if}
						</span>
						<span class="name" title={it.name}>{it.name}</span>
						<span class="addr">{it.city && !it.address.includes(it.city) ? `${it.city}, ` : ''}{it.address}</span>
						<span class="line {ln.tone}">
							<span class="l-ic" aria-hidden="true">
								{#if ln.tone === 'good' || ln.tone === 'warn'}
									<Icon name="battery" size={17} />
								{:else if ln.tone === 'bad'}
									<Icon name="alert" size={17} />
								{:else if ln.tone === 'wait'}
									<span class="mini-spin"></span>
								{:else}
									<Icon name="info" size={17} />
								{/if}
							</span>
							<span>{ln.text}</span>
						</span>
					</a>
				</li>
			{/each}
		</ul>
		{#if filtered.length > limit}
			<p class="more">
				<button type="button" class="btn btn-secondary" onclick={() => (limit += STEP)}>
					Показати ще {num(Math.min(STEP, filtered.length - limit))}
				</button>
			</p>
		{/if}
	{/if}
</section>

<style>
	/* --- Герой --- */
	.hero {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: flex-end;
		gap: 1.25rem 2.5rem;
		margin-bottom: 1.35rem;
	}
	.hero-text {
		flex: 1 1 36rem;
		max-width: 62rem;
	}
	.eyebrow-line {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.2rem 0.5rem;
		margin: 0 0 0.5rem;
		font-size: 0.9375rem;
		font-weight: 600;
		color: var(--muted);
	}
	.hello {
		color: var(--sun-ink);
	}
	h1 {
		font-size: clamp(1.6rem, 1.1rem + 1.5vw, 2.35rem);
		line-height: 1.22;
		letter-spacing: -0.02em;
		font-weight: 700;
		margin-bottom: 0.6rem;
		text-wrap: balance;
	}
	h1 > span {
		display: inline-block;
	}
	.hl {
		background: linear-gradient(transparent 58%, var(--sun-soft) 58%);
		color: var(--sun-ink);
		padding: 0 0.1em;
		white-space: nowrap;
		font-variant-numeric: tabular-nums;
	}
	.hl.bad {
		background: linear-gradient(transparent 58%, var(--deficit-soft) 58%);
		color: var(--deficit-ink);
	}
	.lead {
		margin: 0;
		font-size: 1.0625rem;
		color: #3d4857;
		max-width: 52rem;
	}
	.hero-side {
		flex: 0 0 auto;
	}

	/* --- Показники --- */
	.stats {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 1rem;
		margin-bottom: 0.5rem;
	}
	.stat {
		display: grid;
		min-width: 0;
	}
	.stat > :global(*) {
		height: 100%;
	}
	.more-wrap {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0 2rem;
		align-items: start;
		margin-bottom: 1.75rem;
	}
	/* Розкритий блок займає всю ширину, щоб таблиці й графіки мали місце */
	.more-wrap > :global(.disc.open) {
		grid-column: 1 / -1;
		order: 2;
	}
	@media (max-width: 900px) {
		.more-wrap {
			grid-template-columns: 1fr;
		}
	}
	.facts {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 15rem), 1fr));
		gap: 0.75rem 1.5rem;
		margin: 0 0 0.75rem;
	}
	.facts div {
		padding: 0.6rem 0.85rem;
		background: var(--surface);
		border: 1px solid #e3e8ef;
		border-radius: 12px;
	}
	.facts dt {
		font-size: 0.875rem;
		color: var(--muted);
	}
	.facts dd {
		margin: 0.15rem 0 0;
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.1rem 0.5rem;
	}
	.facts dd b {
		font-size: 1.25rem;
	}
	.facts dd span {
		font-size: 0.875rem;
		color: var(--muted);
	}
	.facts-note {
		font-size: 0.875rem;
		color: var(--muted);
		margin: 0;
	}

	/* --- Будівлі --- */
	.buildings {
		scroll-margin-top: 5rem;
	}
	.b-head {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem 1rem;
		margin-bottom: 0.85rem;
	}
	.b-title {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem 0.75rem;
	}
	.b-head h2 {
		margin: 0;
		font-size: 1.5rem;
	}
	.seg-sm a {
		padding: 0.4rem 0.9rem;
		font-size: 0.95rem;
	}

	.filters {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.6rem;
		padding: 0.7rem;
		margin-bottom: 0.75rem;
		background: var(--surface);
		border: 1px solid #e3e8ef;
		border-radius: var(--radius-lg);
		box-shadow: var(--shadow);
	}
	.search {
		flex: 1 1 15rem;
		position: relative;
		display: flex;
		align-items: center;
	}
	.search :global(.icon) {
		position: absolute;
		left: 0.85rem;
		color: var(--muted);
		pointer-events: none;
	}
	.search input {
		width: 100%;
		min-height: 44px;
		padding-left: 2.6rem;
		font-size: 1rem;
		border-radius: 11px;
		background: #f7f9fc;
	}
	.search input:focus-visible {
		background: #fff;
	}
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}
	.chip {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.35rem 0.8rem;
		min-height: 40px;
		border-radius: 999px;
		border: 1px solid #cfd7e1;
		background: #fff;
		color: #2b3645;
		font: inherit;
		font-size: 0.925rem;
		font-weight: 600;
		cursor: pointer;
		white-space: nowrap;
		transition:
			background var(--dur-fast, 150ms),
			border-color var(--dur-fast, 150ms),
			color var(--dur-fast, 150ms),
			transform var(--dur-fast, 150ms);
	}
	.chip:hover {
		border-color: var(--navy-3);
		background: #f3f6fa;
	}
	.chip:active {
		transform: scale(0.97);
	}
	.chip[aria-pressed='true'] {
		background: var(--navy);
		border-color: var(--navy);
		color: #fff;
	}
	.chip.crit {
		color: var(--deficit-ink);
		border-color: #f0c2ad;
	}
	.chip.crit[aria-pressed='true'] {
		background: var(--deficit-ink);
		border-color: var(--deficit-ink);
		color: #fff;
	}
	.b-tools {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.6rem 1rem;
	}
	.sort {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.sort[hidden] {
		display: none;
	}
	.sort label {
		font-weight: 500;
		color: var(--muted);
	}
	.sort select {
		min-height: 44px;
		border-radius: 11px;
		font-size: 0.95rem;
	}
	.found {
		margin: 0 0 0.75rem;
		min-height: 1.5rem;
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

	/* --- Картки --- */
	.cards {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 17.5rem), 1fr));
		gap: 1rem;
		transition: opacity var(--dur-base, 240ms);
	}
	.stale {
		opacity: 0.6;
	}
	.cards > li {
		display: grid;
	}
	.site {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		padding: 1rem 1.1rem 1rem;
		background: var(--surface);
		border: 1px solid #e3e8ef;
		border-radius: 16px;
		box-shadow: var(--shadow);
		color: var(--text);
		text-decoration: none;
		overflow: hidden;
		transition:
			transform var(--dur-base, 240ms) var(--ease),
			box-shadow var(--dur-base, 240ms) var(--ease),
			border-color var(--dur-base, 240ms);
	}
	.site::after {
		content: '';
		position: absolute;
		inset: auto 0 0 0;
		height: 3px;
		background: transparent;
		transform: scaleX(0);
		transform-origin: left;
		opacity: 0.9;
		transition: transform var(--dur-slow, 420ms) var(--ease);
	}
	.site.t-good::after {
		background: var(--surplus);
	}
	.site.t-warn::after {
		background: var(--sun);
	}
	.site.t-bad::after {
		background: var(--deficit);
	}
	.site:hover {
		color: var(--text);
		border-color: #c8d2de;
		box-shadow: var(--shadow-lg);
		transform: translateY(-3px);
	}
	.site:hover::after,
	.site:focus-visible::after {
		transform: scaleX(1);
	}
	.site:active {
		transform: translateY(-1px) scale(0.995);
	}
	.top {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.15rem;
	}
	.type {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		min-width: 0;
	}
	.type-ic {
		display: grid;
		place-items: center;
		width: 2rem;
		height: 2rem;
		border-radius: 9px;
		background: #edf2f8;
		color: var(--navy-3);
		flex: none;
	}
	.type-t {
		font-size: 0.8125rem;
		font-weight: 700;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--muted);
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
		font-size: 0.875rem;
		color: var(--muted);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.line {
		margin-top: auto;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding-top: 0.6rem;
		font-size: 0.9rem;
		font-weight: 600;
		line-height: 1.3;
		color: #3d4857;
	}
	.site .line {
		border-top: 1px solid #edf1f5;
		margin-top: auto;
	}
	.l-ic {
		display: grid;
		place-items: center;
		width: 1.75rem;
		height: 1.75rem;
		border-radius: 50%;
		flex: none;
		background: var(--neutral-soft);
		color: #5b6676;
	}
	.line.good {
		color: var(--surplus-ink);
	}
	.line.good .l-ic {
		background: var(--surplus-soft);
		color: var(--surplus-ink);
	}
	.line.warn {
		color: var(--sun-ink);
	}
	.line.warn .l-ic {
		background: var(--sun-soft);
		color: var(--sun-ink);
	}
	.line.bad {
		color: var(--deficit-ink);
	}
	.line.bad .l-ic {
		background: var(--deficit-soft);
		color: var(--deficit-ink);
	}
	.line.nodata,
	.line.wait {
		color: var(--muted);
		font-weight: 500;
	}
	.line.nodata .l-ic {
		background: transparent;
		border: 1px dashed #b4bfcc;
	}
	.mini-spin {
		width: 0.85rem;
		height: 0.85rem;
		border: 2px solid #cfd7e1;
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
	.more {
		text-align: center;
		margin-top: 1.25rem;
	}

	/* --- Каркас завантаження --- */
	.sk-card {
		display: flex;
		flex-direction: column;
		gap: 0.6rem;
		padding: 1rem 1.1rem;
		background: var(--surface);
		border: 1px solid #e3e8ef;
		border-radius: 16px;
		min-height: 10.5rem;
	}
	.sk-card .skeleton {
		display: block;
		border-radius: 6px;
	}
	.sk-a {
		width: 40%;
		height: 1.6rem;
	}
	.sk-b {
		width: 90%;
		height: 1.1rem;
	}
	.sk-c {
		width: 60%;
		height: 0.9rem;
	}
	.sk-d {
		margin-top: auto;
		width: 75%;
		height: 1.2rem;
	}

	/* --- Порожньо --- */
	.nothing {
		display: flex;
		gap: 1rem;
		align-items: flex-start;
		padding: 1.5rem;
		background: var(--surface);
		border: 1px dashed #c3ccd7;
		border-radius: var(--radius-lg);
	}
	.nothing-ic {
		display: grid;
		place-items: center;
		width: 3.25rem;
		height: 3.25rem;
		border-radius: 50%;
		background: var(--accent-soft);
		color: var(--accent);
		flex: none;
	}
	.empty-t {
		font-size: 1.1rem;
		font-weight: 650;
		margin-bottom: 0.25rem;
	}
	.empty-s {
		color: var(--muted);
	}

	/* --- Мапа --- */
	.map-wrap {
		position: relative;
	}
	.map-ph {
		display: flex;
		flex-direction: row;
		align-items: center;
		justify-content: center;
		gap: 0.4rem;
		min-height: 22rem;
		padding: 2rem;
		text-align: center;
		color: var(--muted);
		background:
			radial-gradient(circle at 30% 40%, #e6eef8 0 2px, transparent 3px) 0 0 / 28px 28px,
			#f7f9fc;
		border: 1px dashed #c3ccd7;
		border-radius: var(--radius-lg);
	}
	.spinner {
		width: 1.1rem;
		height: 1.1rem;
		border: 2px solid var(--line);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}
	.map-box {
		border-radius: var(--radius-lg);
		overflow: hidden;
		border: 1px solid #e3e8ef;
		box-shadow: var(--shadow-md);
	}
	.map-note {
		margin: 0.6rem 0 0;
		font-size: 0.9rem;
		color: var(--muted);
	}

	@media (max-width: 1100px) {
		.stats {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
	@media (max-width: 900px) {
		/* Типи — одним рядком, що гортається пальцем */
		.chips {
			flex-wrap: nowrap;
			overflow-x: auto;
			width: 100%;
			padding: 2px 2px 4px;
			scrollbar-width: thin;
			-webkit-mask-image: linear-gradient(90deg, #000 92%, transparent);
			mask-image: linear-gradient(90deg, #000 92%, transparent);
		}
		.chips .chip:last-child {
			margin-right: 1.5rem;
		}
	}
	@media (max-width: 560px) {
		.stats {
			grid-template-columns: 1fr;
		}
		.sort,
		.sort select {
			width: 100%;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.site,
		.site:hover,
		.site:active,
		.chip:active {
			transition: none;
			transform: none;
		}
		.site::after {
			transition: none;
		}
		.mini-spin,
		.spinner {
			animation: none;
		}
	}
</style>
