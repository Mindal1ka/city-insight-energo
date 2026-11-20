<script lang="ts">
	// Картка об'єкта: шапка (цифри + рекомендація) і вкладки Огляд · Станція · Гроші · Блекаут.
	// Дані: GET /api/ses/{id} (поки бекенд не готовий — ДЕМО-синтетика в ObjApi.ts), /api/insight/{id}.
	import { page } from '$app/state';
	import { replaceState } from '$app/navigation';
	import { api, errMessage, ApiError } from '#lib/api.ts';
	import { num, date } from '#lib/format.ts';
	import { catLabel } from '#lib/categories.ts';
	import { PERIODS, uah, type Period } from '#lib/api-ses.ts';
	import { auth } from '#lib/auth.svelte.ts';
	import { canSeeSensitive, canSeeBattery, canSeeFinance, canEdit, isInternal } from '#lib/roles.ts';
	import Status from '#lib/Status.svelte';
	import Icon from '#lib/Icon.svelte';
	import KBadge from '#lib/KBadge.svelte';
	import DemoPill from '#lib/DemoPill.svelte';
	import Disclosure from '#lib/Disclosure.svelte';
	import ForecastCard from '#lib/ForecastCard.svelte';
	import V2Blackout from '#lib/obj/V2Blackout.svelte';
	import ObjFinance from '#lib/obj/ObjFinance.svelte';
	import V2Monthly from '#lib/obj/V2Monthly.svelte';
	import V2Budget from '#lib/obj/V2Budget.svelte';
	import V2Live from '#lib/obj/V2Live.svelte';
	import V2Dist from '#lib/obj/V2Dist.svelte';
	import V2Reco from '#lib/obj/V2Reco.svelte';
	import SourceTag from '#lib/SourceTag.svelte';
	import { fetchInsight, updateLimit, type Insight, type MonthRow } from '#lib/api-v2.ts';
	import { onDestroy } from 'svelte';
	import { segIndicator } from '#lib/motion.ts';
	import { loadObj, saveObj, normSes, normCosts, emptySes, emptyCosts, type ObjDetail, type ObjPatch } from '#lib/obj/ObjApi.ts';

	const id = $derived(page.params.id ?? '');

	let d = $state<ObjDetail | null>(null);
	let error = $state<string | null>(null);
	let notFound = $state(false);
	let loading = $state(true);
	let seq = 0;
	async function load(oid: string) {
		const my = ++seq;
		loading = true;
		error = null;
		notFound = false;
		try {
			const r = await loadObj(oid);
			if (my === seq) d = r;
		} catch (e) {
			if (my !== seq) return;
			if (e instanceof ApiError && e.status === 404) notFound = true;
			else error = errMessage(e);
			d = null;
		} finally {
			if (my === seq) loading = false;
		}
	}
	$effect(() => {
		load(id);
	});

	// --- v2: insight (ліміти, live, розподіл, сайзинг); live оновлюється кожні 60 с ---
	let ins = $state<Insight | null>(null);
	async function loadIns(oid: string, silent = false) {
		const n = Number(oid);
		if (!Number.isFinite(n)) return;
		try {
			const r = await fetchInsight(n);
			if (oid === id) ins = r;
		} catch {
			if (!silent && oid === id) ins = null;
		}
	}
	$effect(() => {
		ins = null;
		loadIns(id);
	});
	const insTimer = setInterval(() => {
		if (id && typeof document !== 'undefined' && !document.hidden) loadIns(id, true);
	}, 60_000);
	onDestroy(() => clearInterval(insTimer));
	async function saveLimit(v: number | null) {
		try {
			await updateLimit(Number(id), v);
			await loadIns(id);
			say('Збережено');
		} catch (err) {
			say(errMessage(err), false);
			throw err;
		}
	}

	// --- Ролі ---
	const user = $derived(auth.user);
	const canLimit = $derived(user?.role === 'energy_manager' || user?.role === 'finance');
	const cat = $derived(d?.building.category_short ?? null);
	// Бекенд сам вирішує рівень доступу (access); клієнтські правила — лише запасний варіант
	const access = $derived(d?.access ?? null);
	const sens = $derived(access ? access !== 'public' : canSeeSensitive(user, cat, id));
	const bat = $derived(access ? access === 'full' && canSeeBattery(user, cat, id) : canSeeBattery(user, cat, id));
	const fin = $derived(sens && canSeeFinance(user, cat, id));
	const editable = $derived(!!d && (d.mock ? canEdit(user, id) : d.can_edit));
	const ses = $derived(sens ? (d?.ses ?? null) : null);

	let period = $state<Period>('year');
	const e = $derived(d?.energy[period] ?? null);
	const k = $derived(d?.k[period] ?? null);
	const kc = $derived(d?.k_class[period] ?? null);
	const hasCons = $derived(!!e && (e.cons_kwh ?? 0) > 0);
	const noCost = $derived(!!ses && !(d?.costs?.total_uah || d?.finance?.invested_uah));

	// Лічильники: з /api/ses, інакше — з /api/buildings/{id}.meters (якщо бекенд їх віддає)
	let bMeters = $state<{ electricity: number | null; total: number | null } | null>(null);
	$effect(() => {
		bMeters = null;
		if (!d || d.meters || String(d.building.id) !== id) return;
		const my = id;
		api.building(my).then(
			(r) => {
				const mm = (r as unknown as { meters?: { electricity?: number; total?: number } }).meters;
				if (my === id && mm) bMeters = { electricity: mm.electricity ?? null, total: mm.total ?? null };
			},
			() => {}
		);
	});
	const meters = $derived(d?.meters ?? bMeters);

	// --- Редагування з оптимістичним оновленням ---
	let editOpen = $state(false);
	// Шухляда редагування (форма + валідація) вантажиться лише коли її вперше відкривають
	let drawerMod = $state<Promise<typeof import('#lib/obj/ObjEditDrawer.svelte')> | null>(null);
	$effect(() => {
		if (editOpen && !drawerMod) drawerMod = import('#lib/obj/ObjEditDrawer.svelte');
	});
	let toast = $state<{ text: string; ok: boolean } | null>(null);
	let tt: ReturnType<typeof setTimeout> | undefined;
	function say(text: string, ok = true) {
		toast = { text, ok };
		clearTimeout(tt);
		tt = setTimeout(() => (toast = null), 3200);
	}
	async function onsave(patch: ObjPatch) {
		if (!d) return;
		const prev = { ses: d.ses, costs: d.costs };
		const sesPart = Object.fromEntries(Object.entries(patch).filter(([key]) => !key.endsWith('_uah')));
		const costPart = Object.fromEntries(Object.entries(patch).filter(([key]) => key.endsWith('_uah')));
		d.ses = normSes({ ...(d.ses ?? emptySes()), ...sesPart, source: 'введено' } as typeof prev.ses & object);
		d.costs = normCosts({ ...(d.costs ?? emptyCosts()), ...costPart } as typeof prev.costs & object);
		try {
			const r = await saveObj(id, patch, !!d.mock);
			if (r) d = r;
			else await load(id); // ДЕМО: перерахувати фінанси з новими даними
			say('Збережено');
		} catch (err) {
			if (d) {
				d.ses = prev.ses;
				d.costs = prev.costs;
			}
			say(errMessage(err), false);
			throw err;
		}
	}


	// --- Вкладки (?tab=) ---
	type TabId = 'overview' | 'station' | 'money' | 'blackout';
	let tab = $state<string>(page.url.searchParams.get('tab') ?? 'overview');
	let blackoutOk = $state(false);
	const tabs = $derived(
		[
			{ id: 'overview', label: 'Огляд', icon: 'chart', show: true },
			{ id: 'station', label: 'Станція', icon: 'sun', show: sens },
			{ id: 'money', label: 'Гроші', icon: 'wallet', show: fin && (hasCons || !!ses) },
			{ id: 'blackout', label: 'Блекаут', icon: 'battery', show: isInternal(user) && blackoutOk }
		].filter((t) => t.show) as { id: TabId; label: string; icon: 'chart'; show: boolean }[]
	);
	const cur = $derived<TabId>(tabs.some((t) => t.id === tab) ? (tab as TabId) : 'overview');
	// Напрямок зміни вкладки: вміст зсувається туди, куди «пішли» (±12 px), лише після першого перемикання
	let tabDir = $state(0);
	function pick(t: TabId) {
		const from = tabs.findIndex((x) => x.id === cur);
		const to = tabs.findIndex((x) => x.id === t);
		if (to !== from) tabDir = to > from ? 1 : -1;
		tab = t;
		const u = new URL(page.url.href);
		if (t === 'overview') u.searchParams.delete('tab');
		else u.searchParams.set('tab', t);
		replaceState(u, page.state);
	}
	function tabKey(ev: KeyboardEvent) {
		const i = tabs.findIndex((t) => t.id === cur);
		const n = ev.key === 'ArrowRight' ? i + 1 : ev.key === 'ArrowLeft' ? i - 1 : -1;
		if (n < 0 || n >= tabs.length) return;
		ev.preventDefault();
		pick(tabs[n].id);
		(document.getElementById(`tab-${tabs[n].id}`) as HTMLElement | null)?.focus();
	}

	// --- Великі цифри шапки ---
	const rows = $derived<MonthRow[]>(ins?.months ?? []);
	function sumM(k: 'cons_kwh' | 'gen_kwh' | 'saved_uah'): number | null {
		const v = rows.map((r) => r[k]);
		return v.some((x) => x != null) ? v.reduce((a: number, x) => a + (x ?? 0), 0) : null;
	}
	const yr = $derived(d?.energy.year ?? null);
	const consMonth = $derived.by(() => {
		const avg = ins?.sizing?.cons_kwh_month_avg;
		if (avg != null) return avg;
		const c = sumM('cons_kwh');
		if (c != null) return c / 12;
		return yr?.cons_kwh ? yr.cons_kwh / 12 : null;
	});
	const genMonth = $derived.by(() => {
		const g = sumM('gen_kwh') ?? yr?.gen_kwh ?? null;
		return g != null ? g / 12 : null;
	});
	const batKwh = $derived(bat && ses ? (ins?.battery_capacity_kwh ?? ses.battery_kwh ?? null) : null);
	const savedYear = $derived(fin && ses ? (sumM('saved_uah') ?? d?.finance?.saved_uah.year ?? null) : null);
	// Немає споживання в UMUNI → не показуємо нулі й висновки, лише «немає даних»
	const noCons = $derived(!consMonth);
	const bigNums = $derived(
		[
			{ k: 'cons', icon: 'plug', pre: 'Споживає ≈', v: consMonth, unit: 'кВт·год/міс', d: 0 },
			{ k: 'gen', icon: 'sun', pre: 'Панелі дають ≈', v: ses ? genMonth : null, unit: 'кВт·год/міс', d: 0 },
			{ k: 'bat', icon: 'battery', pre: 'Акумулятор', v: batKwh || null, unit: 'кВт·год', d: 1 },
			{ k: 'sav', icon: 'wallet', pre: 'Заощаджує', v: savedYear, unit: 'грн/рік', d: 0 }
		].filter((x) => x.v != null && !(noCons && x.k !== 'bat')) as { k: string; icon: 'plug'; pre: string; v: number; unit: string; d: number }[]
	);

	const y26 = $derived(ins?.y2026 ?? null);
	const place = $derived(d ? String(d.building.address ?? '') : '');
	const pLabel = $derived(PERIODS.find((p) => p.id === period)?.label.toLowerCase() ?? '');
