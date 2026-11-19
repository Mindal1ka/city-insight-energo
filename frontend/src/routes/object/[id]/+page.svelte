<script lang="ts">
	// Картка об'єкта: станція → енергія → фінанси → лічильники; оперативне — у «Детальніше».
	// Дані: GET /api/ses/{id} (поки бекенд не готовий — ДЕМО-синтетика в ObjApi.ts).
	import { page } from '$app/state';
	import { api, errMessage, ApiError, type SiteDetail } from '#lib/api.ts';
	import { num, date, moment } from '#lib/format.ts';
	import { catLabel } from '#lib/categories.ts';
	import { PERIODS, type Period } from '#lib/api-ses.ts';
	import { auth } from '#lib/auth.svelte.ts';
	import { canSeeSensitive, canSeeBattery, canSeeFinance, canEdit, isInternal } from '#lib/roles.ts';
	import Status from '#lib/Status.svelte';
	import Icon from '#lib/Icon.svelte';
	import KBadge from '#lib/KBadge.svelte';
	import DemoPill from '#lib/DemoPill.svelte';
	import Disclosure from '#lib/Disclosure.svelte';
	import Distribution from '#lib/Distribution.svelte';
	import HourlyChart from '#lib/HourlyChart.svelte';
	import OutageSimulator from '#lib/OutageSimulator.svelte';
	import ForecastCard from '#lib/ForecastCard.svelte';
	import ObjTile from '#lib/obj/ObjTile.svelte';
	import ObjMonthChart from '#lib/obj/ObjMonthChart.svelte';
	import ObjFinance from '#lib/obj/ObjFinance.svelte';
	import ObjEditDrawer from '#lib/obj/ObjEditDrawer.svelte';
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

	// --- Ролі ---
	const user = $derived(auth.user);
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

	// --- Оперативні дані (Що зараз) — лише для службових ролей ---
	let site = $state<SiteDetail | null>(null);
	$effect(() => {
		site = null;
		// /api/sites — оперативні дані з акумулятором; фінансовому органу бекенд їх не віддає (403)
		if (!bat || !id) return;
		const my = id;
		api.site(my).then(
			(r) => my === id && (site = r),
			() => {}
		);
	});
	const m = $derived(moment(site?.now));

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
			<div class="h-main">
				<p class="eyebrow">{catLabel(b.category_short ?? '')}</p>
				<h1 title={b.name}>{b.name}</h1>
				<p class="place"><Icon name="pin" size={16} /> {place}</p>
				<p class="facts tnum">
					{#if b.heated_area}<span><Icon name="building" size={15} /> {num(Number(b.heated_area))} м²</span>{/if}
					{#if b.floors}<span>{b.floors} пов.</span>{/if}
					{#if d.demo && sens}<DemoPill align="left" text="Дані СЕС змодельовані (у місті немає реєстру СЕС); споживання — реальні дані UMUNI" />{/if}
				</p>
			</div>
			<div class="h-side">
				{#if sens}
					<div class="kbig">
						<span class="k-l">K · {pLabel}</span>
						<KBadge {k} cls={kc} size="lg" />
					</div>
				{/if}
				<div class="seg" role="radiogroup" aria-label="Період">
					{#each PERIODS as p (p.id)}
						<button type="button" role="radio" aria-checked={period === p.id} class:on={period === p.id} onclick={() => (period = p.id)}>{p.label}</button>
					{/each}
				</div>
				{#if editable}
					<button type="button" class="btn btn-secondary btn-sm edit" onclick={() => (editOpen = true)}><Icon name="panel" size={16} /> Редагувати</button>
				{/if}
			</div>
		</header>

		<!-- ============ 2. Станція ============ -->
		{#if sens}
			<section class="sec" aria-labelledby="st-h">
				<h2 id="st-h"><span class="si sun" aria-hidden="true"><Icon name="sun" size={18} /></span>Станція</h2>
				{#if ses}
					<div class="tiles">
						<ObjTile i={0} icon="panel" tone="sun" label="Панелі" value={ses.total_kw} decimals={1} unit="кВт"
							sub={ses.panels_count ? `${num(ses.panels_count)} шт × ${num(ses.panel_w)} Вт` : ''} />
						<ObjTile i={1} icon="inverter" tone="cons" label="Інвертор" value={ses.inverter_kw} decimals={1} unit="кВт" sub={ses.inverter_model ?? ''} />
						{#if bat}
							<ObjTile i={2} icon="battery" tone="bat" label="Акумулятори" value={ses.battery_kwh} decimals={1} unit="кВт·год"
								sub={ses.battery_count ? `${num(ses.battery_count)} × ${num(ses.battery_module_kwh, 2)} кВт·год` : ses.battery_kwh === 0 ? 'немає' : ''} />
						{/if}
						<ObjTile i={3} icon="plug" label="Приєднана потужність" value={ses.connected_kw} decimals={0} unit="кВт" />
						<ObjTile i={4} icon="clock" label="Запущено" text={ses.launched ? date(ses.launched) : null} />
						<ObjTile i={5} icon="info" tone={ses.source === 'введено' ? 'good' : 'muted'} label="Джерело" text={ses.source === 'введено' ? 'Введено' : 'ДЕМО'} />
					</div>
				{:else}
					<div class="empty">
						<span class="e-ic" aria-hidden="true">○</span>
						<p><b>СЕС немає</b></p>
						<a class="btn btn-sun btn-sm" href="/solar/{b.id}"><Icon name="sun" size={16} /> Потенціал даху</a>
						{#if editable}<button type="button" class="btn btn-secondary btn-sm" onclick={() => (editOpen = true)}>Додати СЕС</button>{/if}
					</div>
				{/if}
			</section>
		{/if}

		<!-- ============ 3. Енергія ============ -->
		<section class="sec" aria-labelledby="en-h">
			<h2 id="en-h"><span class="si en" aria-hidden="true"><Icon name="bolt" size={18} /></span>Енергія <small>· {pLabel}, кВт·год</small></h2>
			{#if !hasCons && !(ses && e?.gen_kwh)}
				<div class="empty"><span class="e-ic" aria-hidden="true">?</span><p><b>Немає даних про споживання</b></p></div>
			{:else if e}
				{#key period}
					<div class="tiles t5">
						{#if ses}<ObjTile i={0} icon="sun" tone="sun" label="Згенеровано" value={e.gen_kwh} />{/if}
						<ObjTile i={1} icon="plug" tone="cons" label="Спожито" value={e.cons_kwh} />
						{#if ses}
							<ObjTile i={2} icon="check" tone="good" label="Власне використано" value={e.self_kwh} />
							<ObjTile i={3} icon="chart" tone="warn" label="Надлишок" value={e.surplus_kwh} />
						{/if}
						{#if ses}
							<ObjTile i={4} icon="grid" tone="grid" label="З мережі" value={e.grid_kwh} />
						{:else if b.heated_area}
							<ObjTile i={2} icon="building" label="На 1 м²" value={(e.cons_kwh ?? 0) / Number(b.heated_area)} decimals={period === 'year' ? 1 : 2} unit="кВт·год" />
						{/if}
					</div>
				{/key}
			{/if}
			{#if d.monthly.some((x) => (x.cons_kwh ?? 0) > 0 || (ses && (x.gen_kwh ?? 0) > 0))}
				<div class="panel chart">
					<ObjMonthChart data={d.monthly} hasSes={!!ses} />
				</div>
			{/if}
		</section>

		<!-- ============ 4. Фінанси ============ -->
		{#if fin && (hasCons || ses)}
			<section class="sec" aria-labelledby="fi-h">
				<h2 id="fi-h"><span class="si fi" aria-hidden="true"><Icon name="wallet" size={18} /></span>Фінанси</h2>
				<ObjFinance {d} showSes={!!ses} />
				{#if noCost}
					<div class="empty slim">
						<span class="e-ic" aria-hidden="true">₴</span>
						<p><b>Немає даних про вартість</b></p>
						{#if editable}<button type="button" class="btn btn-sm" onclick={() => (editOpen = true)}>Внести вартість</button>{/if}
					</div>
				{/if}
			</section>
		{/if}

		<!-- ============ 5. Лічильники ============ -->
		{#if meters && (meters.electricity !== null || meters.total !== null)}
			<section class="sec" aria-labelledby="me-h">
				<h2 id="me-h"><span class="si me" aria-hidden="true"><Icon name="gauge" size={18} /></span>Лічильники</h2>
				<div class="meters tnum">
					<span><Icon name="bolt" size={16} /> Електроенергія <b>{num(meters.electricity)}</b></span>
					<span><Icon name="gauge" size={16} /> Усього <b>{num(meters.total)}</b></span>
				</div>
			</section>
		{/if}

		<!-- ============ 6. Оперативне ============ -->
		<section class="sec more" aria-label="Детальніше">
			{#if bat && site && hasCons}
				<Disclosure summary="Що зараз" hint={m ? `${m.time}` : ''}>
					<Distribution d={site.distribution} hasSes={!!ses} solarHref="/solar/{b.id}" />
					<div class="panel chart">
						<HourlyChart hours={site.hourly} nowHour={m?.hour ?? null} nowMinute={m?.minute ?? 0} peakHour={site.today.peak_kw > 0 ? site.today.peak_hour : null} />
					</div>
				</Disclosure>
			{/if}
			{#if bat && hasCons}
				<Disclosure summary="Якщо вимкнуть світло">
					<OutageSimulator siteId={b.id} startDefault={m && m.hour < 23 ? m.hour + 1 : 18} />
				</Disclosure>
			{/if}
			<Disclosure summary="Сонце завтра">
				<ForecastCard kw={ses?.total_kw ?? null} />
			</Disclosure>
			{#if !sens}
				<p class="lock-chip">
					<Icon name="lock" size={14} /> Дані СЕС — після входу
					{#if !isInternal(user)}<a href="/login?next=/object/{b.id}">Увійти</a>{/if}
				</p>
				<a class="btn btn-sun btn-sm" href="/solar/{b.id}"><Icon name="sun" size={16} /> Потенціал СЕС на даху</a>
			{/if}
		</section>
	</div>

	{#if editable}
		<ObjEditDrawer bind:open={editOpen} ses={d.ses} costs={d.costs} {onsave} />
	{/if}
{/if}

{#if toast}
	<div class="toast" class:bad={!toast.ok} role="status" aria-live="polite">
		{#if toast.ok}<Icon name="check" size={18} stroke={2.4} />{:else}<Icon name="alert" size={18} />{/if}
		{toast.text}
	</div>
{/if}

<style>
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
		gap: 1.75rem;
		transition: opacity var(--dur-base);
	}
	.obj.stale {
		opacity: 0.6;
	}
	.hero {
		display: flex;
		justify-content: space-between;
		gap: 1.5rem;
		flex-wrap: wrap;
		animation: obj-in 0.45s var(--ease-out) both;
	}
	.h-main {
		min-width: 0;
		flex: 1 1 360px;
	}
	.eyebrow {
		margin: 0 0 0.25rem;
	}
	h1 {
		margin: 0;
		font-size: clamp(1.35rem, 2.6vw, 1.9rem);
		line-height: 1.2;
		color: var(--ink);
		overflow-wrap: anywhere;
	}
	.place {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		margin: 0.4rem 0 0;
		color: var(--muted);
	}
	.facts {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem 1rem;
		margin: 0.6rem 0 0;
		font-size: var(--fs-sm);
		color: var(--muted);
	}
	.facts span {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
	}
	.h-side {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 0.75rem;
	}
	.kbig {
		display: grid;
		justify-items: end;
		gap: 0.3rem;
	}
	.k-l {
		font-size: var(--fs-xs);
		color: var(--muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.seg {
		display: inline-flex;
		padding: 3px;
		border-radius: 999px;
		background: var(--neutral-soft);
	}
	.seg button {
		border: 0;
		background: transparent;
		padding: 0.45rem 0.95rem;
		border-radius: 999px;
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
	.seg button:focus-visible {
		outline: 3px solid var(--focus);
		outline-offset: 1px;
	}
	.edit {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.sec {
		display: grid;
		gap: 0.75rem;
		min-width: 0;
	}
	h2 {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		margin: 0;
		font-size: var(--fs-xl);
		color: var(--ink);
	}
	h2 small {
		font-size: var(--fs-sm);
		font-weight: 500;
		color: var(--muted);
	}
	.si {
		display: grid;
		place-items: center;
		width: 2rem;
		height: 2rem;
		border-radius: 9px;
	}
	.si.sun { background: var(--sun-soft); color: var(--sun-ink); }
	.si.en { background: var(--accent-soft); color: var(--cons); }
	.si.fi { background: var(--surplus-soft); color: var(--surplus-ink); }
	.si.me { background: var(--neutral-soft); color: var(--muted); }
	.tiles {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
		gap: 0.75rem;
	}
	.tiles.t5 {
		grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
	}
	.chart {
		padding: 1rem;
	}
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
		gap: 0.6rem;
	}
	.meters span {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.5rem 0.85rem;
		border-radius: 999px;
		background: var(--surface);
		border: 1px solid var(--card-line);
		font-size: var(--fs-sm);
		color: var(--muted);
	}
	.meters b {
		color: var(--ink);
		font-size: var(--fs-md);
	}
	.more {
		gap: 0.5rem;
	}
	.lock-chip {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		justify-self: start;
		margin: 0.25rem 0;
		padding: 0.3rem 0.7rem;
		border-radius: 999px;
		background: var(--neutral-soft);
		font-size: var(--fs-xs);
		color: var(--muted);
	}
	.more > .btn {
		justify-self: start;
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
		border-radius: 999px;
		background: var(--ok);
		color: #fff;
		font-weight: 600;
		box-shadow: var(--shadow-lg);
		animation: toast-in var(--dur-base) var(--ease-spring);
	}
	.toast.bad {
		background: var(--bad);
	}
	@keyframes obj-in {
		from {
			opacity: 0;
			transform: translateY(8px);
		}
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
		.obj {
			gap: 1.25rem;
		}
		.h-side {
			align-items: stretch;
			width: 100%;
		}
		.kbig {
			display: flex;
			justify-content: space-between;
			align-items: center;
		}
		.seg {
			display: flex;
		}
		.seg button {
			flex: 1;
		}
		.tiles,
		.tiles.t5 {
			grid-template-columns: 1fr 1fr;
			gap: 0.5rem;
		}
		.chart {
			padding: 0.75rem 0.5rem;
		}
	}
</style>
