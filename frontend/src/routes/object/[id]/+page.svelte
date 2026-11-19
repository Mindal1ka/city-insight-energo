<script lang="ts">
	// Сторінка об'єкта. Прогресивне розкриття:
	//  1) «відповідь за 5 секунд» — назва, одне просте речення, 3–4 картки, ОДНА рекомендована дія;
	//  2) розділи простими словами: зараз → відключення → сонце завтра → що зробити → технічні дані;
	//  другорядні й технічні числа — у «Детальніше».
	import { page } from '$app/state';
	import { tick } from 'svelte';
	import { api, errMessage, ApiError, type SiteDetail } from '#lib/api.ts';
	import { num, signed, date, moment, hh } from '#lib/format.ts';
	import { viewFrom, withView } from '#lib/view.ts';
	import { duration, type Improvement } from '#lib/api-independence.ts';
	import { isReduced } from '#lib/motion.ts';
	import Status from '#lib/Status.svelte';
	import DemoPill from '#lib/DemoPill.svelte';
	import ViewSwitch from '#lib/ViewSwitch.svelte';
	import Icon from '#lib/Icon.svelte';
	import IndexBadge from '#lib/IndexBadge.svelte';
	import HourlyChart from '#lib/HourlyChart.svelte';
	import Meter from '#lib/Meter.svelte';
	import Distribution from '#lib/Distribution.svelte';
	import IndependenceCard from '#lib/IndependenceCard.svelte';
	import OutageSimulator from '#lib/OutageSimulator.svelte';
	import ForecastCard from '#lib/ForecastCard.svelte';
	import StatCard from '#lib/StatCard.svelte';
	import Reveal from '#lib/Reveal.svelte';
	import Disclosure from '#lib/Disclosure.svelte';
	import Term from '#lib/Term.svelte';
	import { independenceApi, type IndependenceDetail } from '#lib/api-independence.ts';
	import { VIEWS } from '#lib/api.ts';
	import CityMap from '#lib/CityMap.svelte';
	import { loadMap, hasCoords, type MapPoint } from '#lib/api-map.ts';

	const id = $derived(page.params.id ?? '');
	const view = $derived(viewFrom(page.url));

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

	// Енергонезалежність закладу — окремий запит; якщо не вдався, решта сторінки працює
	let ind = $state<IndependenceDetail | null>(null);
	let indError = $state<string | null>(null);
	let iseq = 0;
	async function loadInd(bid: string, v: typeof view) {
		const my = ++iseq;
		indError = null;
		try {
			const d = await independenceApi.one(bid, v);
			if (my === iseq) ind = d;
		} catch (e) {
			if (my === iseq) {
				ind = null;
				indError = errMessage(e);
			}
		}
	}
	$effect(() => {
		loadInd(id, view);
	});
	const outageDay = $derived(VIEWS[view].day ?? null);

	const b = $derived(s?.building);
	const ses = $derived(s?.ses ?? null);
	const it = $derived(ind && String(ind.item.id) === String(id) ? ind.item : null);
	const m = $derived(moment(s?.now));
	const place = $derived.by(() => {
		if (!b) return '';
		if (b.city && b.address.includes(b.city)) return b.address;
		return b.city === 'Полтава' ? `м. Полтава, ${b.address}` : [b.city, b.address].filter(Boolean).join(', ');
	});
	const isDemoSes = $derived(!!ses && (ses.source ?? 'ДЕМО') !== 'CSV');
	const selfShare = $derived(
		s && s.today.consumed_kwh > 0 ? (s.today.self_kwh / s.today.consumed_kwh) * 100 : null
	);
	const noData = $derived(!!s && ((s.today.consumed_kwh === 0 && !s.building.elec_kwh_2025) || it?.data_ok === false));
	const batKwh = $derived(it?.battery_kwh ?? ses?.battery_kwh ?? 0);
	const hasBat = $derived(batKwh > 0);
	const autonomy = $derived(it ? (hasBat ? it.autonomy_hours : 0) : null);
	const costToday = $derived(s ? s.today.consumed_kwh * s.limits.tariff_uah_kwh : null);

	// --- Одна рекомендована дія ---
	const WORD: Record<string, number> = { висока: 1, середня: 2, низька: 3 };
	const prio = (p: Improvement['priority']) =>
		typeof p === 'number' ? p : (WORD[p] ?? (Number.parseFloat(p) || 9));
	const steps = $derived(ind ? [...ind.improve].sort((a, c) => prio(a.priority) - prio(c.priority)) : []);
	/** Перше речення — для короткого підпису; решта лишається в розділі «Що зробити» */
	const firstSentence = (t: string) => t.split(/(?<=\.)\s+(?=[А-ЯІЇЄҐA-Z])/)[0] ?? t;
	/** «Розширити СЕС на 1,9 кВт СЕС» → «Розширити СЕС на 1,9 кВт» (повтор у тексті з бекенду) */
	const tidy = (t: string) => t.replace(/^(.*СЕС.*?)\s+СЕС$/, '$1');
	const solarHref = $derived(b ? withView(`/solar/${b.id}`, view) : '/solar');
	const primary = $derived.by(() => {
		const st = steps[0];
		if (st) {
			const solar = /СЕС|сонячн/i.test(st.action);
			return {
				title: tidy(st.action),
				text: firstSentence(st.effect),
				href: solar ? solarHref : '#todo',
				cta: solar ? 'Розрахунок для даху' : 'Як це зробити',
				external: solar
			};
		}
		if (s && !ses && !noData)
			return {
				title: 'Перевірити, скільки енергії дасть сонячна станція на даху',
				text: 'Розрахунок потужності, вартості й окупності для цієї будівлі.',
				href: solarHref,
				cta: 'Розрахунок для даху',
				external: true
			};
		return null;
	});

	// --- Тони карток: колір + значок + прихований текст ---
	type Tone = 'neutral' | 'good' | 'warn' | 'bad';
	const shareTone = (v: number | null): Tone => (v === null ? 'neutral' : v >= 30 ? 'good' : v >= 10 ? 'neutral' : 'warn');
	const autoTone = (h: number | null): Tone => (h === null ? 'neutral' : h >= 4 ? 'good' : h > 0 ? 'warn' : 'bad');
	const limitTone = (p: number | null, over: boolean): Tone =>
		p === null ? 'neutral' : over || p > 100 ? 'bad' : p >= 85 ? 'warn' : 'good';

	// --- Навігація по розділах ---
	const SECTIONS = $derived([
		{ id: 'now', label: 'Що зараз', icon: 'bolt' as const },
		{ id: 'outage', label: 'Якщо вимкнуть світло', icon: 'battery' as const },
		{ id: 'tomorrow', label: 'Сонце завтра', icon: 'sun' as const },
		{ id: 'todo', label: 'Що зробити', icon: 'check' as const },
		{ id: 'tech', label: ses ? 'Технічні дані станції' : 'Дані будівлі', icon: 'inverter' as const }
	]);
	function jump(e: MouseEvent, target: string) {
		const el = document.getElementById(target);
		if (!el) return;
		e.preventDefault();
		el.scrollIntoView({ behavior: isReduced() ? 'auto' : 'smooth', block: 'start' });
		// Фокус на заголовок розділу — для клавіатури й екранних зчитувачів
		const h = el.querySelector<HTMLElement>('h2');
		h?.focus({ preventScroll: true });
	}

	// Маленька мапа «де це» — лише розташування (без станцій і акумуляторів)
	let mapPts = $state<MapPoint[]>([]);
	loadMap()
		.then((m) => (mapPts = m.points))
		.catch(() => (mapPts = []));
	const here = $derived(mapPts.find((p) => String(p.id) === String(id) && hasCoords(p)) ?? null);

	// Старі посилання «?tab=distribution» ведуть до розділу «Що зараз з енергією»
	let jumped = '';
	$effect(() => {
		if (!s || page.url.searchParams.get('tab') !== 'distribution' || jumped === id) return;
		jumped = id;
		tick().then(() => document.getElementById('now')?.scrollIntoView({ block: 'start' }));
	});
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
	<div class="obj" class:stale={loading} aria-busy={loading}>
		<!-- ============ 1. Відповідь за 5 секунд ============ -->
		<section class="panel hero" aria-labelledby="obj-h">
			<div class="hero-top">
				<div class="hero-main">
					<p class="eyebrow rise" style="--d: 0ms">
						{b.category_short}
						{#if it?.critical}
							<span class="crit"><Icon name="alert" size={14} stroke={2.4} /> критичний заклад</span>
						{/if}
					</p>
					<h1 id="obj-h" class="rise" style="--d: 40ms">{b.name}</h1>
					<p class="place rise" style="--d: 80ms"><Icon name="pin" size={18} /> {place}</p>
				</div>
				<div class="hero-side rise" style="--d: 120ms">
					{#if it}
						<div class="idx">
							<span class="idx-l"><Term key="енергонезалежність">Енергонезалежність</Term></span>
							<IndexBadge index={it.index} cls={it.index_class} size="md" />
						</div>
					{/if}
					<ViewSwitch now={s.now} />
				</div>
			</div>

			<p class="answer rise" style="--d: 160ms">
				{#if noData}
					Про споживання електроенергії цієї будівлі <b>ще немає даних</b>, тому порахувати, скільки вона протримається без світла, поки неможливо.
				{:else}
					{#if ses}
						Сьогодні сонце покриває <b class="tnum">{num(selfShare, 0)} %</b> потреби закладу.
					{:else}
						Сонячної станції не зафіксовано — <b>електроенергія надходить з мережі</b>.
					{/if}
					{#if it}
						{#if !hasBat}
							<b class="bad-t">Резерв на випадок відключення не зафіксовано</b>.
						{:else if autonomy !== null}
							Якщо вимкнуть світло — протримається <b class="tnum">{duration(autonomy)}</b> <span class="demo-note">(за демо-моделлю)</span>.
						{/if}
					{/if}
				{/if}
			</p>

			<div class="stat-grid cards rise" style="--d: 220ms">
				{#if noData}
					<StatCard label="Споживання за 2025 рік" value={null} icon="plug" hint="У системі UMUNI немає даних лічильника." tone="warn" toneLabel="немає даних" />
					<StatCard label="Площа будівлі" value={b.heated_area} unit="м²" icon="building" hint="Опалювана площа за даними UMUNI." />
					<StatCard label="Поверхів" value={b.floors} icon="building" hint="Кількість поверхів будівлі." />
				{:else if ses}
					<StatCard label="Сонце покриває сьогодні" value={selfShare} unit="%" icon="sun" tone={shareTone(selfShare)} demo
						hint="Решту — {num(s.today.from_grid_kwh, 1)} кВт·год — бере з мережі.">
						<span class="mini-bar" aria-hidden="true"><i style="--w: {Math.min(100, selfShare ?? 0)}%"></i></span>
					</StatCard>
					<StatCard label="Без світла протримається" value={autonomy} format={duration} icon="battery" tone={autoTone(autonomy)} demo
						hint={hasBat ? `На акумуляторі ${num(batKwh, 1)} кВт·год, навіть уночі без сонця.` : 'Резерв не зафіксовано.'} />
					<StatCard label="До кінця дня" value={s.distribution.balance_kwh} format={(n) => signed(n, 1)} unit="кВт·год" icon="bolt"
						tone={s.distribution.enough ? 'good' : 'bad'} toneLabel={s.distribution.enough ? 'енергії достатньо' : 'енергії бракує'} demo
						hint={s.distribution.enough ? 'Сонця й акумулятора вистачить із запасом.' : `Бракує ${num(Math.abs(s.distribution.balance_kwh), 1)} кВт·год — докупимо з мережі.`} />
					<StatCard label="Заощаджено" value={s.period.saved_uah} unit="грн" icon="wallet" tone="good" toneLabel="економія" demo
						hint="За {num(s.period.days)} днів роботи станції — менше платимо за світло." />
				{:else}
					<StatCard label="Витрачено сьогодні" value={s.today.consumed_kwh} decimals={1} unit="кВт·год" icon="plug"
						hint="Сонячної станції не зафіксовано — енергія з мережі." />
					<StatCard label="Коштує сьогодні" value={costToday} unit="грн" icon="wallet"
						hint="За тарифом {num(s.limits.tariff_uah_kwh, 2)} грн за 1 кВт·год." />
					<StatCard label="Без світла протримається" value={autonomy} format={duration} icon="battery" tone={autoTone(autonomy)} demo
						hint={hasBat ? `На акумуляторі ${num(batKwh, 1)} кВт·год.` : 'Резерв не зафіксовано: у даних немає ні станції, ні акумулятора.'} />
					<StatCard label="Місячний ліміт використано" value={s.limits.money_month_pct} unit="%" icon="gauge"
						tone={limitTone(s.limits.money_month_pct, s.limits.over_money)} demo
						hint="{num(s.limits.money_month_used_uah)} з {num(s.limits.money_month_uah)} грн на цей місяць." />
				{/if}
			</div>

			{#if primary}
				<div class="action rise" style="--d: 300ms">
					<span class="act-ic" aria-hidden="true"><Icon name="arrow-right" size={24} stroke={2.4} /></span>
					<div class="act-txt">
						<p class="act-k">Що зробити насамперед</p>
						<p class="act-t">{primary.title}</p>
						<p class="act-s">{primary.text}</p>
					</div>
					{#if primary.external}
						<a class="btn btn-sun btn-lg act-btn" href={primary.href}>{primary.cta} <Icon name="arrow-right" size={18} /></a>
					{:else}
						<a class="btn btn-sun btn-lg act-btn" href={primary.href} onclick={(e) => jump(e, 'todo')}>{primary.cta} <Icon name="arrow-right" size={18} /></a>
					{/if}
				</div>
			{/if}
		</section>

		<!-- Зміст сторінки -->
		<nav class="toc no-print" aria-label="Розділи сторінки">
			{#each SECTIONS as sec, i (sec.id)}
				<a href="#{sec.id}" onclick={(e) => jump(e, sec.id)} class="rise" style="--d: {340 + i * 40}ms">
					<Icon name={sec.icon} size={16} /> {sec.label}
				</a>
			{/each}
		</nav>

		<!-- ============ 2. Що зараз з енергією ============ -->
		<section id="now" class="sec" aria-labelledby="now-h">
			<Reveal>
				<header class="sec-h">
					<span class="sec-ic now" aria-hidden="true"><Icon name="bolt" size={22} /></span>
					<div>
						<h2 id="now-h" tabindex="-1">Що зараз з енергією</h2>
						<p class="sec-sub">
							{#if m}Станом на {m.time}, {m.date}.{/if}
							{#if ses}Чи вистачить сонця й акумулятора до кінця дня.{:else}Скільки енергії ще знадобиться сьогодні.{/if}
						</p>
					</div>
				</header>
			</Reveal>

			{#if noData}
				<Reveal>
					<div class="notice notice-warn">
						<p>У UMUNI немає даних про електроенергію цієї будівлі, тому добовий профіль, баланс і ліміти не розраховано.</p>
					</div>
				</Reveal>
			{:else}
				<Reveal>
					<Distribution d={s.distribution} hasSes={!!ses} solarHref={solarHref} />
				</Reveal>

				<Reveal>
					<section class="panel" aria-labelledby="chart-h">
						<div class="panel-head">
							<div>
								<h3 id="chart-h">Як минає сьогоднішній день</h3>
								<p class="muted small sub">
									{#if ses}Помаранчеві стовпчики — скільки дало сонце, синя лінія — скільки витратив заклад.{:else}Синя лінія — скільки енергії витрачає заклад щогодини.{/if}
									Праворуч від позначки «зараз» — прогноз.
								</p>
							</div>
							<DemoPill />
						</div>
						<HourlyChart hours={s.hourly} nowHour={m?.hour ?? null} nowMinute={m?.minute ?? 0} peakHour={s.today.peak_kw > 0 ? s.today.peak_hour : null} />

						<Disclosure summary="Детальніше: за день, за весь час і ліміти" hint="{ses ? 9 : 5} показників">
							<div class="detail-grid">
								<div class="dg">
									<h4>Сьогодні</h4>
									<dl class="kv">
										{#if ses}
											<div><dt>Згенеровано сонцем</dt><dd>{num(s.today.generated_kwh, 1)} <small>кВт·год</small></dd></div>
										{/if}
										<div><dt>Витрачено закладом</dt><dd>{num(s.today.consumed_kwh, 1)} <small>кВт·год</small></dd></div>
										{#if ses}
											<div><dt>З них від власного сонця</dt><dd>{num(s.today.self_kwh, 1)} <small>кВт·год</small></dd></div>
											<div><dt>Куплено з мережі</dt><dd>{num(s.today.from_grid_kwh, 1)} <small>кВт·год</small></dd></div>
											<div><dt>Пішло в акумулятор</dt><dd>{num(s.today.to_battery_kwh, 1)} <small>кВт·год</small></dd></div>
										{/if}
									</dl>
								</div>
								<div class="dg">
									<h4>За весь час</h4>
									<dl class="kv">
										{#if ses}
											<div><dt>Згенеровано з {date(s.period.since)}</dt><dd>{num(s.period.generated_kwh)} <small>кВт·год</small></dd></div>
										{/if}
										<div><dt>Витрачено з {date(s.period.consumed_since ?? '2025-01-01')}</dt><dd>{num(s.period.consumed_kwh)} <small>кВт·год</small></dd></div>
										{#if ses}
											<div><dt>Заощаджено за {num(s.period.days)} днів</dt><dd>{num(s.period.saved_uah)} <small>грн</small></dd></div>
										{/if}
									</dl>
									<p class="src"><span class="real">споживання — реальні дані UMUNI</span>{#if ses}<DemoPill align="left" />{/if}</p>
								</div>
								<div class="dg limits">
									<h4>Ліміти <DemoPill text="Лімітів у пакеті даних міста немає; показано змодельовані значення" align="left" /></h4>
									<Meter
										label="Гроші на місяць"
										used={s.limits.money_month_used_uah}
										limit={s.limits.money_month_uah}
										pct={s.limits.money_month_pct}
										over={s.limits.over_money}
										unit="грн"
									/>
									<Meter
										label="Енергія на день"
										used={s.limits.energy_day_used_kwh}
										limit={s.limits.energy_day_kwh}
										pct={s.limits.energy_day_pct}
										over={s.limits.over_day}
										unit="кВт·год"
										digits={1}
										hint="Тариф {num(s.limits.tariff_uah_kwh, 2)} грн за 1 кВт·год"
									/>
								</div>
							</div>
						</Disclosure>
					</section>
				</Reveal>
			{/if}
		</section>

		<!-- ============ 3. Що буде, якщо вимкнуть світло ============ -->
		<section id="outage" class="sec" aria-labelledby="outage-h">
			<Reveal>
				<header class="sec-h">
					<span class="sec-ic out" aria-hidden="true"><Icon name="battery" size={22} /></span>
					<div>
						<h2 id="outage-h" tabindex="-1">Що буде, якщо вимкнуть світло</h2>
						<p class="sec-sub">Скільки заклад протримається на <Term key="акумулятор">акумуляторі</Term> і сонці без мережі.</p>
					</div>
				</header>
			</Reveal>
			{#if it && !noData}
				<Reveal>
					<div class="auto">
						<div class="au">
							<span class="au-ic night" aria-hidden="true">☾</span>
							<div>
								<p class="au-l">Уночі, без сонця</p>
								<p class="au-v tnum">{hasBat ? duration(it.autonomy_hours) : '0 хв'}</p>
							</div>
						</div>
						<div class="au">
							<span class="au-ic day" aria-hidden="true"><Icon name="sun" size={20} /></span>
							<div>
								<p class="au-l">Удень, коли світить сонце</p>
								<p class="au-v tnum">{#if it.autonomy_with_sun_capped}понад {/if}{it.has_ses || hasBat ? duration(it.autonomy_hours_with_sun) : '0 хв'}</p>
							</div>
						</div>
						<DemoPill align="left" text="Станції й акумулятори в пакеті міста не вказані; автономність розраховано на змодельованих даних і реальному споживанні UMUNI" />
						<p class="au-n">
							{#if hasBat}
								Це <Term key="автономність">автономність</Term> при звичайній роботі закладу. Змініть час і тривалість відключення нижче — побачите, що буде саме тоді.
							{:else}
								Резерв не зафіксовано: у даних немає акумулятора{#if it.has_ses}, а сонячна станція без акумулятора вимикається разом із мережею{/if}.
							{/if}
						</p>
					</div>
				</Reveal>
			{/if}
			{#if noData}
				<Reveal>
					<div class="notice notice-warn"><p>Без даних про споживання не можна порахувати, скільки протримається заклад.</p></div>
				</Reveal>
			{:else}
				<Reveal>
					<OutageSimulator siteId={b.id} day={outageDay} startDefault={m && m.hour < 23 ? m.hour + 1 : 18} />
				</Reveal>
			{/if}
		</section>

		<!-- ============ 4. Сонце завтра ============ -->
		<section id="tomorrow" class="sec" aria-labelledby="tomorrow-h">
			<Reveal>
				<header class="sec-h">
					<span class="sec-ic sun" aria-hidden="true"><Icon name="sun" size={22} /></span>
					<div>
						<h2 id="tomorrow-h" tabindex="-1">Сонце завтра</h2>
						<p class="sec-sub">
							{#if ses}Скільки виробить станція {num(ses.total_kw, 1)} <Term key="кВт">кВт</Term> за прогнозом погоди.{:else}Скільки дав би кожен 1 кВт сонячних панелей у Полтаві за прогнозом погоди.{/if}
						</p>
					</div>
				</header>
			</Reveal>
			<Reveal>
				<ForecastCard kw={ses?.total_kw ?? null} />
			</Reveal>
		</section>

		<!-- ============ 5. Що зробити ============ -->
		<section id="todo" class="sec" aria-labelledby="todo-h">
			<Reveal>
				<header class="sec-h">
					<span class="sec-ic todo" aria-hidden="true"><Icon name="check" size={22} /></span>
					<div>
						<h2 id="todo-h" tabindex="-1">Що зробити</h2>
						<p class="sec-sub">Кроки, щоб заклад менше залежав від мережі. Перший — найважливіший.</p>
					</div>
				</header>
			</Reveal>
			<Reveal>
				{#if ind}
					<IndependenceCard d={ind} solarHref={noData ? null : solarHref} />
				{:else if indError}
					<div class="notice notice-warn"><p>Рекомендації зараз недоступні: {indError}</p></div>
				{:else}
					<p class="muted" role="status">Завантаження рекомендацій…</p>
				{/if}
			</Reveal>
		</section>

		<!-- ============ 6. Технічні дані ============ -->
		<section id="tech" class="sec" aria-labelledby="tech-h">
			<Reveal>
				<header class="sec-h">
					<span class="sec-ic tech" aria-hidden="true"><Icon name="inverter" size={22} /></span>
					<div>
						<h2 id="tech-h" tabindex="-1">{ses ? 'Технічні дані станції' : 'Дані будівлі'}</h2>
						<p class="sec-sub">Для енергоменеджера: обладнання, будівля, джерела даних.</p>
					</div>
				</header>
			</Reveal>
			<div class="tech-grid" class:with-map={!!here}>
			<Reveal>
				<div class="panel tech">
					{#if ses}
						<div class="tech-sum">
							<div class="ts">
								<span class="eq-ic sun" aria-hidden="true"><Icon name="panel" size={22} /></span>
								<div>
									<p class="ts-l">Сонячні панелі</p>
									<p class="ts-v tnum"><b>{num(ses.total_kw, 1)}</b> <Term key="кВт">кВт</Term></p>
									<p class="ts-s">{num(ses.panels_count)} панелей</p>
								</div>
							</div>
							<div class="ts">
								<span class="eq-ic teal" aria-hidden="true"><Icon name="battery" size={22} /></span>
								<div>
									<p class="ts-l"><Term key="акумулятор">Акумулятор</Term></p>
									<p class="ts-v tnum"><b>{num(ses.battery_kwh, 1)}</b> <Term key="кВт·год">кВт·год</Term></p>
									<p class="ts-s">вистачить на {it ? duration(it.autonomy_hours) : '—'} без мережі</p>
								</div>
							</div>
							<div class="ts">
								<span class="eq-ic {ses.battery_within_connected ? 'ok' : 'bad'}" aria-hidden="true"><Icon name={ses.battery_within_connected ? 'check' : 'alert'} size={22} stroke={2.4} /></span>
								<div>
									<p class="ts-l">Перевірка підключення</p>
									<p class="ts-v"><b>{ses.battery_within_connected ? 'Усе гаразд' : 'Потрібна перевірка'}</b></p>
									<p class="ts-s">запущено {date(ses.launched)}</p>
								</div>
							</div>
						</div>
					{/if}

					<Disclosure summary={ses ? 'Усі технічні дані станції й будівлі' : 'Усі дані будівлі'} open={!ses}>
						{#if ses}
							<div class="tech-head">
								<h4>Обладнання станції</h4>
								{#if isDemoSes}<DemoPill align="left" />{:else}<span class="pill">реєстр міста (CSV)</span>{/if}
							</div>
							<dl class="kv tech-kv">
								<div><dt>Сонячні панелі</dt><dd>{num(ses.panels_count)} шт × {num(ses.panel_w)} Вт = {num(ses.total_kw, 1)} кВт</dd></div>
								<div><dt>Інвертор <small class="muted">(перетворює струм панелей на «розетковий»)</small></dt><dd>{ses.inverter_model}, {num(ses.inverter_kw, 1)} кВт</dd></div>
								<div><dt>Акумулятор</dt><dd>{num(ses.battery_kwh, 1)} кВт·год, потужність {num(ses.battery_kw, 1)} кВт</dd></div>
								<div><dt><Term key="приєднана потужність">Приєднана потужність</Term></dt><dd>{num(ses.connected_kw, 1)} кВт</dd></div>
								<div><dt>Дата запуску</dt><dd>{date(ses.launched)}</dd></div>
							</dl>
							{#if ses.battery_within_connected}
								<p class="check ok" role="status">
									<Icon name="check" size={20} stroke={2.4} />
									<span><b>Перевірка пройдена:</b> потужність акумулятора {num(ses.battery_kw, 1)} кВт не перевищує приєднаної потужності {num(ses.connected_kw, 1)} кВт.</span>
								</p>
							{:else}
								<p class="check bad" role="alert">
									<Icon name="alert" size={20} stroke={2.2} />
									<span><b>Увага:</b> потужність акумулятора {num(ses.battery_kw, 1)} кВт перевищує приєднану потужність {num(ses.connected_kw, 1)} кВт. Потрібно перевірити налаштування інвертора або договір приєднання.</span>
								</p>
							{/if}
						{/if}
						<div class="tech-head">
							<h4>Будівля</h4>
							<span class="real">дані UMUNI · реальні</span>
						</div>
						<dl class="kv tech-kv">
							<div><dt>Місто</dt><dd>{b.city || '—'}</dd></div>
							<div><dt>Адреса</dt><dd>{b.address}</dd></div>
							<div><dt>Тип закладу</dt><dd>{b.category_short}</dd></div>
							<div><dt>Площа</dt><dd>{b.heated_area ? `${num(b.heated_area)} м²` : '—'}</dd></div>
							<div><dt>Поверхів</dt><dd>{b.floors ?? '—'}</dd></div>
							<div><dt>Електроенергія за 2025 рік</dt><dd>{b.elec_kwh_2025 ? `${num(b.elec_kwh_2025)} кВт·год` : 'немає даних'}</dd></div>
						</dl>
						{#if s.notes.length}
							<ul class="notes">
								{#each s.notes as n, i (i)}
									<li><Icon name="info" size={16} /> {n}</li>
								{/each}
							</ul>
						{/if}
					</Disclosure>
				</div>
			</Reveal>
			{#if here}
				<Reveal delay={80}>
					<figure class="panel where">
						<figcaption><Icon name="pin" size={16} /> Де розташовано</figcaption>
						<div class="where-map">
							<CityMap points={[here]} selectedId={null} colorBy="category" compact height="240px" label="Розташування: {b.name}, {place}" />
						</div>
						<p class="muted small">{place}</p>
					</figure>
				</Reveal>
			{/if}
			</div>
		</section>
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
		display: grid;
		gap: 1.25rem;
		transition: opacity 0.2s;
	}
	.stale {
		opacity: 0.6;
	}

	/* ---------- Відповідь за 5 секунд ---------- */
	.hero {
		position: relative;
		overflow: hidden;
		display: grid;
		gap: 1.1rem;
		padding: 1.75rem;
		background:
			radial-gradient(700px 260px at 100% 0%, rgba(245, 165, 36, 0.14), transparent 70%),
			var(--surface);
	}
	.hero-top {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem 2rem;
	}
	.hero-main {
		flex: 1 1 30rem;
		min-width: 0;
	}
	.eyebrow {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem 0.75rem;
		margin: 0;
	}
	.crit {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		padding: 0.1rem 0.6rem;
		border-radius: 999px;
		background: #fbe9e8;
		color: #8f1414;
		border: 1px solid #f0b8b5;
		font-size: 0.75rem;
		letter-spacing: 0.02em;
	}
	h1 {
		font-size: clamp(1.6rem, 1.2rem + 1.2vw, 2.25rem);
		letter-spacing: -0.015em;
		line-height: 1.2;
		margin: 0.3rem 0 0.35rem;
	}
	.place {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		color: var(--text-2, #3d4857);
		font-size: 1.05rem;
		margin: 0;
	}
	.hero-side {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 0.75rem;
	}
	.idx {
		display: flex;
		align-items: center;
		gap: 0.6rem;
	}
	.idx-l {
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--muted);
	}
	.answer {
		margin: 0;
		font-size: clamp(1.15rem, 1rem + 0.5vw, 1.45rem);
		line-height: 1.45;
		color: var(--ink, #0f1b2d);
		max-width: 62ch;
	}
	.answer b {
		color: var(--navy, #0f2f52);
		white-space: nowrap;
	}
	.answer .demo-note {
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--sun-ink);
		white-space: nowrap;
	}
	.answer .bad-t {
		color: var(--deficit-ink);
		white-space: normal;
	}
	.cards {
		margin: 0.25rem 0 0;
	}
	.mini-bar {
		display: block;
		height: 8px;
		border-radius: 999px;
		background: #e8edf3;
		overflow: hidden;
	}
	.mini-bar i {
		display: block;
		height: 100%;
		width: var(--w);
		border-radius: inherit;
		background: linear-gradient(90deg, #f7b23b, var(--sun-strong));
	}
	.action {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 1rem 1.25rem;
		padding: 1.1rem 1.25rem;
		border-radius: var(--radius-lg);
		background: linear-gradient(135deg, #fffaf0, #fff1d2);
		border: 1px solid #f0d49b;
		border-left: 6px solid var(--sun-strong);
	}
	.act-ic {
		display: grid;
		place-items: center;
		width: 3rem;
		height: 3rem;
		flex: none;
		border-radius: 50%;
		background: var(--sun);
		color: #2b1a00;
	}
	.act-txt {
		flex: 1 1 22rem;
		min-width: 0;
	}
	.act-k {
		margin: 0;
		font-size: 0.8125rem;
		font-weight: 700;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--sun-ink);
	}
	.act-t {
		margin: 0.1rem 0 0.15rem;
		font-size: 1.25rem;
		font-weight: 700;
		line-height: 1.3;
		color: #2b1a00;
	}
	.act-s {
		margin: 0;
		color: #5a4310;
	}
	.act-btn {
		flex: none;
	}

	@media (prefers-reduced-motion: no-preference) {
		.rise {
			animation: rise 0.6s cubic-bezier(0.22, 1, 0.36, 1) var(--d, 0ms) backwards;
		}
		@keyframes rise {
			from {
				opacity: 0;
				transform: translateY(12px);
			}
		}
		.mini-bar i {
			animation: grow-x 1s cubic-bezier(0.22, 1, 0.36, 1) 0.45s backwards;
		}
		@keyframes grow-x {
			from {
				width: 0;
			}
		}
		.act-ic {
			animation: nudge 2.4s ease-in-out 1.2s 2;
		}
		@keyframes nudge {
			0%,
			100% {
				transform: none;
			}
			50% {
				transform: translateX(4px);
			}
		}
	}

	/* ---------- Зміст ---------- */
	.toc {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}
	.toc a {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.45rem 0.9rem;
		min-height: 40px;
		border-radius: 999px;
		background: var(--surface);
		border: 1px solid var(--card-line, #e2e7ee);
		color: var(--text-2, #36425a);
		font-weight: 600;
		font-size: 0.9375rem;
		text-decoration: none;
		box-shadow: var(--shadow);
		transition:
			transform var(--dur-fast, 150ms),
			border-color var(--dur-fast, 150ms),
			color var(--dur-fast, 150ms);
	}
	.toc a:hover {
		color: var(--accent);
		border-color: color-mix(in srgb, var(--accent) 40%, transparent);
		transform: translateY(-1px);
	}

	/* ---------- Розділи ---------- */
	.sec {
		display: grid;
		gap: 1rem;
		margin-top: 1.25rem;
		scroll-margin-top: 1rem;
	}
	.sec-h {
		display: flex;
		align-items: center;
		gap: 0.9rem;
	}
	.sec-h h2 {
		margin: 0;
		font-size: clamp(1.35rem, 1.15rem + 0.6vw, 1.7rem);
		letter-spacing: -0.01em;
	}
	.sec-h h2:focus {
		outline: none;
	}
	.sec-h h2:focus-visible {
		outline: 3px solid var(--focus);
		outline-offset: 4px;
		border-radius: 4px;
	}
	.sec-sub {
		margin: 0.15rem 0 0;
		color: var(--muted);
	}
	.sec-ic {
		display: grid;
		place-items: center;
		width: 2.75rem;
		height: 2.75rem;
		flex: none;
		border-radius: 14px;
	}
	.sec-ic.now {
		background: #e6eef8;
		color: var(--navy-3, #1f4f84);
	}
	.sec-ic.out {
		background: #dff3f0;
		color: #0f766e;
	}
	.sec-ic.sun {
		background: var(--sun-soft);
		color: var(--sun-ink);
	}
	.sec-ic.todo {
		background: var(--surplus-soft);
		color: var(--surplus-ink);
	}
	.sec-ic.tech {
		background: #eef2f6;
		color: #36425a;
	}
	.panel h3 {
		font-size: 1.2rem;
	}
	.sub {
		margin: 0.2rem 0 0;
		max-width: 70ch;
	}

	/* Деталі дня */
	.detail-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 17rem), 1fr));
		gap: 1.25rem 2rem;
		padding-top: 0.25rem;
	}
	.dg h4 {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin: 0 0 0.6rem;
		font-size: 1rem;
	}
	.dg.limits {
		display: grid;
		gap: 1.2rem;
		align-content: start;
	}
	.dg.limits h4 {
		margin: 0;
	}
	.kv {
		display: grid;
		gap: 0;
		margin: 0;
	}
	.kv div {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 1rem;
		padding: 0.5rem 0;
		border-bottom: 1px solid var(--line-soft, #e6ebf1);
	}
	.kv div:last-child {
		border-bottom: 0;
	}
	.kv dt {
		color: var(--text-2, #36425a);
	}
	.kv dd {
		margin: 0;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		text-align: right;
	}
	.kv dd small {
		font-weight: 500;
		color: var(--muted);
	}
	.src {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem;
		margin: 0.6rem 0 0;
	}
	.real {
		display: inline-flex;
		align-items: center;
		padding: 0.1rem 0.55rem;
		border-radius: 999px;
		background: #e6eef8;
		color: #1f4f84;
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.03em;
		white-space: nowrap;
	}

	/* Автономність */
	.auto {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.75rem 1.25rem;
		padding: 1rem 1.25rem;
		border-radius: var(--radius-lg);
		background: var(--surface);
		border: 1px solid var(--card-line, #e2e7ee);
		box-shadow: var(--shadow);
	}
	.au {
		display: flex;
		align-items: center;
		gap: 0.7rem;
		padding-right: 1.25rem;
		border-right: 1px solid var(--line-soft, #e6ebf1);
	}
	.au-ic {
		display: grid;
		place-items: center;
		width: 2.5rem;
		height: 2.5rem;
		border-radius: 50%;
		flex: none;
		font-size: 1.25rem;
	}
	.au-ic.night {
		background: #10243d;
		color: #ffd56b;
	}
	.au-ic.day {
		background: var(--sun-soft);
		color: var(--sun-ink);
	}
	.au-l {
		margin: 0;
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--muted);
	}
	.au-v {
		margin: 0;
		font-size: 1.5rem;
		font-weight: 700;
		color: var(--ink, #0f1b2d);
	}
	.au-n {
		flex: 1 1 18rem;
		margin: 0;
		color: var(--text-2, #36425a);
	}

	/* Технічні дані */
	.tech-grid {
		display: grid;
		gap: 1.25rem;
		align-items: start;
	}
	.tech-grid.with-map {
		grid-template-columns: minmax(0, 2fr) minmax(16rem, 1fr);
	}
	.where {
		margin: 0;
		padding: 1rem;
		display: grid;
		gap: 0.6rem;
	}
	.where figcaption {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-weight: 600;
	}
	.where-map {
		border-radius: 12px;
		overflow: hidden;
	}
	.where p {
		margin: 0;
	}
	@media (max-width: 900px) {
		.tech-grid.with-map {
			grid-template-columns: 1fr;
		}
	}
	.tech {
		display: grid;
		gap: 0.25rem;
	}
	.tech-sum {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 15rem), 1fr));
		gap: 1rem;
	}
	.ts {
		display: flex;
		gap: 0.8rem;
		align-items: flex-start;
	}
	.ts-l {
		margin: 0;
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--muted);
	}
	.ts-v {
		margin: 0.1rem 0 0;
		font-size: 1.3rem;
	}
	.ts-s {
		margin: 0.1rem 0 0;
		font-size: 0.875rem;
		color: var(--text-2, #36425a);
	}
	.eq-ic {
		display: grid;
		place-items: center;
		width: 2.6rem;
		height: 2.6rem;
		border-radius: 12px;
		flex: none;
	}
	.eq-ic.sun {
		background: var(--sun-soft);
		color: var(--sun-ink);
	}
	.eq-ic.teal {
		background: #dff3f0;
		color: #0f766e;
	}
	.eq-ic.ok {
		background: var(--surplus-soft);
		color: var(--surplus-ink);
	}
	.eq-ic.bad {
		background: var(--deficit-soft);
		color: var(--deficit-ink);
	}
	.tech-head {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem 0.75rem;
		margin: 0.75rem 0 0.25rem;
	}
	.tech-head:first-child {
		margin-top: 0;
	}
	.tech-head h4 {
		margin: 0;
		font-size: 1rem;
	}
	.tech-kv {
		max-width: 52rem;
	}
	.check {
		display: flex;
		gap: 0.6rem;
		align-items: flex-start;
		margin: 0.75rem 0 0;
		padding: 0.8rem 1rem;
		border-radius: 12px;
		border: 1px solid;
		line-height: 1.45;
		max-width: 52rem;
	}
	.check :global(.icon) {
		flex: none;
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
	.notes {
		list-style: none;
		margin: 1rem 0 0;
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
		flex: none;
		margin-top: 0.15rem;
	}

	@media (max-width: 1100px) {
		.hero-side {
			align-items: flex-start;
			flex: 1 1 100%;
			flex-direction: row;
			flex-wrap: wrap;
			justify-content: space-between;
		}
	}
	@media (max-width: 700px) {
		.hero {
			padding: 1.25rem;
		}
		.au {
			border-right: 0;
			padding-right: 0;
		}
		.act-btn {
			width: 100%;
			justify-content: center;
		}
		.kv div {
			flex-direction: column;
			gap: 0.1rem;
		}
		.kv dd {
			text-align: left;
		}
	}
</style>
