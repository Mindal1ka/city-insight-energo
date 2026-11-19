<script lang="ts">
	// Сторінка об'єкта: паспорт, станція, генерація/споживання, ліміти, погодинний графік і розподіл енергії
	import { page } from '$app/state';
	import { api, errMessage, ApiError, type SiteDetail } from '#lib/api.ts';
	import { num, energy, date, moment, hh } from '#lib/format.ts';
	import { viewFrom, withView } from '#lib/view.ts';
	import Status from '#lib/Status.svelte';
	import StatusTag from '#lib/StatusTag.svelte';
	import DemoPill from '#lib/DemoPill.svelte';
	import ViewSwitch from '#lib/ViewSwitch.svelte';
	import Icon from '#lib/Icon.svelte';
	import HourlyChart from '#lib/HourlyChart.svelte';
	import Meter from '#lib/Meter.svelte';
	import Distribution from '#lib/Distribution.svelte';

	const id = $derived(page.params.id ?? '');
	const view = $derived(viewFrom(page.url));
	const tab = $derived(page.url.searchParams.get('tab') === 'distribution' ? 'distribution' : 'overview');

	let s = $state<SiteDetail | null>(null);
	let error = $state<string | null>(null);
	let notFound = $state(false);
	let loading = $state(true);

	let seq = 0;
	async function load(bid: string, v: typeof view) {
		const my = ++seq;
		loading = true;
		error = null;
		notFound = false;
		try {
			const d = await api.site(bid, v);
			if (my === seq) s = d;
		} catch (e) {
			if (my !== seq) return;
			if (e instanceof ApiError && e.status === 404) notFound = true;
			else error = errMessage(e);
			s = null;
		} finally {
			if (my === seq) loading = false;
		}
	}
	$effect(() => {
		load(id, view);
	});

	const b = $derived(s?.building);
	const ses = $derived(s?.ses ?? null);
	const status = $derived(!s ? 'no_ses' : !ses ? 'no_ses' : s.distribution.balance_kwh >= 0 ? 'surplus' : 'deficit');
	const m = $derived(moment(s?.now));
	const place = $derived.by(() => {
		if (!b) return '';
		if (b.city && b.address.includes(b.city)) return b.address;
		return b.city === 'Полтава' ? `м. Полтава, ${b.address}` : [b.city, b.address].filter(Boolean).join(', ');
	});
	const isDemoSes = $derived(!!ses && (ses.source ?? 'ДЕМО') !== 'CSV');
	const genPeriod = $derived(energy(s?.period.generated_kwh));
	const consPeriod = $derived(energy(s?.period.consumed_kwh));
	const selfShare = $derived(
		s && s.today.consumed_kwh > 0 ? (s.today.self_kwh / s.today.consumed_kwh) * 100 : null
	);
	const noData = $derived(!!s && s.today.consumed_kwh === 0 && !s.building.elec_kwh_2025);

	function tabHref(t: 'overview' | 'distribution'): string {
		return withView(`/object/${id}`, view, t === 'distribution' ? { tab: 'distribution' } : {});
	}
</script>

<svelte:head><title>{b ? `${b.name} · ` : ''}Об’єкт · City Insight Map · Енергія</title></svelte:head>

<p class="back no-print">
	<a href={withView('/', view)}><Icon name="arrow-left" size={18} /> Усі об’єкти</a>
</p>

