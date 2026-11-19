<script lang="ts">
	// Головна — повноекранна мапа всіх комунальних об'єктів, колір = клас ефективності СЕС (K).
	// Публічний режим: бекенд не віддає K по об'єктах → фарбуємо за типом, лише зведені цифри громади.
	import { onMount, tick, untrack } from 'svelte';
	import { fly, fade } from 'svelte/transition';
	import { cubicOut } from 'svelte/easing';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import SesMap from '#lib/SesMap.svelte';
	import SesFilters from '#lib/SesFilters.svelte';
	import ZonePanel from '#lib/ZonePanel.svelte';
	import { fetchZones, type Zones } from '#lib/api-v2.ts';
	import KBadge from '#lib/KBadge.svelte';
	import CategoryIcon from '#lib/CategoryIcon.svelte';
	import { catLabel } from '#lib/categories.ts';
	import { CATEGORIES } from '#lib/api-map.ts';
	import { errMessage } from '#lib/api.ts';
	import { auth } from '#lib/auth.svelte.ts';
	import { isReduced } from '#lib/motion.ts';
	import { matchExtra, seasonDay, SEASONS, kwhMonth, type Season } from '#lib/ses-extra.ts';
	import {
		fetchSes,
		filterItems,
		K_CLASSES,
		kwh,
		uah,
		type KClass,
		type Period,
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
	let showZones = $state(true);
	let zonesData = $state<Zones | null>(null);
	let zoneId = $state<number | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);
	let selectedId = $state<number | null>(Number(page.url.searchParams.get('id')) || null);

	const restricted = $derived(!!data?.restricted);
	const items = $derived(data?.items ?? []);
	const shown = $derived(
		filterItems(items, { classes: restricted ? [] : classes, types, q }).filter((i) => matchExtra(i, { department, need }))
	);
	const selected = $derived(items.find((i) => i.id === selectedId) ?? null);
	const t = $derived(data?.totals);
	const zones = $derived(zonesData?.items ?? []);
	const zone = $derived(zones.find((z) => z.id === zoneId) ?? null);
	const zt = $derived(zonesData?.totals);

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

	let zReq = 0;
	async function loadZones(p: Period, s: Season | null) {
		const my = ++zReq;
		try {
			const day = seasonDay(s);
			const z = day ? await fetchZones('month', day) : await fetchZones(p === 'year' ? 'month' : p);
			if (my === zReq) zonesData = z;
		} catch {
			if (my === zReq) zonesData = null; // зони недоступні (права) — просто без шару
		}
	}

	$effect(() => {
		void auth.user?.token; // перезавантажити після входу / виходу
		load(period, season);
		loadZones(period, season);
	});

	// Стан у URL (щоб «Назад» з картки об'єкта повертав до того самого місця)
	$effect(() => {
		const p = period;
		const id = selectedId;
		untrack(() => {
			const u = new URL(location.href);
			if (p === 'year') u.searchParams.delete('p');
			else u.searchParams.set('p', p);
			if (id) u.searchParams.set('id', String(id));
			else u.searchParams.delete('id');
			if (u.search === location.search) return;
			try {
				goto(u, { state: {}, shallow: true, replace: true });
			} catch {
				/* роутер ще не готовий */
			}
		});
	});

	// Висота: від верху блоку до низу вікна (мінус нижня панель вкладок на телефоні)
	let root: HTMLDivElement;
	let h = $state(600);
	let phone = $state(false);
	let padTop = $state(0);
	function measure() {
		if (!root) return;
		const main = root.closest('main');
		if (main) padTop = parseFloat(getComputedStyle(main).paddingTop) || 0;
		const top = (main ? main.getBoundingClientRect().top : root.getBoundingClientRect().top - padTop) + window.scrollY;
		const tab = document.querySelector<HTMLElement>('.tabbar');
		const tabH = tab && getComputedStyle(tab).display !== 'none' ? tab.offsetHeight : 0;
		h = Math.max(380, window.innerHeight - top - tabH);
		phone = window.innerWidth < 700;
	}
	onMount(() => {
		document.body.classList.add('map-home');
		measure();
		const t1 = setTimeout(measure, 300);
		window.addEventListener('resize', measure);
		return () => {
			clearTimeout(t1);
			window.removeEventListener('resize', measure);
			document.body.classList.remove('map-home');
		};
	});

	let cardEl = $state<HTMLElement>();
	let cardH = $state(0);
	let topH = $state(0);
	async function select(id: number | null) {
		selectedId = id;
		if (id != null) zoneId = null;
		if (id != null) {
			await tick();
			cardEl?.focus({ preventScroll: true });
		}
	}
	function pickZone(id: number | null) {
		zoneId = id;
		if (id != null) selectedId = null;
	}
	function onKey(e: KeyboardEvent) {
		if (e.key === 'Escape' && zoneId != null) zoneId = null;
		else if (e.key === 'Escape' && selectedId != null) select(null);
	}
	function firstHit() {
		const f = shown.find((i) => i.lat != null);
		if (f) select(f.id);
	}

	const legend = $derived(
		restricted
			? CATEGORIES.map((c) => ({ key: c.key, color: c.color, glyph: c.glyph, label: c.label }))
			: K_CLASSES.map((c) => ({ key: c.id, color: c.color, glyph: c.glyph, label: c.short }))
	);
	const periodWord = $derived(
		season ? (SEASONS.find((x) => x.id === season)?.label ?? '') : period === 'day' ? 'за день' : period === 'month' ? 'за місяць' : 'за рік'
	);
	const dur = isReduced() ? 0 : 320;
	const nums = $derived(
		selected
			? [
					{ l: 'Згенеровано', v: selected.gen_kwh != null ? kwh(selected.gen_kwh) : null, u: '' },
					{ l: 'Спожито', v: selected.cons_kwh != null ? kwh(selected.cons_kwh) : null, u: '' },
					{ l: 'Заощаджено', v: selected.saved_uah_year != null ? uah(selected.saved_uah_year) : null, u: '/рік' }
				].filter((n) => n.v != null)
			: []
	);
	const unmapped = $derived(shown.filter((i) => i.lat == null).length);
