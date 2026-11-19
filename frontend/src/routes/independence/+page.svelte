<script lang="ts">
	// «Енергонезалежність громади» — розповідь зверху вниз, кожен блок — одна думка:
	// де ми зараз → найбільший ризик → що дасть програма СЕС → рейтинг закладів → як ми рахуємо.
	// Карти навмисно немає (безпека критичних об'єктів).
	import { page } from '$app/state';
	import { flip } from 'svelte/animate';
	import { errMessage } from '#lib/api.ts';
	import {
		independenceApi,
		duration,
		money,
		categoryRank,
		addKw,
		type IndependenceList,
		type IndependenceItem
	} from '#lib/api-independence.ts';
	import { num } from '#lib/format.ts';
	import { catLabel } from '#lib/categories.ts';
	import { viewFrom, withView } from '#lib/view.ts';
	import { fadeUp, stagger, DUR, isReduced } from '#lib/motion.ts';
	import Status from '#lib/Status.svelte';
	import DemoPill from '#lib/DemoPill.svelte';
	import Icon from '#lib/Icon.svelte';
	import IndexBadge from '#lib/IndexBadge.svelte';
	import Term from '#lib/Term.svelte';
	import CountUp from '#lib/CountUp.svelte';
	import Reveal from '#lib/Reveal.svelte';
	import Disclosure from '#lib/Disclosure.svelte';
	import StatCard from '#lib/StatCard.svelte';

	const view = $derived(viewFrom(page.url));
	const HEALTH = "Охорона здоров'я";
	// Телефон (≤640): у вузьких картках 2×2 позначку «ДЕМО» не дублюємо — вона вже є в шапці сторінки
	let phone = $state(false);
	$effect(() => {
		const mq = matchMedia('(max-width: 640px)');
		const on = () => (phone = mq.matches);
		on();
		mq.addEventListener('change', on);
		return () => mq.removeEventListener('change', on);
	});

	let data = $state<IndependenceList | null>(null);
	let error = $state<string | null>(null);
	let loading = $state(true);

	let seq = 0;
	async function load(v = view) {
		const my = ++seq;
		loading = true;
		error = null;
		try {
			const d = await independenceApi.list(v);
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

	const c = $derived(data?.community);
	const hasBat = (i: IndependenceItem) => (i.battery_kwh ?? 0) > 0;
	const obj = (id: number) => withView(`/object/${id}`, view);

	/** Один раз позначає, що блок з'явився на екрані (для анімацій «на появі») */
	function inview(node: HTMLElement, cb: () => void) {
		if (isReduced() || typeof IntersectionObserver === 'undefined') {
			cb();
			return;
		}
		const io = new IntersectionObserver(
			(es) => {
				if (es.some((e) => e.isIntersecting)) {
					cb();
					io.disconnect();
				}
			},
			{ threshold: 0.35 }
		);
		io.observe(node);
		return { destroy: () => io.disconnect() };
	}
	let heroSeen = $state(false);
	let critSeen = $state(false);
	let potSeen = $state(false);

	// ---------- 1. Де ми зараз ----------
	const batterySites = $derived(
		c?.battery_sites ?? (data?.items ?? []).filter(hasBat).length
	);

	// ---------- 2. Де бракує даних про резерв ----------
	// Критичні заклади без акумулятора: спершу ті, що споживають найбільше
	const noReserve = $derived(
		(data?.items ?? [])
			.filter((i) => i.critical && !hasBat(i))
			.sort((a, b) => (b.elec_kwh_year ?? 0) - (a.elec_kwh_year ?? 0))
	);
	const CRIT_TOP = 5;
	let showAllCrit = $state(false);
	function critAction(i: IndependenceItem): string {
		return 'Дані про резерв не внесено';
	}

	// ---------- 4. Рейтинг ----------
	let category = $state('');
	let onlyCritical = $state(false);
	let onlyNoSes = $state(false);
	let query = $state('');
	let sort = $state<'weak' | 'strong' | 'name'>('strong');
	let limit = $state(20);
	let detailed = $state(false);

	const norm = (s: string) => s.toLocaleLowerCase('uk').replace(/[’'"«»]/g, '');
	const cats = $derived(
		[...(data?.categories ?? [])].sort(
			(a, b) => categoryRank(a.category_short) - categoryRank(b.category_short) || b.sites - a.sites
		)
	);
	const filtered = $derived.by(() => {
		const q = norm(query.trim());
		const l = (data?.items ?? []).filter(
			(i) =>
				(!category || i.category_short === category) &&
				(!onlyCritical || i.critical) &&
				(!onlyNoSes || !i.has_ses) &&
				(!q || norm(`${i.name} ${i.address}`).includes(q))
		);
		const byName = (a: IndependenceItem, b: IndependenceItem) => a.name.localeCompare(b.name, 'uk');
		if (sort === 'name') return l.sort(byName);
		if (sort === 'strong') return l.sort((a, b) => b.index - a.index || byName(a, b));
		// найменш захищені спершу: критичні, далі школи/садки, далі більші споживачі
		return l.sort(
			(a, b) =>
				a.index - b.index ||
				categoryRank(a.category_short) - categoryRank(b.category_short) ||
				(b.elec_kwh_year ?? 0) - (a.elec_kwh_year ?? 0)
		);
	});
	$effect(() => {
		void category;
		void onlyCritical;
		void onlyNoSes;
		void query;
		void sort;
		limit = 20;
	});
	const filtersOn = $derived(!!(category || onlyCritical || onlyNoSes || query));
	// Телефон: сортування й перемикачі — у нижній шторці «Фільтри»
	let sheetEl = $state<HTMLDialogElement | null>(null);
	const sheetCount = $derived((onlyCritical ? 1 : 0) + (onlyNoSes ? 1 : 0) + (sort !== 'strong' ? 1 : 0));
	const SORTS: { v: 'strong' | 'weak' | 'name'; t: string }[] = [
		{ v: 'strong', t: 'Спершу найкращі' },
		{ v: 'weak', t: 'Спершу найменш захищені' },
		{ v: 'name', t: 'За назвою' }
	];
	function pickCat(k: string) {
		category = category === k ? '' : k;
	}
	function reset() {
		category = '';
		onlyCritical = false;
		onlyNoSes = false;
		query = '';
	}

	type Tone = 'ok' | 'mid' | 'bad' | 'none';
	/** Один стан закладу словами */
	function status(i: IndependenceItem): { text: string; tone: Tone } {
		const bat = hasBat(i);
		if (bat && i.has_ses) return { text: `Сонце і резерв на ${duration(i.autonomy_hours)}`, tone: 'ok' };
		if (bat) return { text: `Резерв на ${duration(i.autonomy_hours)}, сонця не зафіксовано`, tone: 'mid' };
		if (i.has_ses) return { text: 'Є сонце, резерву не зафіксовано', tone: 'mid' };
		if (i.data_ok === false) return { text: 'Немає даних про споживання', tone: 'none' };
		return { text: 'Сонця й резерву не зафіксовано', tone: 'bad' };
	}
	/** Що зробити (для детальної таблиці) */
	function todo(i: IndependenceItem): string {
		if (i.data_ok === false) return hasBat(i) ? 'додати дані в UMUNI' : 'акумулятор; додати дані в UMUNI';
		const p: string[] = [];
		if (!hasBat(i)) p.push('акумулятор');
		if (addKw(i) >= 1) p.push(`${i.has_ses ? 'ще ' : ''}панелі ${num(addKw(i), 0)} кВт`);
		return p.length ? p.join(' + ') : 'усе є — підтримувати';
	}
	const catMax = $derived(Math.max(5, ...cats.map((x) => x.self_sufficiency_pct ?? 0)));
	const critWord = (n: number) => {
		const a = n % 100;
		const b = n % 10;
		if (a > 10 && a < 20) return 'закладів';
		if (b === 1) return 'заклад';
		if (b >= 2 && b <= 4) return 'заклади';
		return 'закладів';
	};
</script>

<svelte:head><title>Енергонезалежність громади · City Insight Map · Енергія</title></svelte:head>

<header class="head">
	<div>
		<h1><Term key="енергонезалежність" plain>Енергонезалежність</Term> громади</h1>
		<p class="lead">Скільки електрики будівлі громади отримують від власного сонця і що буде, якщо зникне світло.</p>
	</div>
	<span class="demo-quiet">
		<DemoPill text="Будівлі й річне споживання електроенергії — реальні дані UMUNI 2025. Наявні сонячні панелі й акумулятори змодельовані, доки місто не надасть перелік." />
	</span>
</header>

<Status loading={loading && !data} {error} retry={() => load()} />

{#if data && c}
	<div class="story" class:stale={loading}>
		<!-- 1. Де ми зараз -->
		<section class="block now" aria-labelledby="now-h">
			<h2 id="now-h" class="kicker"><span class="step" aria-hidden="true">1</span>Де ми зараз</h2>
			<div class="now-grid">
				<div class="now-main" use:inview={() => (heroSeen = true)}>
					<p class="nm-l"><Icon name="sun" size={22} /> Власне сонце дає</p>
					<p class="nm-v"><span class="big-num"><CountUp value={c.self_sufficiency_pct} decimals={1} duration={600} /></span><span class="u">%</span></p>
					<p class="nm-s">
						усієї електрики, яку {num(c.sites)} будівель громади споживають за рік. Решту
						<b class="tnum">{num(100 - c.self_sufficiency_pct, 0)} %</b> купуємо з мережі.
					</p>
					<div class="mix" class:go={heroSeen} role="img" aria-label="Сонце {num(c.self_sufficiency_pct, 1)} %, мережа {num(100 - c.self_sufficiency_pct, 1)} %">
						<span class="mix-sun" style:--w="{c.self_sufficiency_pct}%"></span>
						<span class="mix-grid"></span>
					</div>
					<p class="mix-legend" aria-hidden="true">
						<span><i class="dot sun"></i>сонце на дахах</span>
						<span><i class="dot grid"></i>мережа</span>
					</p>
				</div>
				<div class="stats">
					<Reveal delay={80}>
						<StatCard label={phone ? 'З панелями' : 'Будівлі з панелями'} value={c.ses_sites} unit="з {num(c.sites)}" icon="panel" demo={!phone}
							hint="Мають сонячну станцію на даху." />
					</Reveal>
					<Reveal delay={160}>
						<StatCard label={phone ? 'З резервом' : 'Будівлі з акумулятором'} value={batterySites} unit="з {num(c.sites)}" icon="battery" demo={!phone}
							hint="Мають резерв на випадок відключення світла." />
					</Reveal>
					<Reveal delay={240}>
						<StatCard label="Типовий резерв" value={c.autonomy_hours_median} format={duration} icon="clock" demo={!phone}
							hint="Стільки заклад з акумулятором працює без світла." />
					</Reveal>
				</div>
			</div>
		</section>

		<!-- 2. Де бракує даних про резерв (нейтрально: це прогалина в даних, а не встановлений факт) -->
		<Reveal>
			<section class="block risk" aria-labelledby="risk-h">
				<h2 id="risk-h" class="kicker"><span class="step" aria-hidden="true">2</span>Де бракує даних про резерв</h2>
				{#if noReserve.length}
					<p class="statement">
						Дані про резерв внесено лише для <b class="tnum">{num(c.critical_sites_total - noReserve.length)} з {num(c.critical_sites_total)}</b> медзакладів <span class="demo-tag">ДЕМО</span>
					</p>
					<p class="muted sub">Це прогалина в даних, а не висновок про стан закладів. Після підключення реального реєстру станцій тут будуть справжні дані. Нижче — медзаклади без даних, що споживають найбільше.</p>
					<ul class="crit-list" class:seen={critSeen} use:inview={() => (critSeen = true)}>
						{#each showAllCrit ? noReserve : noReserve.slice(0, CRIT_TOP) as i, n (i.id)}
							<li style:--i={n >= CRIT_TOP ? Math.min(n - CRIT_TOP, 6) : n}>
								<a href={obj(i.id)}>
									<span class="cl-ic" aria-hidden="true"><Icon name="info" size={18} /></span>
									<span class="cl-txt">
										<span class="cl-name">{i.name}</span>
										<span class="cl-do">{critAction(i)}</span>
									</span>
									<Icon name="arrow-right" size={18} />
								</a>
							</li>
						{/each}
					</ul>
					{#if noReserve.length > CRIT_TOP}
						<button type="button" class="btn btn-secondary more-btn" onclick={() => (showAllCrit = !showAllCrit)} aria-expanded={showAllCrit}>
							{showAllCrit ? 'Згорнути список' : `Показати всіх (${noReserve.length})`}
						</button>
					{/if}
				{:else}
					<p class="ok-msg"><Icon name="check" size={20} /> За даними системи, резерв зафіксовано в усіх медичних закладах.</p>
				{/if}
			</section>
		</Reveal>

		<!-- 3. Що дасть програма СЕС -->
		<Reveal>
			<section class="block pot" aria-labelledby="pot-h">
				<h2 id="pot-h" class="kicker"><span class="step" aria-hidden="true">3</span>Що дасть програма <Term key="СЕС" plain>СЕС</Term></h2>
				<p class="statement">
					Частка власного сонця зросте з
					<span class="from tnum">{num(c.self_sufficiency_pct, 1)} %</span> до
					<span class="to tnum">{num(c.potential_self_sufficiency_pct, 1)} %</span>
				</p>
				<div class="pot-bars" use:inview={() => (potSeen = true)} class:go={potSeen} role="img"
					aria-label="Зараз {num(c.self_sufficiency_pct, 1)} %, після програми {num(c.potential_self_sufficiency_pct, 1)} % електрики від власного сонця">
					<div class="pb-row">
						<span class="pb-l">Зараз</span>
						<div class="pb"><span class="seg-now" style:--w="{c.self_sufficiency_pct}%"></span></div>
						<b class="pb-v tnum">{num(c.self_sufficiency_pct, 1)} %</b>
					</div>
					<div class="pb-row">
						<span class="pb-l">Після програми</span>
						<div class="pb">
							<span class="seg-now" style:--w="{c.self_sufficiency_pct}%"></span><span class="seg-add" style:--w="{Math.max(0, c.potential_self_sufficiency_pct - c.self_sufficiency_pct)}%"></span>
						</div>
						<b class="pb-v tnum to"><CountUp value={potSeen ? c.potential_self_sufficiency_pct : c.self_sufficiency_pct} decimals={1} duration={600} suffix=" %" /></b>
					</div>
					<div class="pb-scale" aria-hidden="true"><span></span><span class="ticks"><span>0</span><span>50 %</span><span>100 %</span></span><span></span></div>
				</div>
				<div class="pot-foot">
					<p class="pot-facts">
						Для цього — ще <b class="tnum">{num(c.potential_kw, 0)} кВт</b> панелей{#if c.potential_sites}{' '}на <b class="tnum">{num(c.potential_sites)}</b> будівлях{/if},
						кожна станція під власне споживання будівлі. Орієнтовна вартість — <b class="tnum">{money(c.potential_cost_uah)}</b>.
					</p>
					<a class="btn" href={withView('/solar', view)} data-sveltekit-reset="false">Де ставити нові СЕС <Icon name="arrow-right" size={18} /></a>
				</div>
			</section>
		</Reveal>

		<!-- 4. Рейтинг -->
		<Reveal>
			<section class="block rank-block" aria-labelledby="rank-h">
				<h2 id="rank-h" class="kicker"><span class="step" aria-hidden="true">4</span>Рейтинг закладів</h2>
				<p class="index-explain">
					<b>Індекс енергостійкості</b> — бал від 0 до 100: половина балів — за частку власного сонця,
					половина — за години роботи на акумуляторі без світла. 0 — немає ні панелей, ні акумулятора.
				</p>

				<!-- Телефон: пошук + ряд чипів типів + шторка «Фільтри» -->
				<div class="pf only-phone" role="search">
					<div class="pf-top">
						<div class="search">
							<label for="iq-m" class="visually-hidden">Пошук за назвою або адресою</label>
							<Icon name="search" size={18} />
							<input id="iq-m" type="search" bind:value={query} placeholder="Назва або адреса" autocomplete="off" enterkeyhint="search" />
						</div>
						<button type="button" class="pf-btn" aria-haspopup="dialog" onclick={() => sheetEl?.showModal()}>
							<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12" /><circle cx="16" cy="6" r="2" /><circle cx="10" cy="12" r="2" /><circle cx="18" cy="18" r="2" /></svg>
							Фільтри{#if sheetCount}<span class="pf-n">{sheetCount}</span>{/if}
						</button>
					</div>
					<div class="chip-row pf-chips" role="group" aria-label="Тип закладу">
						<button type="button" class="chip" aria-pressed={!category} onclick={() => (category = '')}>Усі типи</button>
						{#each cats as k (k.category_short)}
							<button type="button" class="chip" aria-pressed={category === k.category_short} onclick={() => pickCat(k.category_short)}>
								{catLabel(k.category_short)}<span class="chip-n tnum">{k.sites}</span>
							</button>
						{/each}
					</div>
				</div>

				<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
				<dialog class="sheet" bind:this={sheetEl} aria-labelledby="sheet-h" onclick={(e) => { if (e.target === sheetEl) sheetEl?.close(); }}>
					<div class="sheet-in">
						<span class="grab" aria-hidden="true"></span>
						<div class="sheet-head">
							<h3 id="sheet-h">Фільтри</h3>
							<button type="button" class="sheet-x" aria-label="Закрити" onclick={() => sheetEl?.close()}>
								<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18" /></svg>
							</button>
						</div>
						<p class="sheet-l" id="sort-l">Порядок</p>
						<div class="opts" role="radiogroup" aria-labelledby="sort-l">
							{#each SORTS as o (o.v)}
								<button type="button" role="radio" aria-checked={sort === o.v} class="opt" onclick={() => (sort = o.v)}>
									<span class="radio" aria-hidden="true"></span>{o.t}
								</button>
							{/each}
						</div>
						<p class="sheet-l">Показати лише</p>
						<div class="opts">
							<button type="button" role="switch" aria-checked={onlyCritical} class="opt" onclick={() => (onlyCritical = !onlyCritical)}>
								Медичні заклади<span class="sw" aria-hidden="true"><i></i></span>
							</button>
							<button type="button" role="switch" aria-checked={onlyNoSes} class="opt" onclick={() => (onlyNoSes = !onlyNoSes)}>
								Без сонячних панелей<span class="sw" aria-hidden="true"><i></i></span>
							</button>
						</div>
						<div class="sheet-foot">
							<button type="button" class="btn btn-secondary" onclick={() => { onlyCritical = false; onlyNoSes = false; sort = 'strong'; }}>Скинути</button>
							<button type="button" class="btn" onclick={() => sheetEl?.close()}>Показати {num(filtered.length)}</button>
						</div>
					</div>
				</dialog>

				<div class="filters hide-phone" role="search">
					<div class="search">
						<label for="iq" class="visually-hidden">Пошук за назвою або адресою</label>
						<Icon name="search" size={18} />
						<input id="iq" type="search" bind:value={query} placeholder="Назва або адреса" autocomplete="off" />
					</div>
					<label class="fsel">
						<span class="visually-hidden">Тип закладу</span>
						<select bind:value={category}>
							<option value="">Усі типи</option>
							{#each cats as k (k.category_short)}
								<option value={k.category_short}>{catLabel(k.category_short)} ({k.sites})</option>
							{/each}
						</select>
					</label>
					<button type="button" class="tgl" aria-pressed={onlyCritical} onclick={() => (onlyCritical = !onlyCritical)}>
						{#if onlyCritical}<Icon name="check" size={16} />{/if}Лише медичні
					</button>
					<button type="button" class="tgl" aria-pressed={onlyNoSes} onclick={() => (onlyNoSes = !onlyNoSes)}>
						{#if onlyNoSes}<Icon name="check" size={16} />{/if}Лише без панелей
					</button>
					<label class="fsel sort">
						<span class="visually-hidden">Сортування</span>
						<select bind:value={sort}>
							<option value="strong">Спершу найкращі</option>
							<option value="weak">Спершу найменш захищені</option>
							<option value="name">За назвою</option>
						</select>
					</label>
				</div>

				<div class="rank-bar">
					<p class="found" role="status" aria-live="polite">
						Знайдено <b class="tnum">{num(filtered.length)}</b>
						{#if filtersOn}· <button type="button" class="linkish" onclick={reset}>скинути фільтри</button>{/if}
					</p>
					<button type="button" class="tgl tgl-detail hide-phone" aria-pressed={detailed} onclick={() => (detailed = !detailed)}>
						<span class="sw" aria-hidden="true"><i></i></span> Детальна таблиця
					</button>
				</div>

				{#if filtered.length}
					<ul class="rank-list only-phone">
						{#each filtered.slice(0, limit) as i (i.id)}
							{@const s = status(i)}
							<li class:crit={i.critical}>
								<a href={obj(i.id)}>
									<span class="rl-name">{i.name}</span>
									<span class="rl-badge"><IndexBadge index={i.index} cls={i.index_class} size="sm" /></span>
									<span class="rl-sub">{catLabel(i.category_short)}{#if i.critical && i.category_short !== HEALTH}{' '}· <b class="crit-t">медичний</b>{/if}</span>
									<span class="rl-st st {s.tone}"><i aria-hidden="true"></i>{s.text}</span>
								</a>
							</li>
						{/each}
					</ul>
					<div class="table-wrap hide-phone">
						<table class="rank" class:detailed>
							<thead>
								<tr>
									<th scope="col">Заклад</th>
									<th scope="col">Індекс енергостійкості</th>
									<th scope="col">Стан</th>
									{#if detailed}
										<th scope="col" class="num">Сонце покриває</th>
										<th scope="col" class="num">Без світла протримається</th>
										<th scope="col">Що зробити</th>
									{/if}
								</tr>
							</thead>
							<tbody>
								{#each filtered.slice(0, limit) as i, n (i.id)}
									{@const s = status(i)}
									<tr class:crit={i.critical} animate:flip={{ duration: isReduced() ? 0 : DUR.slow }} in:fadeUp={{ delay: stagger(n, 25, 250), y: 6 }}>
										<td class="name">
											<a href={obj(i.id)}>{i.name}</a>
											<span class="sub2">{catLabel(i.category_short)}{#if i.critical && i.category_short !== HEALTH}{' '}· <b class="crit-t">медичний</b>{/if}</span>
										</td>
										<td><IndexBadge index={i.index} cls={i.index_class} size="sm" /></td>
										<td><span class="st {s.tone}"><i aria-hidden="true"></i>{s.text}</span></td>
										{#if detailed}
											<td class="num">{i.has_ses ? `${num(i.self_sufficiency_pct, 0)} %` : '—'}</td>
											<td class="num">{hasBat(i) ? duration(i.autonomy_hours) : 'не зафіксовано'}</td>
											<td class="todo">{todo(i)}</td>
										{/if}
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
					{#if filtered.length > limit}
						<p class="more">
							<button type="button" class="btn btn-secondary" onclick={() => (limit += 40)}>
								{filtered.length - limit <= 40 ? `Показати решту ${num(filtered.length - limit)}` : `Показати ще 40 з ${num(filtered.length - limit)}`}
							</button>
						</p>
					{/if}
				{:else}
					<div class="empty">
						<p><strong>Немає закладів за цими умовами.</strong> Спробуйте зняти один із фільтрів.</p>
						<button type="button" class="btn btn-secondary" onclick={reset}>Скинути фільтри</button>
					</div>
				{/if}

				<Disclosure summary="Підсумок за типами закладів" hint="{cats.length} типів" class="cat-disc">
					<ul class="cat-list only-phone">
						{#each cats as k (k.category_short)}
							<li>
								<button type="button" onclick={() => { category = k.category_short; document.getElementById('rank-h')?.scrollIntoView({ behavior: isReduced() ? 'auto' : 'smooth' }); }}>
									<span class="ct-name">{catLabel(k.category_short)}</span>
									<b class="ct-pct tnum">{num(k.self_sufficiency_pct, 1)} %</b>
									<span class="cbar ct-bar"><span style:width="{((k.self_sufficiency_pct ?? 0) / catMax) * 100}%"></span></span>
									<span class="ct-sub">{num(k.sites)} будівель · з панелями {num(k.with_ses)} · резерв {k.autonomy_hours_median ? duration(k.autonomy_hours_median) : 'немає'}</span>
								</button>
							</li>
						{/each}
					</ul>
					<div class="table-wrap hide-phone">
						<table>
							<thead>
								<tr>
									<th scope="col">Тип</th>
									<th scope="col" class="num">Будівель</th>
									<th scope="col" class="num">З панелями</th>
									<th scope="col">Сонце покриває</th>
									<th scope="col" class="num">Типовий резерв</th>
								</tr>
							</thead>
							<tbody>
								{#each cats as k (k.category_short)}
									<tr>
										<th scope="row">
											<button type="button" class="linkish" onclick={() => { category = k.category_short; document.getElementById('rank-h')?.scrollIntoView({ behavior: isReduced() ? 'auto' : 'smooth' }); }}>
												{catLabel(k.category_short)}
											</button>
										</th>
										<td class="num">{num(k.sites)}</td>
										<td class="num">{num(k.with_ses)}</td>
										<td>
											<span class="cbar"><span style:width="{((k.self_sufficiency_pct ?? 0) / catMax) * 100}%"></span></span>
											<b class="tnum">{num(k.self_sufficiency_pct, 1)} %</b>
										</td>
										<td class="num">{k.autonomy_hours_median ? duration(k.autonomy_hours_median) : 'немає акумуляторів'}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</Disclosure>
			</section>
		</Reveal>

		<!-- 5. Як ми рахуємо -->
		<Reveal>
			<section class="block how" aria-labelledby="how-h">
				<h2 id="how-h" class="kicker"><span class="step" aria-hidden="true">5</span>Як ми рахуємо</h2>
				<Disclosure summary="Звідки цифри і як рахується індекс енергостійкості">
					<ul class="how-list">
						<li><b>Частка власного сонця</b> — скільки з річного споживання електрики будівлі покривають її сонячні панелі (виробіток 1 кВт панелей — за даними <Term key="PVGIS" plain>PVGIS</Term> для Полтави).</li>
						<li><b>Резерв</b> — скільки годин <Term key="акумулятор" plain>акумулятор</Term> тримає будівлю без світла і без сонця при звичайному навантаженні.</li>
						<li><b>Індекс енергостійкості</b> — 50 балів за сонце (максимум, якщо сонце покриває 40 % і більше) + 50 балів за резерв (максимум від 8 годин).</li>
						<li><b>Програма СЕС</b> — панелі, підібрані під власне споживання кожної будівлі, без надлишку, який не можна продати.</li>
					</ul>
					{#if data.formula?.text}<p class="formula small">{data.formula.text}</p>{/if}
					{#if data.notes?.length}
						<ul class="notes small muted">
							{#each data.notes as nt, k (k)}<li>{nt}</li>{/each}
						</ul>
					{/if}
				</Disclosure>
				<p class="security muted small">
					<Icon name="lock" size={16} /> Карту навмисно не показуємо: де саме є резервне живлення — чутлива інформація.
				</p>
			</section>
		</Reveal>
	</div>
{/if}

<style>
	.head {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: flex-start;
		gap: 0.5rem 2rem;
		margin-bottom: 1.5rem;
	}
	h1 {
		font-size: 2.3rem;
		letter-spacing: -0.02em;
		margin-bottom: 0.3rem;
	}
	.lead {
		margin: 0;
		font-size: 1.1rem;
		color: #3d4857;
		max-width: 46rem;
	}
	.demo-quiet {
		opacity: 0.8;
		transition: opacity 0.2s;
	}
	.demo-quiet:hover,
	.demo-quiet:focus-within {
		opacity: 1;
	}
	.stale {
		opacity: 0.55;
		transition: opacity 0.2s;
	}
	.story {
		display: grid;
		/* minmax(0,…): інакше колонка росте до min-content найширшого блоку (рейтинг) і сторінка їде вбік */
		grid-template-columns: minmax(0, 1fr);
		gap: 1.5rem;
	}
	.block {
		background: var(--surface);
		border: 1px solid #e3e8ef;
		border-radius: var(--radius-lg);
		box-shadow: var(--shadow-md);
		padding: 1.75rem 2rem;
	}
	.kicker {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		margin: 0 0 1rem;
		font-size: 0.95rem;
		font-weight: 700;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--muted);
	}
	.step {
		display: grid;
		place-items: center;
		width: 1.7rem;
		height: 1.7rem;
		border-radius: 50%;
		background: var(--navy);
		color: #fff;
		font-size: 0.85rem;
		letter-spacing: 0;
	}
	.statement {
		font-size: 1.6rem;
		font-weight: 700;
		line-height: 1.3;
		letter-spacing: -0.01em;
		margin: 0 0 0.35rem;
		max-width: 52rem;
	}
	.sub {
		margin: 0 0 1.1rem;
		font-size: 1.02rem;
	}

	/* 1. Де ми зараз */
	.now {
		background:
			radial-gradient(700px 300px at 0% 0%, rgba(245, 165, 36, 0.13), transparent 70%),
			var(--surface);
	}
	.now-grid {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: 1.5rem;
		align-items: start;
	}
	.nm-l {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		margin: 0;
		font-weight: 600;
		font-size: 1.15rem;
		color: var(--sun-ink);
	}
	.nm-v {
		margin: 0.1rem 0 0.4rem;
		color: var(--navy);
	}
	.nm-v .big-num {
		font-size: 5.2rem;
	}
	.nm-v .u {
		font-size: 2.4rem;
		font-weight: 700;
		margin-left: 0.1em;
	}
	.nm-s {
		margin: 0 0 1.1rem;
		font-size: 1.15rem;
		max-width: 34rem;
	}
	.mix {
		display: flex;
		height: 18px;
		border-radius: 999px;
		overflow: hidden;
		background: #e2e8f0;
		max-width: 34rem;
	}
	.mix-sun {
		display: block;
		width: var(--w);
		min-width: 6px;
		background: var(--sun-strong);
		border-radius: 999px 0 0 999px;
	}
	.mix-grid {
		flex: 1;
	}
	.mix-legend {
		display: flex;
		gap: 1.25rem;
		margin: 0.5rem 0 0;
		font-size: 0.875rem;
		color: var(--muted);
	}
	.mix-legend span {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
	}
	.dot {
		width: 0.7rem;
		height: 0.7rem;
		border-radius: 50%;
	}
	.dot.sun {
		background: var(--sun-strong);
	}
	.dot.grid {
		background: #cbd5e1;
	}
	.stats {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 15rem), 1fr));
		gap: 0.9rem;
	}

	/* 2. Ризик */
	.risk {
		border-left: 6px solid var(--line-strong);
	}
	.demo-tag {
		display: inline-block;
		vertical-align: middle;
		padding: 0.05rem 0.5rem;
		border-radius: 999px;
		border: 1px dashed #d08a1c;
		background: var(--sun-soft);
		color: var(--sun-ink);
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.06em;
	}
	.risk .statement b {
		color: var(--navy);
	}
	.crit-list {
		list-style: none;
		margin: 0 0 1rem;
		padding: 0;
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 24rem), 1fr));
		gap: 0.6rem 0.9rem;
	}
	.crit-list a {
		height: 100%;
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.8rem 1rem;
		border-radius: 12px;
		border: 1px solid var(--card-line);
		background: var(--surface-2);
		color: var(--text);
		text-decoration: none;
		transition:
			border-color 0.15s,
			box-shadow 0.15s,
			transform 0.15s;
	}
	.crit-list a:hover {
		border-color: var(--line-strong);
		box-shadow: var(--shadow-md);
	}
	.crit-list a > :global(.icon:last-child) {
		color: var(--accent);
		flex: none;
	}
	.cl-ic {
		flex: none;
		display: grid;
		place-items: center;
		width: 2.1rem;
		height: 2.1rem;
		border-radius: 50%;
		background: var(--bg-2);
		color: var(--muted);
	}
	.cl-txt {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
	}
	.cl-name {
		font-weight: 700;
		line-height: 1.3;
	}
	.cl-do {
		font-size: 0.9rem;
		color: var(--muted);
		font-weight: 500;
	}
	.ok-msg {
		display: flex;
		gap: 0.5rem;
		align-items: center;
		color: var(--surplus-ink);
		font-weight: 600;
		margin: 0;
	}
	@media (prefers-reduced-motion: no-preference) {
		.crit-list a:hover {
			transform: translateY(-2px);
		}
		.crit-list:not(.seen) li {
			opacity: 0;
		}
		.crit-list.seen li {
			animation: rise 0.4s cubic-bezier(0.22, 1, 0.36, 1) both;
			animation-delay: calc(var(--i, 0) * 40ms);
		}
		@keyframes rise {
			from {
				opacity: 0;
				transform: translateY(10px);
			}
		}
	}

	/* 3. Програма СЕС */
	.pot {
		border-left: 6px solid var(--surplus);
	}
	.from {
		color: var(--muted);
		white-space: nowrap;
	}
	.to {
		color: var(--surplus-ink);
		white-space: nowrap;
	}
	.pot-bars {
		display: grid;
		gap: 0.7rem;
		margin: 1.1rem 0 1.25rem;
		max-width: 56rem;
	}
	.pb-row,
	.pb-scale {
		display: grid;
		grid-template-columns: 9.5rem minmax(0, 1fr) 5rem;
		align-items: center;
		gap: 0.9rem;
	}
	.pb-l {
		font-weight: 600;
		color: #3d4857;
	}
	.pb-v {
		font-size: 1.2rem;
		text-align: right;
	}
	.pb {
		display: flex;
		height: 22px;
		border-radius: 999px;
		background: #e8edf3;
		overflow: hidden;
	}
	.pb span {
		display: block;
		height: 100%;
		width: var(--w);
	}
	.seg-now {
		background: var(--sun-strong);
		min-width: 6px;
	}
	.seg-add {
		background: var(--surplus);
	}
	.pb-scale {
		font-size: 0.8rem;
		color: var(--muted);
		margin-top: -0.35rem;
	}
	.ticks {
		display: flex;
		justify-content: space-between;
	}
	@media (prefers-reduced-motion: no-preference) {
		.pot-bars .seg-now,
		.pot-bars .seg-add,
		.mix-sun {
			transition: width 0.6s cubic-bezier(0.22, 1, 0.36, 1);
		}
		.pot-bars .seg-add {
			transition-delay: 0.15s;
		}
		.pot-bars:not(.go) .seg-add,
		.pot-bars:not(.go) .seg-now,
		.mix:not(.go) .mix-sun {
			width: 0;
			min-width: 0;
		}
	}
	.pot-foot {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 1rem 2rem;
	}
	.pot-facts {
		margin: 0;
		max-width: 44rem;
		font-size: 1.02rem;
	}

	/* 4. Рейтинг */
	.index-explain {
		margin: 0 0 1.25rem;
		padding: 0.8rem 1rem;
		border-radius: 12px;
		background: #f3f6fa;
		max-width: 60rem;
	}
	.filters {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.6rem;
		margin-bottom: 0.9rem;
	}
	.search {
		flex: 1 1 15rem;
		position: relative;
		display: flex;
		align-items: center;
	}
	.search :global(.icon) {
		position: absolute;
		left: 0.8rem;
		color: var(--muted);
		pointer-events: none;
	}
	.search input {
		width: 100%;
		padding-left: 2.5rem;
		min-height: 44px;
	}
	.fsel select {
		min-height: 44px;
	}
	.sort {
		margin-left: auto;
	}
	.tgl {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		min-height: 44px;
		padding: 0.35rem 1rem;
		border-radius: 999px;
		border: 1px solid #cfd7e1;
		background: #fff;
		font: inherit;
		font-size: 0.95rem;
		font-weight: 600;
		color: #2b3645;
		cursor: pointer;
		transition:
			background 0.15s,
			border-color 0.15s,
			color 0.15s;
	}
	.tgl:hover {
		border-color: var(--navy-3);
	}
	.tgl[aria-pressed='true']:not(.tgl-detail) {
		background: var(--navy);
		border-color: var(--navy);
		color: #fff;
	}
	.rank-bar {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem 1rem;
		margin-bottom: 0.6rem;
	}
	.found {
		color: var(--muted);
		margin: 0;
	}
	.tgl-detail {
		border-color: transparent;
		background: transparent;
		padding-inline: 0.5rem;
		gap: 0.55rem;
	}
	.sw {
		position: relative;
		width: 2.4rem;
		height: 1.4rem;
		border-radius: 999px;
		background: #cbd5e1;
		transition: background 0.2s;
	}
	.sw i {
		position: absolute;
		top: 0.2rem;
		left: 0.2rem;
		width: 1rem;
		height: 1rem;
		border-radius: 50%;
		background: #fff;
		box-shadow: 0 1px 2px rgba(0, 0, 0, 0.25);
		transition: transform 0.2s cubic-bezier(0.22, 1, 0.36, 1);
	}
	.tgl-detail[aria-pressed='true'] .sw {
		background: var(--navy-3);
	}
	.tgl-detail[aria-pressed='true'] .sw i {
		transform: translateX(1rem);
	}
	.rank td {
		vertical-align: middle;
	}
	.rank tr.crit td:first-child {
		box-shadow: inset 4px 0 0 var(--deficit);
	}
	.rank .name a {
		display: inline-block;
		padding-block: 0.3rem 0.1rem;
		font-weight: 600;
	}
	.rank:not(.detailed) .name {
		width: 100%;
	}
	.rank.detailed .name {
		min-width: 18rem;
	}
	.sub2 {
		display: block;
		font-size: 0.8rem;
		color: var(--muted);
	}
	.crit-t {
		color: var(--deficit-ink);
	}
	.st {
		white-space: nowrap;
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		font-size: 0.925rem;
		font-weight: 500;
	}
	.st i {
		flex: none;
		width: 0.6rem;
		height: 0.6rem;
		border-radius: 50%;
		background: #94a3b8;
	}
	.st.ok i {
		background: var(--surplus);
	}
	.st.mid i {
		background: var(--sun-strong);
	}
	.st.bad i {
		background: var(--deficit);
	}
	.st.none {
		color: var(--muted);
	}
	.todo {
		font-size: 0.9rem;
		min-width: 12rem;
	}
	.rank.detailed .st {
		white-space: normal;
	}
	.more {
		text-align: center;
		margin: 1rem 0 0;
	}
	.empty p {
		margin-bottom: 0.6rem;
	}
	.rank-block :global(.cat-disc) {
		margin-top: 1.25rem;
	}
	.cbar {
		display: inline-block;
		width: 7rem;
		height: 10px;
		border-radius: 999px;
		background: #e8edf3;
		margin-right: 0.5rem;
		vertical-align: middle;
		overflow: hidden;
	}
	.cbar span {
		display: block;
		height: 100%;
		background: var(--sun-strong);
	}
	th[scope='row'] {
		font-weight: 600;
		white-space: nowrap;
	}
	.linkish {
		background: none;
		border: 0;
		padding: 0;
		font: inherit;
		font-weight: inherit;
		color: var(--accent);
		text-decoration: underline;
		cursor: pointer;
	}

	/* 5. Як рахуємо */
	.how-list {
		margin: 0 0 0.75rem;
		padding-left: 1.2rem;
		display: grid;
		gap: 0.4rem;
		max-width: 60rem;
	}
	.formula {
		margin: 0 0 0.75rem;
		padding: 0.6rem 0.85rem;
		border-radius: 10px;
		background: #f3f6fa;
		color: #3d4857;
		max-width: 60rem;
	}
	.notes {
		margin: 0;
		padding-left: 1.2rem;
	}
	.security {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		margin: 1rem 0 0;
	}

	@media (max-width: 1100px) {
		.now-grid {
			grid-template-columns: 1fr;
		}
		.stats {
			grid-template-columns: repeat(auto-fit, minmax(min(100%, 12.5rem), 1fr));
		}
	}
	@media (max-width: 700px) {
		.block {
			padding: 1.25rem 1.1rem;
		}
		h1 {
			font-size: 1.8rem;
		}
		.statement {
			font-size: 1.3rem;
		}
		.nm-v .big-num {
			font-size: 3.8rem;
		}
		.pb-row {
			grid-template-columns: minmax(0, 1fr) auto;
			row-gap: 0.25rem;
		}
		.pb-row .pb {
			grid-column: 1 / -1;
			grid-row: 2;
		}
		.pb-scale {
			display: none;
		}
		.sort {
			margin-left: 0;
		}
	}
	/* Вузький екран: проста таблиця стає списком «назва → індекс і стан» */
	@media (max-width: 820px) {
		.rank:not(.detailed) thead {
			position: absolute;
			width: 1px;
			height: 1px;
			overflow: hidden;
			clip: rect(0 0 0 0);
		}
		.rank:not(.detailed),
		.rank:not(.detailed) tbody {
			display: block;
		}
		.rank:not(.detailed) tr {
			display: flex;
			flex-wrap: wrap;
			align-items: center;
			gap: 0.4rem 0.75rem;
			padding: 0.75rem 0.9rem;
			border-bottom: 1px solid #e3e8ef;
		}
		.rank:not(.detailed) td {
			display: block;
			padding: 0;
			border: 0;
		}
		.rank:not(.detailed) td.name {
			flex: 1 1 100%;
		}
		.rank:not(.detailed) tr.crit {
			box-shadow: inset 4px 0 0 var(--deficit);
		}
		.rank:not(.detailed) tr.crit td:first-child {
			box-shadow: none;
		}
	}

	/* ---------- Телефон (≤640): нативний вигляд ---------- */
	.pf-top {
		display: flex;
		gap: 0.5rem;
		margin-bottom: 0.6rem;
	}
	.pf-top .search {
		flex: 1 1 auto;
		min-width: 0;
	}
	.pf-btn {
		flex: none;
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		min-height: 44px;
		padding: 0 0.85rem;
		border-radius: 12px;
		border: 1px solid var(--line);
		background: var(--surface);
		font: inherit;
		font-weight: 600;
		font-size: 0.95rem;
		color: var(--text-2);
		cursor: pointer;
	}
	.pf-n {
		display: grid;
		place-items: center;
		min-width: 1.25rem;
		height: 1.25rem;
		padding: 0 0.3rem;
		border-radius: 999px;
		background: var(--navy);
		color: #fff;
		font-size: 0.75rem;
	}
	.pf-chips {
		margin-bottom: 0.75rem;
	}
	.chip-n {
		font-weight: 500;
		opacity: 0.7;
		font-size: 0.8rem;
	}
	.sheet {
		margin: auto 0 0;
		width: 100%;
		max-width: 100%;
		max-height: 88dvh;
		padding: 0;
		border: 0;
		border-radius: 20px 20px 0 0;
		background: var(--surface);
		color: var(--text);
		box-shadow: var(--shadow-lg);
		overscroll-behavior: contain;
	}
	.sheet::backdrop {
		background: rgba(10, 31, 56, 0.45);
	}
	@media (prefers-reduced-motion: no-preference) {
		.sheet[open] {
			animation: sheet-up 0.32s cubic-bezier(0.22, 1, 0.36, 1);
		}
		@keyframes sheet-up {
			from {
				transform: translateY(100%);
			}
		}
	}
	.sheet-in {
		padding: 0.5rem 1rem calc(1rem + var(--safe-b, 0px));
	}
	.grab {
		display: block;
		width: 2.5rem;
		height: 4px;
		border-radius: 999px;
		background: var(--line);
		margin: 0 auto 0.5rem;
	}
	.sheet-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.sheet-head h3 {
		margin: 0;
		font-size: 1.15rem;
	}
	.sheet-x {
		display: grid;
		place-items: center;
		width: 44px;
		height: 44px;
		margin-right: -0.5rem;
		border: 0;
		background: none;
		color: var(--muted);
		cursor: pointer;
	}
	.sheet-l {
		margin: 0.75rem 0 0.35rem;
		font-size: 0.8rem;
		font-weight: 700;
		letter-spacing: 0.05em;
		text-transform: uppercase;
		color: var(--muted);
	}
	.opts {
		display: grid;
		border: 1px solid var(--line-soft);
		border-radius: 14px;
		overflow: hidden;
	}
	.opt {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		min-height: 50px;
		padding: 0 1rem;
		border: 0;
		border-top: 1px solid var(--line-soft);
		background: var(--surface);
		font: inherit;
		font-size: 1rem;
		text-align: left;
		color: var(--text);
		cursor: pointer;
	}
	.opt:first-child {
		border-top: 0;
	}
	.opt[role='radio'] {
		justify-content: flex-start;
	}
	.radio {
		flex: none;
		width: 1.25rem;
		height: 1.25rem;
		border-radius: 50%;
		border: 2px solid var(--line-strong);
		transition:
			border-width 0.15s,
			border-color 0.15s;
	}
	.opt[aria-checked='true'] .radio {
		border: 6px solid var(--navy-3);
	}
	.opt[aria-checked='true'] .sw {
		background: var(--navy-3);
	}
	.opt[aria-checked='true'] .sw i {
		transform: translateX(1rem);
	}
	.opt .sw {
		flex: none;
	}
	.sheet-foot {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.6rem;
		margin-top: 1rem;
	}
	.sheet-foot .btn {
		justify-content: center;
	}
	.rank-list,
	.cat-list {
		list-style: none;
		margin: 0;
		padding: 0;
		border: 1px solid var(--card-line);
		border-radius: 14px;
		overflow: hidden;
		background: var(--surface);
	}
	.rank-list li + li,
	.cat-list li + li {
		border-top: 1px solid var(--line-soft);
	}
	.rank-list li.crit {
		box-shadow: inset 4px 0 0 var(--deficit);
	}
	.rank-list a {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		grid-template-areas: 'name badge' 'sub badge' 'st st';
		align-items: center;
		gap: 0.15rem 0.6rem;
		padding: 0.7rem 0.9rem;
		min-height: 64px;
		color: var(--text);
		text-decoration: none;
	}
	.rank-list a:active,
	.cat-list button:active {
		background: var(--surface-2);
	}
	.rl-name {
		grid-area: name;
		font-weight: 650;
		line-height: 1.3;
		display: -webkit-box;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		overflow: hidden;
	}
	.rl-badge {
		grid-area: badge;
		align-self: start;
	}
	.rl-sub {
		grid-area: sub;
		font-size: 0.8rem;
		color: var(--muted);
	}
	.rank-list .rl-st {
		grid-area: st;
		margin-top: 0.2rem;
		white-space: normal;
		font-size: 0.875rem;
	}
	.cat-list button {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		gap: 0.3rem 0.75rem;
		align-items: center;
		width: 100%;
		padding: 0.7rem 0.9rem;
		border: 0;
		background: none;
		font: inherit;
		text-align: left;
		color: var(--text);
		cursor: pointer;
	}
	.ct-name {
		font-weight: 650;
		color: var(--accent);
	}
	.cbar.ct-bar {
		grid-column: 1 / -1;
		width: 100%;
		margin: 0;
	}
	.ct-sub {
		grid-column: 1 / -1;
		font-size: 0.8rem;
		color: var(--muted);
	}

	@media (max-width: 640px) {
		.head {
			margin-bottom: 1rem;
			gap: 0.5rem;
		}
		h1 {
			font-size: 1.45rem;
		}
		.lead {
			font-size: 0.975rem;
		}
		.story {
			gap: 0.875rem;
		}
		.block {
			padding: 1rem;
			border-radius: 14px;
			box-shadow: var(--shadow);
		}
		.risk,
		.pot {
			border-left-width: 4px;
		}
		.kicker {
			font-size: 0.8rem;
			margin-bottom: 0.6rem;
		}
		.step {
			width: 1.4rem;
			height: 1.4rem;
			font-size: 0.75rem;
		}
		.statement {
			font-size: 1.1rem;
		}
		.sub {
			font-size: 0.925rem;
			margin-bottom: 0.75rem;
		}
		.now-grid {
			gap: 1rem;
		}
		.nm-l {
			font-size: 1rem;
		}
		.nm-v .big-num {
			font-size: 3.6rem;
		}
		.nm-v .u {
			font-size: 1.8rem;
		}
		.nm-s {
			font-size: 1rem;
			margin-bottom: 0.8rem;
		}
		.mix {
			height: 14px;
		}
		.stats {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 0.625rem;
		}
		.stats > :global(:last-child:nth-child(odd)) {
			grid-column: 1 / -1;
		}
		.crit-list {
			gap: 0.5rem;
			margin-bottom: 0.75rem;
		}
		.crit-list a {
			padding: 0.6rem 0.75rem;
			gap: 0.6rem;
			min-height: 56px;
		}
		.cl-ic {
			width: 1.8rem;
			height: 1.8rem;
		}
		.cl-name {
			font-size: 0.95rem;
			display: -webkit-box;
			-webkit-box-orient: vertical;
			-webkit-line-clamp: 2;
			line-clamp: 2;
			overflow: hidden;
		}
		.cl-do {
			font-size: 0.8rem;
		}
		.more-btn,
		.pot-foot .btn,
		.more .btn {
			width: 100%;
			justify-content: center;
		}
		.pot-bars {
			margin: 0.75rem 0 1rem;
		}
		.pb-v {
			font-size: 1.05rem;
		}
		.pb {
			height: 16px;
		}
		.pot-facts {
			font-size: 0.95rem;
		}
		.index-explain {
			font-size: 0.9rem;
			padding: 0.65rem 0.8rem;
			margin-bottom: 0.9rem;
		}
		.rank-bar {
			margin-bottom: 0.5rem;
		}
		.found {
			font-size: 0.9rem;
		}
		.security {
			align-items: flex-start;
		}
	}
</style>