</script>

<svelte:head><title>{d ? `${d.building.name} · ` : ''}Об’єкт · Енергія</title></svelte:head>

<p class="back no-print">
	<a href="/"><Icon name="arrow-left" size={18} /> Мапа</a>
</p>

{#if notFound}
	<div class="notice notice-warn"><p><strong>Об’єкт не знайдено.</strong> <a href="/">До мапи</a></p></div>
{/if}
<Status loading={loading && !d} {error} retry={() => load(id)} />

{#if d}
	{@const b = d.building}
	<div class="obj" class:stale={loading} aria-busy={loading}>
		<!-- ============ 1. Шапка ============ -->
		<header class="panel hero">
			<div class="h-top">
				<div class="h-main">
					<p class="eyebrow">
						{catLabel(b.category_short ?? '')}
						{#if ins?.department}<span class="dept"><Icon name="users" size={13} /> {ins.department}</span>{/if}
						{#if d.demo && sens}<DemoPill align="left" text="Дані СЕС змодельовані (у місті немає реєстру СЕС); споживання — реальні дані UMUNI" />{/if}
					</p>
					<h1 title={b.name}>{b.name}</h1>
					<p class="place">
						<Icon name="pin" size={15} /> {place}
						
						{#if b.floors}<span class="fact tnum">· {b.floors} пов.</span>{/if}
					</p>
				</div>
				<div class="h-side">
					{#if sens}
						<div class="kbig">
							<span class="k-l">Покриття сонцем за {pLabel}</span>
							<KBadge {k} cls={kc} size="lg" />
						</div>
					{/if}
					<div class="seg" role="radiogroup" aria-label="Період" use:segIndicator>
						{#each PERIODS as p (p.id)}
							<button type="button" role="radio" aria-checked={period === p.id} class:on={period === p.id} onclick={() => (period = p.id)}>{p.label}</button>
						{/each}
					</div>
					{#if editable}
						<button type="button" class="btn btn-secondary btn-sm edit" onclick={() => (editOpen = true)}><Icon name="panel" size={16} /> Редагувати</button>
					{/if}
				</div>
			</div>

			{#if bigNums.length}
				<div class="nums">
					{#each bigNums as n (n.k)}
						<div class="num {n.k}">
							<span class="n-l"><Icon name={n.icon} size={15} /> {n.pre}</span>
							<span class="n-v tnum">{n.k === 'sav' ? uah(n.v) : num(n.v, n.d)} <small>{n.k === 'sav' ? '/рік' : n.unit}</small></span>
						</div>
					{/each}
				</div>
			{/if}

			{#if y26 && y26.kwh_2026_est != null && y26.quality !== 'немає даних' && y26.quality !== 'немає даних 2026'}
				<p class="y26 tnum">
					<span>2026: ≈ <b>{num(y26.kwh_2026_est / 12)}</b> кВт·год/міс</span>
					{#if y26.trend_pct != null}
						<span class:up={y26.trend_pct > 0} class:down={y26.trend_pct <= 0}>{y26.trend_pct > 0 ? '+' : '−'}{num(Math.abs(y26.trend_pct), 0)} % до 2025</span>
					{/if}
					<SourceTag kind="umuni" />
					{#if y26.quality === 'ймовірна помилка даних'}
						<span class="warn" title="2026 відрізняється від 2025 більш ніж у 2,5 раза — перевірити дані UMUNI"><Icon name="alert" size={15} /></span>
					{/if}
				</p>
			{/if}

			{#if noCons}
				<p class="nodata"><Icon name="info" size={16} /> Немає даних про споживання в UMUNI — покриття, економію й рекомендації порахувати неможливо.</p>
			{:else if sens && ins?.sizing}
				<V2Reco s={ins.sizing} id={b.id} hasStation={!!ses} surplus={false} />
			{/if}
		</header>

		<!-- ============ 2. Вкладки ============ -->
		{#if tabs.length > 1}
			<div class="tabs" role="tablist" aria-label="Розділи картки" use:segIndicator>
				{#each tabs as t (t.id)}
					<button
						type="button"
						role="tab"
						id="tab-{t.id}"
						aria-selected={cur === t.id}
						aria-controls="tp-{t.id}"
						tabindex={cur === t.id ? 0 : -1}
						class:on={cur === t.id}
						onclick={() => pick(t.id)}
						onkeydown={tabKey}><Icon name={t.icon} size={16} /> {t.label}</button>
				{/each}
			</div>
		{/if}

		{#snippet metersLine()}
			{#if meters && (meters.electricity !== null || meters.total !== null)}
				<p class="meters tnum">
					<Icon name="gauge" size={15} /> Лічильники:
					<span>е/е <b>{num(meters.electricity)}</b></span>
					<span>усього <b>{num(meters.total)}</b></span>
				</p>
			{/if}
		{/snippet}

		<!-- ---- Огляд ---- -->
		<div class="tp" class:swap={tabDir !== 0} style:--tp-dx="{tabDir * 12}px" id="tp-overview" role="tabpanel" aria-labelledby="tab-overview" hidden={cur !== 'overview'}>
			{#if ins?.months?.length && !noCons}
				<div class="panel pad"><V2Monthly months={ins.months} capacity={ins.battery_capacity_kwh} months2026={ins.y2026?.months_2026 ?? null} /></div>
			{:else if !hasCons && !(ses && e?.gen_kwh)}
				<div class="empty"><span class="e-ic" aria-hidden="true">?</span><p><b>Немає даних про споживання</b></p></div>
			{:else}
				<div class="empty"><span class="e-ic" aria-hidden="true">…</span><p>Помісячні дані недоступні</p></div>
			{/if}
			{#if !sens}
				{@render metersLine()}
				<p class="lock-chip">
					<Icon name="lock" size={14} /> Дані СЕС — після входу
					{#if !isInternal(user)}<a href="/login?next=/object/{b.id}">Увійти</a>{/if}
				</p>
			{/if}
		</div>

		<!-- ---- Станція ---- -->
		{#if sens}
			<div class="tp" class:swap={tabDir !== 0} style:--tp-dx="{tabDir * 12}px" id="tp-station" role="tabpanel" aria-labelledby="tab-station" hidden={cur !== 'station'}>
				{#if ses}
					<div class="eq">
						<div class="eq-i sun"><Icon name="panel" size={18} /><span><b class="tnum">{num(ses.total_kw, 1)} кВт</b><small>Панелі{ses.panels_count ? ` · ${num(ses.panels_count)} × ${num(ses.panel_w)} Вт` : ''}</small></span></div>
						<div class="eq-i cons"><Icon name="inverter" size={18} /><span><b class="tnum">{num(ses.inverter_kw, 1)} кВт</b><small>Інвертор{ses.inverter_model ? ` · ${ses.inverter_model}` : ''}</small></span></div>
						{#if bat}
							<div class="eq-i bat"><Icon name="battery" size={18} /><span><b class="tnum">{ses.battery_kwh === 0 ? 'немає' : `${num(ses.battery_kwh, 1)} кВт·год`}</b><small>Акумулятори{ses.battery_count ? ` · ${num(ses.battery_count)} × ${num(ses.battery_module_kwh, 2)}` : ''}</small></span></div>
						{/if}
						{#if ses.launched}
							<div class="eq-i"><Icon name="clock" size={18} /><span><b class="tnum">{date(ses.launched)}</b><small>Запуск</small></span></div>
						{/if}
					</div>

					{#if ins?.live}
						<div class="blk">
							<h3>Зараз</h3>
							<V2Live l={ins.live} />
						</div>
					{/if}
					{#if ins?.distribution}
						<div class="blk">
							<h3>Сьогодні</h3>
							<V2Dist d={ins.distribution} />
						</div>
					{/if}

					<Disclosure summary="Сонце завтра">
						<ForecastCard kw={ses.total_kw ?? null} />
					</Disclosure>
				{:else}
					<div class="empty">
						<span class="e-ic" aria-hidden="true"><Icon name="circle" size={18} /></span>
						<p><b>СЕС немає</b></p>
						{#if editable}<button type="button" class="btn btn-secondary btn-sm" onclick={() => (editOpen = true)}>Додати СЕС</button>{/if}
					</div>
				{/if}
				{@render metersLine()}
			</div>
		{/if}

		<!-- ---- Гроші ---- -->
		{#if tabs.some((t) => t.id === 'money')}
			<div class="tp" class:swap={tabDir !== 0} style:--tp-dx="{tabDir * 12}px" id="tp-money" role="tabpanel" aria-labelledby="tab-money" hidden={cur !== 'money'}>
				{#if ins?.budget}
					<div class="panel pad"><V2Budget b={ins.budget} canEdit={canLimit} onsave={saveLimit} /></div>
				{/if}
				<ObjFinance {d} showSes={!!ses} investOnly={!!ins?.budget} />
				{#if noCost}
					<div class="empty slim">
						<span class="e-ic" aria-hidden="true">₴</span>
						<p><b>Немає даних про вартість</b></p>
						{#if editable}<button type="button" class="btn btn-sm" onclick={() => (editOpen = true)}>Внести вартість</button>{/if}
					</div>
				{/if}
			</div>
		{/if}

		<!-- ---- Блекаут: лише для ролей із доступом до чутливих даних (інакше бекенд дає 403) ---- -->
		{#if isInternal(user) && sens && canSeeSensitive(user, cat, id)}
			<div class="tp" class:swap={tabDir !== 0} style:--tp-dx="{tabDir * 12}px" id="tp-blackout" role="tabpanel" aria-labelledby="tab-blackout" hidden={cur !== 'blackout'}>
				<V2Blackout id={b.id} canEdit={editable || user?.role === 'energy_manager'} bind:available={blackoutOk} />
			</div>
		{/if}
	</div>

	{#if editable}
		{#if drawerMod}
			{#await drawerMod then { default: ObjEditDrawer }}
				<ObjEditDrawer bind:open={editOpen} ses={d.ses} costs={d.costs} {onsave} />
			{/await}
		{/if}
	{/if}
{/if}

{#if toast}
	<div class="toast" class:bad={!toast.ok} role="status" aria-live="polite">
		{#if toast.ok}<Icon name="check" size={18} stroke={2.4} />{:else}<Icon name="alert" size={18} />{/if}
		{toast.text}
	</div>
{/if}

<style>
	.nodata {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin: 0.75rem 0 0;
		padding: 0.6rem 0.9rem;
		border: 1px solid var(--line);
		border-radius: var(--radius);
		background: var(--surface-2);
		color: var(--text-2);
		font-size: 0.92rem;
	}
	.back {
		margin: 0 0 0.75rem;
	}
	.back a {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		font-weight: 600;
		text-decoration: none;
	}
	.obj {
		display: grid;
		gap: 1rem;
		min-width: 0;
		transition: opacity var(--dur-base);
	}
	.obj.stale {
		opacity: 0.6;
	}
	.hero {
		display: grid;
		gap: 0.9rem;
	}
	.h-top {
		display: flex;
		justify-content: space-between;
		gap: 1rem 1.5rem;
		flex-wrap: wrap;
	}
	.h-main {
		min-width: 0;
		flex: 1 1 340px;
	}
	.eyebrow {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.3rem 0.6rem;
		margin: 0 0 0.25rem;
	}
	h1 {
		margin: 0;
		font-size: clamp(1.15rem, 2vw, 1.45rem);
		line-height: 1.25;
		color: var(--ink);
		overflow-wrap: anywhere;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
	.dept {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		padding: 0.1rem 0.55rem;
		border-radius: var(--r-pill);
		background: var(--accent-soft);
		color: var(--cons);
		font-size: var(--fs-xs);
		font-weight: 600;
		text-transform: none;
		letter-spacing: 0;
	}
	.place {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.3rem;
		margin: 0.35rem 0 0;
		color: var(--muted);
		font-size: var(--fs-sm);
	}
	.h-side {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 0.6rem;
	}
	.kbig {
		display: flex;
		align-items: center;
		gap: 0.6rem;
	}
	.k-l {
		font-size: var(--fs-xs);
		color: var(--muted);
	}
	.seg {
		display: inline-flex;
		padding: 3px;
		border-radius: var(--r-btn);
		background: var(--neutral-soft);
	}
	.seg button {
		border: 0;
		background: transparent;
		padding: 0.4rem 0.9rem;
		border-radius: var(--r-input);
		font: inherit;
		font-size: var(--fs-sm);
		font-weight: 600;
		color: var(--muted);
		cursor: pointer;
		min-height: 2.25rem;
		transition: background var(--dur-fast), color var(--dur-fast), box-shadow var(--dur-fast);
	}
	.seg button.on {
		background: var(--surface);
		color: var(--ink);
		box-shadow: var(--shadow);
	}
	.seg button:focus-visible,
	.tabs button:focus-visible {
		outline: 3px solid var(--focus);
		outline-offset: 1px;
	}
	.edit {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	/* Чотири великі цифри */
	.nums {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 0.6rem;
	}
	.num {
		display: grid;
		gap: 0.2rem;
		padding: 0.6rem 0.8rem;
		border-radius: var(--r-card);
		background: var(--neutral-soft);
		min-width: 0;
	}
	.n-l {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		font-size: var(--fs-xs);
		color: var(--muted);
	}
	.n-v {
		font-size: 1.35rem;
		font-weight: 800;
		line-height: 1.15;
		color: var(--ink);
		overflow-wrap: anywhere;
	}
	.n-v small {
		font-size: var(--fs-xs);
		font-weight: 500;
		color: var(--muted);
	}
	.num.gen .n-v { color: var(--sun-ink); }
	.num.bat .n-v { color: var(--bat, #6d4fc2); }
	.num.sav .n-v { color: var(--ok); }
	.y26 {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.3rem 0.8rem;
		margin: 0;
		font-size: var(--fs-sm);
		color: var(--muted);
	}
	.y26 b {
		color: var(--ink);
	}
	.y26 .up {
		color: var(--warn, #c2610c);
		font-weight: 700;
	}
	.y26 .down {
		color: var(--ok);
		font-weight: 700;
	}
	.y26 .warn {
		display: inline-flex;
		color: #d08a1c;
		cursor: help;
	}
	/* Вкладки */
	.tabs {
		display: flex;
		gap: 0.25rem;
		overflow-x: auto;
		-webkit-overflow-scrolling: touch;
		scrollbar-width: none;
		border-bottom: 1px solid var(--line);
	}
	.tabs::-webkit-scrollbar {
		display: none;
	}
	.tabs button {
		flex: 0 0 auto;
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		min-height: 2.75rem;
		padding: 0 1rem;
		border: 0;
		border-bottom: 3px solid transparent;
		margin-bottom: -1px;
		background: transparent;
		font: inherit;
		font-weight: 600;
		color: var(--muted);
		cursor: pointer;
	}
	.tabs button:hover {
		color: var(--ink);
	}
	.tabs button.on {
		color: var(--ink);
		border-bottom-color: var(--accent);
	}
	/* Підкреслення активної вкладки — один елемент, що ковзає (segIndicator), 220 мс --ease-in-out */
	.tabs:global(.has-ind) button.on {
		border-bottom-color: transparent;
	}
	.tabs :global(.seg-ind) {
		top: auto !important;
		bottom: 0;
		height: 3px !important;
		border-radius: var(--r-sm) var(--r-sm) 0 0;
		background: var(--accent);
		box-shadow: none;
	}
	/* Період: «таблетка» ковзає під вибраним (кольори ті самі, що й у .on) */
	.seg:global(.has-ind) button.on {
		background: transparent;
		box-shadow: none;
	}
	.seg :global(.seg-ind) {
		background: var(--surface);
		box-shadow: var(--shadow);
		border-radius: var(--r-btn);
	}
	/* Вміст вкладки: проявлення + зсув 12 px у бік руху, лише після перемикання користувачем */
	.tp.swap:not([hidden]) {
		animation: tp-swap var(--dur-base) var(--ease-out) both;
	}
	@keyframes tp-swap {
		from {
			opacity: 0;
			transform: translateX(var(--tp-dx, 0px));
		}
	}
	.tp {
		display: grid;
		gap: 1rem;
		min-width: 0;
	}
	.tp[hidden] {
		display: none;
	}
	.pad {
		padding: 1rem;
		min-width: 0;
	}
	.blk {
		display: grid;
		gap: 0.5rem;
		min-width: 0;
	}
	h3 {
		margin: 0;
		font-size: var(--fs-md);
		color: var(--ink);
	}
	/* Обладнання */
	.eq {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		gap: 0.6rem;
	}
	.eq-i {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.55rem 0.8rem;
		border-radius: var(--r-card);
		background: var(--neutral-soft);
		min-width: 0;
	}
	.eq-i span {
		display: grid;
		min-width: 0;
	}
	.eq-i b {
		color: var(--ink);
	}
	.eq-i small {
		color: var(--muted);
		font-size: var(--fs-xs);
		overflow-wrap: anywhere;
	}
	.eq-i.sun { background: var(--sun-soft); color: var(--sun-ink); }
	.eq-i.cons { background: var(--accent-soft); color: var(--cons); }
	.eq-i.bat { background: var(--surplus-soft); color: var(--surplus-ink); }
	.empty {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.75rem;
		padding: 1rem 1.25rem;
		border: 1px dashed var(--line);
		border-radius: var(--radius);
		background: var(--surface);
	}
	.empty p {
		margin: 0;
		flex: 1 1 auto;
	}
	.empty.slim {
		padding: 0.7rem 1rem;
	}
	.e-ic {
		display: grid;
		place-items: center;
		width: 2.2rem;
		height: 2.2rem;
		border-radius: 50%;
		background: var(--neutral-soft);
		color: var(--muted);
		font-weight: 700;
	}
	.meters {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.3rem 0.9rem;
		margin: 0;
		font-size: var(--fs-sm);
		color: var(--muted);
	}
	.meters b {
		color: var(--ink);
	}
	.lock-chip {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		justify-self: start;
		margin: 0;
		padding: 0.3rem 0.7rem;
		border-radius: var(--r-pill);
		background: var(--neutral-soft);
		font-size: var(--fs-xs);
		color: var(--muted);
	}
	.toast {
		position: fixed;
		left: 50%;
		bottom: calc(1.25rem + var(--tabbar-h) + var(--safe-b));
		transform: translateX(-50%);
		z-index: 1000;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.7rem 1.1rem;
		border-radius: var(--r-card);
		background: var(--ok);
		color: #fff;
		font-weight: 600;
		box-shadow: var(--shadow-lg);
		animation: toast-in var(--dur-base) var(--ease-spring);
	}
	.toast.bad {
		background: var(--bad);
	}
	@keyframes toast-in {
		from {
			opacity: 0;
			transform: translate(-50%, 12px);
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.hero,
		.toast {
			animation: none;
		}
	}
	@media (max-width: 640px) {
		.h-side {
			align-items: stretch;
			width: 100%;
		}
		.kbig {
			justify-content: space-between;
		}
		.seg {
			display: flex;
		}
		.seg button {
			flex: 1;
		}
		.nums {
			grid-template-columns: 1fr 1fr;
			gap: 0.5rem;
		}
		.n-v {
			font-size: 1.15rem;
		}
		.pad {
			padding: 0.75rem 0.6rem;
		}
	}
</style>