</script>

<svelte:head><title>Мапа СЕС — Енергоменеджмент Полтави</title></svelte:head>
<svelte:window onkeydown={onKey} />

<div class="home" bind:this={root} style="height: {h}px; margin-top: {-padTop}px">
	<h1 class="sr">Мапа ефективності СЕС комунальних об’єктів</h1>

	{#if data}
		<SesMap
			items={shown}
			colorBy={restricted ? 'category' : 'class'}
			{selectedId}
			onselect={select}
			waveKey={period + (season ?? '') + (restricted ? 'r' : '')}
			padBottom={phone && selected ? cardH - topH : 0}
			{zones}
			{showZones}
			selectedZoneId={zoneId}
			onzone={pickZone}
		/>
	{/if}

	<!-- Верх: KPI + фільтри -->
	<div class="top" bind:offsetHeight={topH}>
		{#if t}
			<dl class="kpi" in:fade={{ duration: dur }}>
				<div><dt>Об’єктів</dt><dd>{t.objects}</dd></div>
				{#if restricted}
					<div><dt>З СЕС</dt><dd>{t.with_ses ?? '—'}</dd></div>
					<div><dt>Згенеровано</dt><dd>{kwh(t.gen_kwh).replace(' кВт·год', '')}<small> кВт·год</small></dd></div>
					<div><dt>Заощаджено</dt><dd>{uah(t.saved_uah_year)}</dd></div>
				{:else}
					<div><dt>З СЕС</dt><dd>{t.with_ses ?? '—'}</dd></div>
					<div class="ok"><dt>Ефективно</dt><dd><i aria-hidden="true">✓</i>{t.effective ?? '—'}</dd></div>
					<div>
						<dt>Надлишок / брак</dt>
						<dd>
							<span class="up" title="Надлишок"><i aria-hidden="true">↑</i>{t.surplus ?? '—'}</span>
							<span class="dn" title="Не вистачає"><i aria-hidden="true">↓</i>{t.deficit ?? '—'}</span>
						</dd>
					</div>
				{/if}
			</dl>
		{/if}

		<div class="bar">
			<SesFilters {items} bind:period bind:classes bind:types bind:q bind:department bind:need bind:season {restricted} onenter={firstHit} />
			<div class="meta">
				{#if restricted}
					<a class="lock" href="/login?next=/"
						><svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"
							><rect x="5" y="11" width="14" height="9" rx="2" fill="currentColor" /><path
								d="M8 11V8a4 4 0 0 1 8 0v3"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
							/></svg
						>Ефективність СЕС — після входу</a
					>
				{/if}
				{#if data?.demo || data?.mock}<span class="demo" title={data?.mock ? 'Тимчасовий макет: K випадкові' : 'Реєстр СЕС — демо-дані'}>ДЕМО</span>{/if}
				<span class="cnt"><b>{shown.length}</b> з {items.length} · {shown.length - unmapped} на мапі{#if unmapped}&nbsp;· {unmapped} без адреси{/if}</span>
				<a class="lst" href="/objects">Список →</a>
			</div>
			<div class="zrow">
				<button type="button" class="ztog" class:on={showZones} aria-pressed={showZones} onclick={() => ((showZones = !showZones), !showZones && (zoneId = null))}
					><span class="zdot" aria-hidden="true"></span>Зони</button
				>
				{#if zt && showZones}
					<span class="zsum" title="Зон · з надлишком для сусідів · кВт·год"
						>Зон: <b>{zt.zones}</b> · з надлишком для сусідів: <b>{zt.with_share ?? 0}</b> · <b>{kwh(zt.shareable_kwh)}</b></span
					>
				{/if}
			</div>
		</div>
	</div>

	<!-- Легенда -->
	{#if data && !phone}
		<ul class="legend" aria-label="Легенда" in:fade={{ duration: dur }}>
			{#each legend as l (l.key)}
				<li>
					<svg viewBox="0 0 10 10" aria-hidden="true"><path d={l.glyph} fill={l.color} /></svg>{l.label}
				</li>
			{/each}
		</ul>
	{/if}

	{#if loading && !data}
		<div class="state" out:fade={{ duration: 200 }}><span class="spin" aria-hidden="true"></span>Завантаження…</div>
	{:else if error && !data}
		<div class="state err" role="alert">
			{error}<button type="button" onclick={() => load(period, season)}>Повторити</button>
		</div>
	{/if}

	{#if zone && showZones}
		{#key zone.id}<ZonePanel {zone} onclose={() => (zoneId = null)} />{/key}
	{/if}

	<!-- Картка об'єкта -->
	{#if selected}
		{#key selected.id}
			<section
				class="card"
				tabindex="-1"
				bind:this={cardEl}
				bind:offsetHeight={cardH}
				aria-labelledby="card-title"
				in:fly={phone ? { y: 60, duration: dur, easing: cubicOut } : { x: 40, duration: dur, easing: cubicOut }}
				out:fade={{ duration: isReduced() ? 0 : 120 }}
			>
				<button type="button" class="x" onclick={() => select(null)} aria-label="Закрити картку">✕</button>
				<div class="type">
					<CategoryIcon category={selected.category_short} size={16} />{catLabel(selected.category_short)}
				</div>
				<h2 id="card-title">{selected.name}</h2>
				{#if !restricted && (selected.k_class || selected.access !== 'public')}
					<div class="kb"><KBadge k={selected.k} cls={selected.k_class} size="md" /></div>
				{/if}
				{#if nums.length}
					<dl class="nums" style="--n: {nums.length}">
						{#each nums as n (n.l)}
							<div><dt>{n.l}</dt><dd>{n.v}{#if n.u}<small>{n.u}</small>{/if}</dd></div>
						{/each}
					</dl>
				{/if}
				<dl class="more">
					{#if selected.department}<div><dt>Розпорядник</dt><dd>{selected.department}</dd></div>{/if}
					{#if selected.cons_kwh_month_avg != null}<div><dt>Споживання</dt><dd>≈ {kwhMonth(selected.cons_kwh_month_avg)} кВт·год/міс</dd></div>{/if}
				</dl>
				<p class="per">{periodWord}</p>
				<a class="open" href="/object/{selected.id}">Детальніше <span aria-hidden="true">→</span></a>
			</section>
		{/key}
	{/if}
</div>

<style>
	/* Повна ширина вікна, навіть якщо layout обгортає сторінку у .wrap */
	.home {
		position: relative;
		width: 100vw;
		margin-left: calc(50% - 50vw);
		overflow: hidden;
		background: #e8edf2;
		isolation: isolate;
	}
	/* Повноекранна мапа: без нижнього відступу й підвалу під нею */
	:global(body.map-home main) {
		padding-bottom: 0 !important;
		min-height: 0 !important;
	}
	:global(body.map-home .site-footer) {
		display: none;
	}
	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0 0 0 0);
		white-space: nowrap;
	}
	.top {
		position: absolute;
		z-index: 500;
		top: 12px;
		left: 12px;
		right: 12px;
		display: flex;
		gap: 10px;
		align-items: flex-start;
		pointer-events: none;
	}
	.top > * {
		pointer-events: auto;
	}
	.kpi,
	.bar,
	.legend,
	.card,
	.state {
		background: rgba(255, 255, 255, 0.94);
		-webkit-backdrop-filter: saturate(1.5) blur(12px);
		backdrop-filter: saturate(1.5) blur(12px);
		box-shadow: 0 2px 6px rgba(15, 35, 65, 0.08), 0 12px 32px -14px rgba(15, 35, 65, 0.35);
		border-radius: 16px;
	}
	.kpi {
		display: flex;
		margin: 0;
		padding: 8px 4px;
		flex: none;
	}
	.kpi > div {
		padding: 0 12px;
		border-left: 1px solid #e6ebf1;
	}
	.kpi > div:first-child {
		border-left: 0;
	}
	.kpi dt {
		font-size: 0.68rem;
		color: #4f5b6b;
		font-weight: 600;
		white-space: nowrap;
	}
	.kpi dd {
		margin: 0;
		font-size: 1.2rem;
		font-weight: 800;
		color: #0f1b2d;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
		display: flex;
		gap: 8px;
		align-items: baseline;
	}
	.kpi dd small {
		font-size: 0.65rem;
		font-weight: 600;
		color: #4f5b6b;
	}
	.kpi i {
		font-style: normal;
		font-size: 0.8em;
		margin-right: 2px;
	}
	.kpi .ok i {
		color: #1f8a4c;
	}
	.kpi .up i {
		color: #1f6fd1;
	}
	.kpi .dn i {
		color: #d9680f;
	}
	.bar {
		margin-left: auto;
		width: min(640px, 100%);
		min-width: 0;
		padding: 8px;
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.meta {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: 0.78rem;
		color: #4f5b6b;
		padding: 0 4px;
		flex-wrap: wrap;
	}
	.zrow {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 0 4px;
		font-size: 0.78rem;
		color: #4f5b6b;
		flex-wrap: wrap;
	}
	.ztog {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		border: 1px solid #dfe5ec;
		background: #fff;
		border-radius: 999px;
		padding: 4px 12px;
		font: inherit;
		font-weight: 600;
		color: #1a2433;
		cursor: pointer;
	}
	.ztog.on {
		background: #e3eefb;
		border-color: #1f6fd1;
	}
	.zdot {
		width: 12px;
		height: 12px;
		border-radius: 50%;
		border: 2px solid #1f6fd1;
		background: rgba(31, 111, 209, 0.18);
	}
	.zsum {
		font-variant-numeric: tabular-nums;
	}
	.zsum b {
		color: #0f1b2d;
	}
	.cnt {
		margin-left: auto;
		font-variant-numeric: tabular-nums;
	}
	.lst {
		font-weight: 700;
		color: var(--accent, #0b5cad);
		text-decoration: none;
	}
	.lst:hover {
		text-decoration: underline;
	}
	.lock {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 4px 10px;
		border-radius: 999px;
		background: #0f2f52;
		color: #fff;
		font-weight: 600;
		text-decoration: none;
	}
	.lock:hover {
		background: #1f4f84;
	}
	.demo {
		padding: 2px 8px;
		border-radius: 999px;
		background: #fdf1df;
		color: #8a4b00;
		font-weight: 700;
		font-size: 0.7rem;
		letter-spacing: 0.04em;
	}
	.legend {
		position: absolute;
		z-index: 500;
		left: 12px;
		bottom: 22px;
		margin: 0;
		padding: 8px 12px;
		list-style: none;
		display: flex;
		flex-direction: column;
		gap: 3px;
		font-size: 0.78rem;
		color: #1a2433;
		font-weight: 600;
	}
	.legend li {
		display: flex;
		align-items: center;
		gap: 7px;
	}
	.legend svg {
		width: 13px;
		height: 13px;
	}
	.state {
		position: absolute;
		z-index: 600;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		padding: 14px 20px;
		display: flex;
		align-items: center;
		gap: 10px;
		font-weight: 600;
	}
	.state.err {
		color: #a3201c;
	}
	.state button {
		border: 0;
		background: #0f2f52;
		color: #fff;
		border-radius: 999px;
		padding: 6px 14px;
		font: inherit;
		cursor: pointer;
	}
	.spin {
		width: 18px;
		height: 18px;
		border-radius: 50%;
		border: 3px solid #d6dce4;
		border-top-color: #0b5cad;
		animation: spin 0.8s linear infinite;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
	.card {
		position: absolute;
		z-index: 700;
		right: 58px;
		bottom: 22px;
		width: 320px;
		padding: 16px 16px 14px;
		outline: none;
	}
	.card:focus-visible {
		box-shadow: 0 0 0 3px var(--focus, #ffbf47), 0 12px 32px -14px rgba(15, 35, 65, 0.35);
	}
	.x {
		position: absolute;
		top: 10px;
		right: 10px;
		width: 30px;
		height: 30px;
		border: 0;
		border-radius: 50%;
		background: #eef2f7;
		color: #36425a;
		cursor: pointer;
		font-size: 0.8rem;
	}
	.x:hover {
		background: #e1e7ef;
	}
	.type {
		display: flex;
		align-items: center;
		gap: 6px;
		font-size: 0.78rem;
		font-weight: 600;
		color: #4f5b6b;
	}
	h2 {
		margin: 4px 36px 8px 0;
		font-size: 1.02rem;
		line-height: 1.3;
		color: #0f1b2d;
	}
	.kb {
		margin-bottom: 10px;
	}
	.nums {
		display: grid;
		grid-template-columns: repeat(var(--n, 3), 1fr);
		gap: 6px;
		margin: 0;
	}
	.nums div {
		background: #f3f6fa;
		border-radius: 10px;
		padding: 7px 8px;
		min-width: 0;
	}
	.nums dt {
		font-size: 0.66rem;
		color: #4f5b6b;
		font-weight: 600;
	}
	.nums dd {
		margin: 2px 0 0;
		font-weight: 800;
		font-size: 0.85rem;
		color: #0f1b2d;
		font-variant-numeric: tabular-nums;
		line-height: 1.2;
	}
	.nums small {
		font-weight: 600;
		color: #4f5b6b;
	}
	.more {
		margin: 8px 0 0;
		display: grid;
		gap: 3px;
		font-size: 0.78rem;
	}
	.more div {
		display: flex;
		justify-content: space-between;
		gap: 10px;
	}
	.more dt {
		color: #4f5b6b;
		font-weight: 600;
	}
	.more dd {
		margin: 0;
		font-weight: 700;
		color: #0f1b2d;
		text-align: right;
	}
	.per {
		margin: 6px 0 10px;
		font-size: 0.7rem;
		color: #4f5b6b;
	}
	.open {
		display: flex;
		justify-content: center;
		gap: 6px;
		padding: 10px;
		border-radius: 12px;
		background: #0b5cad;
		color: #fff;
		font-weight: 700;
		text-decoration: none;
		transition: background 0.2s;
	}
	.open:hover {
		background: #084684;
	}
	.open:hover span {
		transform: translateX(3px);
	}
	.open span {
		transition: transform 0.2s;
	}
	a:focus-visible,
	button:focus-visible {
		outline: 3px solid var(--focus, #ffbf47);
		outline-offset: 2px;
	}

	@media (max-width: 1100px) {
		.top {
			flex-direction: column;
			align-items: stretch;
		}
		.kpi {
			align-self: flex-start;
		}
		.bar {
			margin-left: 0;
		}
	}
	@media (max-width: 700px) {
		.top {
			top: 8px;
			left: 8px;
			right: 8px;
			gap: 6px;
		}
		.kpi {
			align-self: stretch;
			padding: 6px 0;
		}
		.kpi > div {
			flex: 1;
			padding: 0 8px;
			min-width: 0;
		}
		.kpi dt {
			font-size: 0.6rem;
			overflow: hidden;
			text-overflow: ellipsis;
		}
		.kpi dd {
			font-size: 1rem;
			gap: 5px;
		}
		.bar {
			width: auto;
			padding: 6px;
		}
		.kpi dd small,
		.cnt {
			display: none;
		}
		.lst {
			margin-left: auto;
		}
		.card {
			left: 8px;
			right: 8px;
			bottom: 8px;
			width: auto;
			border-radius: 18px;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.spin {
			animation-duration: 2s;
		}
	}
</style>