{#if notFound}
	<div class="notice notice-warn">
		<p><strong>Об’єкт не знайдено.</strong> Можливо, після оновлення даних змінився його номер. <a href={withView('/', view)}>Оберіть об’єкт зі списку</a>.</p>
	</div>
{/if}
<Status loading={loading && !s} {error} retry={() => load(id, view)} />

{#if s && b}
	<div class="obj" class:stale={loading}>
		<!-- Шапка об'єкта -->
		<section class="panel hero" aria-labelledby="obj-h">
			<div class="hero-main">
				<p class="eyebrow">{b.category_short}</p>
				<h1 id="obj-h">{b.name}</h1>
				<p class="place"><Icon name="pin" size={18} /> {place}</p>
				<ul class="facts">
					<li><span>Опалювана площа</span><b class="tnum">{b.heated_area ? `${num(b.heated_area)} м²` : '—'}</b></li>
					<li><span>Поверхів</span><b class="tnum">{b.floors ?? '—'}</b></li>
					<li><span>Електроенергія 2025</span><b class="tnum">{b.elec_kwh_2025 ? `${num(b.elec_kwh_2025)} кВт·год` : 'немає даних'}</b></li>
					<li class="src"><span class="real">дані UMUNI · реальні</span></li>
				</ul>
			</div>
			<div class="hero-side">
				<StatusTag {status} kwh={ses ? s.distribution.balance_kwh : null} size="lg" />
				<p class="hint-s">
					{#if ses}
						баланс до кінця дня
					{:else}
						сонячної станції немає
					{/if}
				</p>
				<ViewSwitch now={s.now} />
			</div>
		</section>

		<nav class="seg tabs" aria-label="Розділи об’єкта">
			<a href={tabHref('overview')} aria-current={tab === 'overview' ? 'page' : undefined} data-sveltekit-reset="false" data-sveltekit-replacestate>
				<Icon name="building" size={18} /> Огляд об’єкта
			</a>
			<a href={tabHref('distribution')} aria-current={tab === 'distribution' ? 'page' : undefined} data-sveltekit-reset="false" data-sveltekit-replacestate>
				<Icon name="bolt" size={18} /> Розподілення енергії
			</a>
		</nav>

		{#if tab === 'overview'}
			<div class="fade-in stack">
				{#if !ses}
					<a class="cta" href="/solar/{b.id}">
						<span class="cta-ic" aria-hidden="true"><Icon name="sun" size={30} /></span>
						<span class="cta-txt">
							<strong>СЕС немає — подивитися рекомендацію</strong>
							<span>Скільки міг би згенерувати дах цієї будівлі, яка потужність потрібна і за скільки окупиться (PVGIS, реальне споживання UMUNI).</span>
						</span>
						<Icon name="arrow-right" size={24} />
					</a>
				{/if}

				{#if noData}
					<div class="notice notice-warn">
						<p>У UMUNI немає даних про електроенергію цієї будівлі, тому добовий профіль і ліміти не розраховано.</p>
					</div>
				{/if}

				<!-- Ключові числа -->
				<section class="kpis" class:three={!ses} aria-label="Генерація і споживання">
					{#if ses}
						<div class="kpi">
							<p class="k-l"><span class="ki sun"><Icon name="sun" size={20} /></span>Згенеровано сьогодні</p>
							<p class="k-v"><span class="big-num">{num(s.today.generated_kwh, 1)}</span><span class="unit-s">кВт·год</span></p>
							<p class="k-s">
								за весь період: <b class="tnum">{genPeriod.v} {genPeriod.u}</b>
							</p>
							<p class="k-src">з {date(s.period.since)} · <DemoPill align="left" /></p>
						</div>
					{/if}
					<div class="kpi">
						<p class="k-l"><span class="ki navy"><Icon name="plug" size={20} /></span>Спожито сьогодні</p>
						<p class="k-v"><span class="big-num">{num(s.today.consumed_kwh, 1)}</span><span class="unit-s">кВт·год</span></p>
						<p class="k-s">за весь період: <b class="tnum">{consPeriod.v} {consPeriod.u}</b></p>
						<p class="k-src">з {date(s.period.consumed_since ?? '2025-01-01')} · <span class="real">дані UMUNI</span></p>
					</div>
					{#if ses}
						<div class="kpi">
							<p class="k-l"><span class="ki green"><Icon name="check" size={20} /></span>Покрито власною СЕС</p>
							<p class="k-v"><span class="big-num">{num(selfShare, 0)}</span><span class="unit-s">%</span></p>
							<p class="k-s">з мережі: <b class="tnum">{num(s.today.from_grid_kwh, 1)} кВт·год</b></p>
							<p class="k-src">сьогодні · в акумулятор {num(s.today.to_battery_kwh, 1)} кВт·год</p>
						</div>
						<div class="kpi">
							<p class="k-l"><span class="ki green"><Icon name="wallet" size={20} /></span>Заощаджено</p>
							<p class="k-v"><span class="big-num">{num(s.period.saved_uah, 0)}</span><span class="unit-s">грн</span></p>
							<p class="k-s">за {num(s.period.days)} днів роботи станції</p>
							<p class="k-src">з {date(s.period.since)} · <DemoPill align="left" /></p>
						</div>
					{:else}
						<div class="kpi">
							<p class="k-l"><span class="ki navy"><Icon name="gauge" size={20} /></span>Пікове навантаження</p>
							<p class="k-v"><span class="big-num">{num(s.today.peak_kw, 1)}</span><span class="unit-s">кВт</span></p>
							<p class="k-s">о {hh(s.today.peak_hour)}</p>
							<p class="k-src">типовий добовий профіль · <DemoPill align="left" /></p>
						</div>
						<div class="kpi">
							<p class="k-l"><span class="ki navy"><Icon name="wallet" size={20} /></span>Вартість сьогодні</p>
							<p class="k-v"><span class="big-num">{num(s.today.consumed_kwh * s.limits.tariff_uah_kwh, 0)}</span><span class="unit-s">грн</span></p>
							<p class="k-s">за тарифом {num(s.limits.tariff_uah_kwh, 2)} грн/кВт·год</p>
							<p class="k-src">уся енергія — з мережі</p>
						</div>
					{/if}
				</section>

				<!-- Погодинний графік -->
				{#if !noData}
				<section class="panel" aria-labelledby="chart-h">
					<div class="panel-head">
						<div>
							<h2 id="chart-h">Сьогодні погодинно</h2>
							<p class="muted small sub">
								{#if m}{m.date} · зараз {m.time}{/if}
								{#if ses} · генерація, споживання й заряд акумулятора{:else} · споживання (СЕС немає){/if}
							</p>
						</div>
						<DemoPill />
					</div>
					<HourlyChart hours={s.hourly} nowHour={m?.hour ?? null} nowMinute={m?.minute ?? 0} peakHour={s.today.peak_kw > 0 ? s.today.peak_hour : null} />
				</section>
				{/if}

				<div class="two">
					<!-- Станція -->
					{#if ses}
						<section class="panel" aria-labelledby="ses-h">
							<div class="panel-head">
								<h2 id="ses-h">Сонячна станція</h2>
								{#if isDemoSes}<DemoPill />{:else}<span class="pill">реєстр міста (CSV)</span>{/if}
							</div>
							<div class="equip">
								<div class="eq big">
									<span class="eq-ic sun"><Icon name="panel" size={22} /></span>
									<div>
										<p class="eq-l">Сонячні панелі</p>
										<p class="eq-v tnum"><b>{num(ses.panels_count)}</b> шт × <b>{num(ses.panel_w)}</b> Вт = <b>{num(ses.total_kw, 1)}</b> кВт</p>
									</div>
								</div>
								<div class="eq">
									<span class="eq-ic navy"><Icon name="inverter" size={22} /></span>
									<div>
										<p class="eq-l">Інвертор</p>
										<p class="eq-v"><b>{ses.inverter_model}</b></p>
										<p class="eq-s tnum">{num(ses.inverter_kw, 1)} кВт</p>
									</div>
								</div>
								<div class="eq">
									<span class="eq-ic teal"><Icon name="battery" size={22} /></span>
									<div>
										<p class="eq-l">Акумулятор</p>
										<p class="eq-v tnum"><b>{num(ses.battery_kwh, 1)}</b> кВт·год</p>
										<p class="eq-s tnum">потужність {num(ses.battery_kw, 1)} кВт</p>
									</div>
								</div>
								<div class="eq">
									<span class="eq-ic navy"><Icon name="plug" size={22} /></span>
									<div>
										<p class="eq-l">Приєднана потужність</p>
										<p class="eq-v tnum"><b>{num(ses.connected_kw, 1)}</b> кВт</p>
										<p class="eq-s">запущено {date(ses.launched)}</p>
									</div>
								</div>
							</div>
							{#if ses.battery_within_connected}
								<p class="check ok" role="status">
									<Icon name="check" size={20} stroke={2.4} />
									<span><b>Перевірка пройдена:</b> потужність акумулятора {num(ses.battery_kw, 1)} кВт ≤ приєднаної потужності {num(ses.connected_kw, 1)} кВт.</span>
								</p>
							{:else}
								<p class="check bad" role="alert">
									<Icon name="alert" size={20} stroke={2.2} />
									<span><b>Увага:</b> потужність акумулятора {num(ses.battery_kw, 1)} кВт перевищує приєднану потужність {num(ses.connected_kw, 1)} кВт. Потрібно перевірити налаштування інвертора або договір приєднання.</span>
								</p>
							{/if}
						</section>
					{/if}

					<!-- Ліміти -->
					{#if !noData}
					<section class="panel limits" aria-labelledby="lim-h">
						<div class="panel-head">
							<h2 id="lim-h">Ліміти</h2>
							<DemoPill text="Лімітів у пакеті даних міста немає; показано змодельовані значення" />
						</div>
						<Meter
							label="Грошовий ліміт на місяць"
							used={s.limits.money_month_used_uah}
							limit={s.limits.money_month_uah}
							pct={s.limits.money_month_pct}
							over={s.limits.over_money}
							unit="грн"
						/>
						<Meter
							label="Ліміт на день"
							used={s.limits.energy_day_used_kwh}
							limit={s.limits.energy_day_kwh}
							pct={s.limits.energy_day_pct}
							over={s.limits.over_day}
							unit="кВт·год"
							digits={1}
							hint="Тариф {num(s.limits.tariff_uah_kwh, 2)} грн/кВт·год"
						/>
					</section>
					{/if}
				</div>

				{#if s.notes.length}
					<ul class="notes">
						{#each s.notes as n, i (i)}
							<li><Icon name="info" size={16} /> {n}</li>
						{/each}
					</ul>
				{/if}
			</div>
		{:else}
			<div class="fade-in">
				<Distribution d={s.distribution} hasSes={!!ses} solarHref="/solar/{b.id}" />
			</div>
		{/if}
	</div>
{/if}

<style>
	.back {
		margin: 0 0 1rem;
	}
	.back a {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		font-weight: 600;
		text-decoration: none;
	}
	.back a:hover {
		text-decoration: underline;
	}
	.obj {
		transition: opacity 0.2s;
	}
	.stale {
		opacity: 0.55;
	}
	.hero {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		gap: 1.25rem 2rem;
		margin-bottom: 1.25rem;
		position: relative;
		overflow: hidden;
		background:
			radial-gradient(600px 220px at 100% 0%, rgba(245, 165, 36, 0.12), transparent 70%),
			var(--surface);
	}
	.hero-main {
		flex: 1 1 32rem;
		min-width: 0;
	}
	h1 {
		font-size: 2.1rem;
		letter-spacing: -0.015em;
		margin: 0.25rem 0 0.4rem;
	}
	.place {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		color: #3d4857;
		font-size: 1.05rem;
		margin-bottom: 1rem;
	}
	.facts {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem 1.75rem;
		align-items: flex-end;
	}
	.facts li {
		display: flex;
		flex-direction: column;
	}
	.facts span {
		font-size: 0.8125rem;
		color: var(--muted);
	}
	.facts b {
		font-size: 1.1rem;
	}
	.facts .src {
		justify-content: flex-end;
	}
	.real {
		display: inline-flex;
		align-items: center;
		padding: 0.1rem 0.55rem;
		border-radius: 999px;
		background: #e6eef8;
		color: #1f4f84 !important;
		font-size: 0.75rem !important;
		font-weight: 700;
		letter-spacing: 0.03em;
		white-space: nowrap;
	}
	.hero-side {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 0.4rem;
	}
	.hint-s {
		margin: 0 0 0.6rem;
		font-size: 0.85rem;
		color: var(--muted);
	}
	.tabs {
		margin-bottom: 1.25rem;
	}
	.stack {
		display: grid;
		gap: 1.25rem;
	}
	.cta {
		display: flex;
		align-items: center;
		gap: 1.1rem;
		padding: 1.1rem 1.4rem;
		border-radius: var(--radius-lg);
		background: linear-gradient(135deg, #fffaf0, #ffefc9);
		border: 1px solid #f0d49b;
		color: #3b2400;
		text-decoration: none;
		box-shadow: var(--shadow-md);
		transition:
			transform 0.18s var(--ease),
			box-shadow 0.18s;
	}
	.cta:hover {
		color: #3b2400;
		transform: translateY(-2px);
		box-shadow: var(--shadow-lg);
	}
	.cta-ic {
		display: grid;
		place-items: center;
		width: 3.5rem;
		height: 3.5rem;
		flex: none;
		border-radius: 16px;
		background: var(--sun);
	}
	.cta-txt {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}
	.cta-txt strong {
		font-size: 1.2rem;
	}
	.cta-txt span {
		color: #5a4310;
	}
	.kpis {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 1.25rem;
	}
	.kpi {
		background: var(--surface);
		border: 1px solid #e3e8ef;
		border-radius: var(--radius-lg);
		box-shadow: var(--shadow-md);
		padding: 1.2rem 1.3rem;
		display: flex;
		flex-direction: column;
	}
	.kpis.three {
		grid-template-columns: repeat(3, minmax(0, 1fr));
	}
	.k-l {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		font-weight: 600;
		color: #2b3645;
		margin: 0 0 0.5rem;
	}
	.ki {
		display: grid;
		place-items: center;
		width: 2.2rem;
		height: 2.2rem;
		border-radius: 11px;
		flex: none;
	}
	.ki.sun,
	.eq-ic.sun {
		background: var(--sun-soft);
		color: var(--sun-ink);
	}
	.ki.navy,
	.eq-ic.navy {
		background: #e6eef8;
		color: var(--navy-3);
	}
	.ki.green {
		background: var(--surplus-soft);
		color: var(--surplus-ink);
	}
	.eq-ic.teal {
		background: #dff3f0;
		color: #0f766e;
	}
	.k-v {
		margin: 0;
	}
	.k-v .big-num {
		font-size: 2.6rem;
	}
	.k-s {
		margin: 0.4rem 0 0;
		color: #3d4857;
	}
	.k-src {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.35rem;
		margin: auto 0 0;
		padding-top: 0.6rem;
		font-size: 0.8125rem;
		color: var(--muted);
	}
	.panel h2 {
		font-size: 1.3rem;
	}
	.sub {
		margin: 0.15rem 0 0;
	}
	.two {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 30rem), 1fr));
		gap: 1.25rem;
	}
	.equip {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 1rem 1.25rem;
	}
	.eq {
		display: flex;
		gap: 0.8rem;
		align-items: flex-start;
		padding: 0.9rem;
		border-radius: 12px;
		background: #f7f9fc;
		border: 1px solid #edf1f5;
	}
	.eq.big {
		grid-column: 1 / -1;
	}
	.eq-ic {
		display: grid;
		place-items: center;
		width: 2.6rem;
		height: 2.6rem;
		border-radius: 12px;
		flex: none;
	}
	.eq-l {
		margin: 0;
		font-size: 0.8125rem;
		font-weight: 600;
		color: var(--muted);
	}
	.eq-v {
		margin: 0.1rem 0 0;
		font-size: 1.05rem;
		line-height: 1.35;
	}
	.eq.big .eq-v {
		font-size: 1.3rem;
	}
	.eq-s {
		margin: 0.1rem 0 0;
		font-size: 0.875rem;
		color: #3d4857;
	}
	.check {
		display: flex;
		gap: 0.6rem;
		align-items: flex-start;
		margin: 1rem 0 0;
		padding: 0.8rem 1rem;
		border-radius: 12px;
		border: 1px solid;
		line-height: 1.45;
	}
	.check :global(.icon) {
		margin-top: 0.05rem;
	}
	.check.ok {
		background: var(--surplus-soft);
		border-color: #b5dcc0;
		color: var(--surplus-ink);
	}
	.check.bad {
		background: var(--deficit-soft);
		border-color: #f0b89f;
		color: var(--deficit-ink);
	}
	.limits {
		display: flex;
		flex-direction: column;
		gap: 1.6rem;
	}
	.limits .panel-head {
		margin-bottom: 0;
	}
	.notes {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.35rem;
		font-size: 0.875rem;
		color: var(--muted);
	}
	.notes li {
		display: flex;
		gap: 0.45rem;
		align-items: flex-start;
	}
	.notes :global(.icon) {
		margin-top: 0.15rem;
	}
	@media (max-width: 1200px) {
		.kpis,
		.kpis.three {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
	@media (max-width: 1100px) {
		.hero-side {
			align-items: flex-start;
			flex: 1 1 100%;
		}
	}
	@media (max-width: 760px) {
		h1 {
			font-size: 1.6rem;
		}
	}
	@media (max-width: 560px) {
		.kpis,
		.kpis.three,
		.equip {
			grid-template-columns: 1fr;
		}
	}
</style>
