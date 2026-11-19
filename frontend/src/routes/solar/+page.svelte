<script lang="ts">
	// «Де ставити СЕС»: програма для громади. Сценарій (тариф, ціни) → перерахунок на сервері;
	// бюджет і пріоритет → жадібний добір об'єктів на клієнті → обґрунтований перелік для бюджету чи донорів.
	import { page } from '$app/state';
	import { replaceState } from '$app/navigation';
	import { getJSON, qs, errMessage, ApiError, type SolarList, type SolarItem, type SolarDetail, type Summary } from '#lib/api.ts';
	import { num } from '#lib/format.ts';
	import Status from '#lib/Status.svelte';
	import ForecastCard from '#lib/ForecastCard.svelte';
	import { simulate } from '#lib/SolarScenario.svelte';

	type Excluded = { id: number; name: string; category_short: string; reason: string };
	type ListX = SolarList & {
		excluded?: Excluded[];
		params: SolarList['params'] & { capex_fixed_uah?: number; daytime_share?: number; base_year?: number };
	};

	// Значення за замовчуванням бекенду (METHODOLOGY §7) — для кнопки «Скинути»
	const DEF = { tariff: 8, capex: 30000, fixed: 60000, budget: 10 };
	const HEALTH = "Охорона здоров'я";
	const EDU = ['Заклади освіти', 'Дошкільні заклади'];

	const sp = page.url.searchParams;
	const qn = (k: string): number | null => {
		const v = sp.get(k);
		const n = v === null ? NaN : Number(v);
		return Number.isFinite(n) && n >= 0 ? n : null;
	};

	let tariff = $state<number | null>(qn('tariff') ?? DEF.tariff);
	let capex = $state<number | null>(qn('capex') ?? DEF.capex);
	let fixed = $state<number | null>(qn('fixed') ?? DEF.fixed);
	let budgetM = $state<number | null>(qn('budget') ?? DEF.budget);
	let priority = $state<'payback' | 'critical'>(sp.get('priority') === 'critical' ? 'critical' : 'payback');

	let data = $state<ListX | null>(null);
	let summary = $state<Summary | null>(null);
	let example = $state<SolarDetail | null>(null);
	let error = $state<string | null>(null);
	let notReady = $state(false);
	let loading = $state(true);
	let refreshing = $state(false);

	const valid = (v: number | null, min = 0.0001) => v !== null && Number.isFinite(v) && v >= min;
	const query = $derived(
		qs({
			tariff: valid(tariff) ? tariff : null,
			capex: valid(capex) ? capex : null,
			fixed: valid(fixed, 0) ? fixed : null
		})
	);

	let reqNo = 0;
	async function load(q: string) {
		const my = ++reqNo;
		if (data) refreshing = true;
		else loading = true;
		error = null;
		notReady = false;
		try {
			const d = await getJSON<ListX>('/api/solar' + q);
			if (my !== reqNo) return;
			data = d;
			// приклад для пояснення «чому під власне споживання» — найкраща за окупністю будівля
			const top = d.items.find((i) => i.rank === 1) ?? d.items[0];
			if (top) getJSON<SolarDetail>(`/api/solar/${top.id}${q}`).then((x) => (example = x)).catch(() => {});
		} catch (e) {
			if (my !== reqNo) return;
			data = null;
			if (e instanceof ApiError && e.status === 404) notReady = true;
			else error = errMessage(e);
		} finally {
			if (my === reqNo) {
				loading = false;
				refreshing = false;
			}
		}
	}

	// Живий перерахунок із невеликою затримкою, поки людина друкує
	$effect(() => {
		const q = query;
		const t = setTimeout(() => load(q), data ? 350 : 0);
		return () => clearTimeout(t);
	});

	getJSON<Summary>('/api/summary').then((s) => (summary = s)).catch(() => {});

	// Адреса сторінки зберігає сценарій (можна надіслати посилання) — без навігації
	$effect(() => {
		const p = new URLSearchParams();
		if (valid(tariff) && tariff !== DEF.tariff) p.set('tariff', String(tariff));
		if (valid(capex) && capex !== DEF.capex) p.set('capex', String(capex));
		if (valid(fixed, 0) && fixed !== DEF.fixed) p.set('fixed', String(fixed));
		if (valid(budgetM, 0) && budgetM !== DEF.budget) p.set('budget', String(budgetM));
		if (priority !== 'payback') p.set('priority', priority);
		const s = p.toString();
		try {
			replaceState(`${location.pathname}${s ? `?${s}` : ''}`, {}).catch(() => {});
		} catch {
			/* роутер ще не готовий — пропускаємо */
		}
	});

	function reset() {
		tariff = DEF.tariff;
		capex = DEF.capex;
		fixed = DEF.fixed;
		budgetM = DEF.budget;
		priority = 'payback';
	}

	// ——— Пріоритет і жадібний добір у межах бюджету ———
	function tier(it: SolarItem): number {
		if (it.category_short === HEALTH) return 0;
		if (EDU.includes(it.category_short)) return 1;
		return 2;
	}
	const tierLabel = ['Лікарня / медзаклад', 'Школа / садок', ''];
	const pb = (it: SolarItem) => it.payback_years ?? Infinity;

	const items = $derived(data?.items ?? []);
	const ordered = $derived(
		[...items].sort((a, b) =>
			priority === 'critical'
				? tier(a) - tier(b) || pb(a) - pb(b) || (b.savings_uah_year ?? 0) - (a.savings_uah_year ?? 0)
				: pb(a) - pb(b) || (b.savings_uah_year ?? 0) - (a.savings_uah_year ?? 0)
		)
	);
	const budget = $derived(Math.max(0, (budgetM ?? 0) * 1e6));
	const plan = $derived.by(() => {
		let left = budget;
		const picked: (SolarItem & { cum: number })[] = [];
		const rest: SolarItem[] = [];
		let cum = 0;
		for (const it of ordered) {
			const c = it.capex_uah ?? Infinity;
			if (it.payback_years !== null && c <= left) {
				left -= c;
				cum += c;
				picked.push({ ...it, cum });
			} else rest.push(it);
		}
		return { picked, rest, left };
	});

	function stats(list: SolarItem[]) {
		const s = (f: (i: SolarItem) => number | null) => list.reduce((a, i) => a + (f(i) ?? 0), 0);
		const pbs = list.map((i) => i.payback_years).filter((v): v is number => v !== null).sort((a, b) => a - b);
		const med = pbs.length ? (pbs.length % 2 ? pbs[(pbs.length - 1) / 2] : (pbs[pbs.length / 2 - 1] + pbs[pbs.length / 2]) / 2) : null;
		return {
			n: list.length,
			kw: s((i) => i.kw_recommended),
			capex: s((i) => i.capex_uah),
			save: s((i) => i.savings_uah_year),
			self: s((i) => i.self_consumed_kwh_year),
			elec: s((i) => i.elec_kwh_year),
			med,
			health: list.filter((i) => i.category_short === HEALTH).length,
			edu: list.filter((i) => EDU.includes(i.category_short)).length
		};
	}
	const all = $derived(stats(items));
	const sel = $derived(stats(plan.picked));
	const healthTotal = $derived(items.filter((i) => i.category_short === HEALTH).length);

	// Енергонезалежність: частка всієї електроенергії комунальних будівель, яку дасть власне сонце
	const baseYear = $derived(String(data?.params.base_year ?? 2025));
	const cityElec = $derived(summary?.years?.[baseYear]?.elec_kwh ?? null);
	const cityBuildings = $derived(summary?.buildings ?? null);
	const denom = $derived(cityElec ?? all.elec);
	const indSel = $derived(denom > 0 ? sel.self / denom : 0);
	const indAll = $derived(denom > 0 ? all.self / denom : 0);

	const mln = (v: number, d = 1) => num(v / 1e6, d);
	const budgetMax = $derived(Math.max(5, Math.ceil(all.capex / 1e6)));

	// ——— Крива «гроші → енергонезалежність» ———
	const CW = 560;
	const CH = 220;
	const CP = { l: 44, r: 16, t: 14, b: 34 };
	const curve = $derived.by(() => {
		const seq = [...plan.picked, ...plan.rest.filter((i) => i.payback_years !== null)];
		let x = 0;
		let y = 0;
		const pts = [{ x: 0, y: 0 }];
		for (const it of seq) {
			x += it.capex_uah ?? 0;
			y += it.self_consumed_kwh_year ?? 0;
			pts.push({ x, y });
		}
		const xMax = Math.max(x, budget, 1);
		const yMax = denom > 0 ? Math.max(y / denom, 0.01) : 1;
		const yTop = Math.ceil((yMax * 100) / 5) * 5; // відсотки, кратні 5
		const X = (v: number) => CP.l + (v / xMax) * (CW - CP.l - CP.r);
		const Y = (share: number) => CP.t + (1 - (share * 100) / yTop) * (CH - CP.t - CP.b);
		const d = pts.map((p, i) => `${i ? 'L' : 'M'}${X(p.x).toFixed(1)},${Y(denom ? p.y / denom : 0).toFixed(1)}`).join(' ');
		const selCost = plan.picked.length ? plan.picked[plan.picked.length - 1].cum : 0;
		const xTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * xMax);
		const yTicks = [0, yTop / 2, yTop];
		return { d, X, Y, xMax, yTop, selCost, xTicks, yTicks };
	});

	// ——— Ілюстрація: окупність за різного розміру станції (на реальній будівлі-прикладі) ———
	const sizes = $derived.by(() => {
		if (!example || !data) return [];
		const kwRec = example.item.kw_recommended ?? 0;
		if (kwRec <= 0) return [];
		const p = {
			tariff: data.params.tariff_uah_kwh,
			capex: data.params.capex_uah_per_kw,
			fixed: data.params.capex_fixed_uah ?? DEF.fixed,
			daytime: data.params.daytime_share ?? 0.6
		};
		return [
			{ k: 0.5, label: 'Половина' },
			{ k: 1, label: 'Під власне споживання' },
			{ k: 2, label: 'Удвічі більша' },
			{ k: 3, label: 'Утричі більша' }
		].map(({ k, label }) => {
			const r = simulate(example!.monthly, kwRec, kwRec * k, p);
			return { k, label, ...r, surplusShare: r.gen > 0 ? r.surplus / r.gen : 0 };
		});
	});
	const sizeMax = $derived(Math.max(1, ...sizes.map((s) => s.payback ?? 0)));

	// ——— Експорт ———
	function csvCell(v: string | number | null | undefined): string {
		if (v === null || v === undefined) return '';
		const s = typeof v === 'number' ? String(v).replace('.', ',') : v;
		return /[;"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
	}
	function exportCsv() {
		if (!data) return;
		const head = [
			['Перелік об’єктів для встановлення СЕС у межах бюджету'],
			[`Бюджет програми, грн`, budget],
			[`Пріоритет`, priority === 'critical' ? 'критичні заклади першими' : 'найшвидша окупність'],
			[`Тариф, грн/кВт·год`, data.params.tariff_uah_kwh],
			[`Вартість монтажу, грн/кВт`, data.params.capex_uah_per_kw],
			[`Фіксована частина на об’єкт, грн`, data.params.capex_fixed_uah ?? ''],
			[],
			['№', 'ID', 'Будівля', 'Категорія', 'Потужність, кВт', 'Генерація, кВт·год/рік', 'Покриття потреби, %', 'Вартість, грн', 'Наростаючим підсумком, грн', 'Економія, грн/рік', 'Окупність, років']
		];
		const rows = plan.picked.map((it, i) => [
			i + 1, it.id, it.name, it.category_short, it.kw_recommended, it.gen_kwh_year, it.coverage_pct,
			it.capex_uah, it.cum, it.savings_uah_year, it.payback_years
		]);
		const tot = [['', '', 'Разом', `${sel.n} об’єктів`, +sel.kw.toFixed(1), '', '', sel.capex, '', sel.save, sel.med !== null ? +sel.med.toFixed(1) : '']];
		const text = [...head, ...rows, ...tot].map((r) => r.map(csvCell).join(';')).join('\r\n');
		const blob = new Blob(['﻿' + text], { type: 'text/csv;charset=utf-8' });
		const a = document.createElement('a');
		a.href = URL.createObjectURL(blob);
		a.download = `SES_perelik_${mln(budget).replace(/\s/g, '')}mln.csv`;
		a.click();
		setTimeout(() => URL.revokeObjectURL(a.href), 1000);
	}

	const detailQs = $derived.by(() => {
		const p = new URLSearchParams();
		if (valid(tariff) && tariff !== DEF.tariff) p.set('tariff', String(tariff));
		if (valid(capex) && capex !== DEF.capex) p.set('capex', String(capex));
		if (valid(fixed, 0) && fixed !== DEF.fixed) p.set('fixed', String(fixed));
		const s = p.toString();
		return s ? `?${s}` : '';
	});
	const today = new Date().toLocaleDateString('uk-UA');
</script>

<svelte:head><title>Де ставити СЕС · City Insight Map · Енергія</title></svelte:head>

<div class="page-head">
	<div>
		<h1>Де ставити сонячні станції</h1>
		<p class="lead">
			Програма СЕС для комунальних будівель: скільки коштує, скільки заощадить і наскільки громада стане
			енергонезалежнішою. Задайте бюджет — отримаєте обґрунтований перелік об’єктів.
		</p>
	</div>
</div>

<!-- Шапка для друку -->
<div class="print-only print-head">
	<h1>Перелік об’єктів для встановлення сонячних станцій</h1>
	<p>
		Бюджет програми: {mln(budget)} млн грн · пріоритет: {priority === 'critical' ? 'критичні заклади першими' : 'найшвидша окупність'}
		· тариф {num(data?.params.tariff_uah_kwh, 2)} грн/кВт·год · монтаж {num(data?.params.capex_uah_per_kw)} грн/кВт +
		{num(data?.params.capex_fixed_uah)} грн на об’єкт · сформовано {today}
	</p>
</div>

<section class="card scenario no-print" aria-labelledby="sc-h">
	<div class="sc-top">
		<h2 id="sc-h">Сценарій програми</h2>
		<button type="button" class="linkbtn" onclick={reset}>Скинути до типових</button>
	</div>
	<div class="sc-grid">
		<div class="field budget">
			<label for="s-budget">Бюджет програми, млн грн</label>
			<div class="brow">
				<input
					type="range"
					min="0"
					max={budgetMax}
					step="0.5"
					bind:value={budgetM}
					aria-label="Бюджет програми, млн грн (повзунок)"
					aria-valuetext="{num(budgetM, 1)} млн грн"
				/>
				<input id="s-budget" type="number" min="0" step="0.5" inputmode="decimal" bind:value={budgetM} />
			</div>
			<small class="muted">уся програма коштувала б ≈ {mln(all.capex)} млн грн</small>
		</div>
		<fieldset class="field prio">
			<legend>Кого ставимо першими</legend>
			<div class="seg" role="radiogroup" aria-label="Пріоритет">
				<label class:on={priority === 'payback'}>
					<input type="radio" name="prio" value="payback" bind:group={priority} />
					Найшвидша окупність
				</label>
				<label class:on={priority === 'critical'}>
					<input type="radio" name="prio" value="critical" bind:group={priority} />
					Критичні заклади першими
				</label>
			</div>
			<small class="muted">
				{priority === 'critical'
					? 'Спершу лікарні, потім школи й садки, далі решта; усередині — за окупністю.'
					: 'Кожна гривня дає найбільшу економію; критичність не враховуємо.'}
			</small>
		</fieldset>
		<div class="field">
			<label for="s-tariff">Тариф, грн/кВт·год</label>
			<input id="s-tariff" type="number" min="0.1" step="0.1" inputmode="decimal" bind:value={tariff} />
		</div>
		<div class="field">
			<label for="s-capex">Монтаж, грн за 1 кВт</label>
			<input id="s-capex" type="number" min="1000" step="1000" inputmode="decimal" bind:value={capex} />
		</div>
		<div class="field">
			<label for="s-fixed">Фіксовано на об’єкт, грн</label>
			<input id="s-fixed" type="number" min="0" step="5000" inputmode="decimal" bind:value={fixed} />
			<small class="muted">проєкт і підключення</small>
		</div>
	</div>
	<p class="sc-status muted small" aria-live="polite">
		{#if refreshing}Перераховуємо…{:else if data}Розрахунок актуальний для цих параметрів.{/if}
	</p>
</section>

<Status {loading} {error} retry={() => load(query)} />

{#if notReady && !loading}
	<div class="notice notice-warn" role="status">
		<p><strong>Розрахунок ще не готовий.</strong> Модуль оцінки сонячних станцій зараз доробляється. Спробуйте трохи пізніше.</p>
	</div>
{/if}

{#if data && !loading}
	<!-- ——— Що дає бюджет ——— -->
	<section class="hero" aria-labelledby="hero-h" class:dim={refreshing}>
		<div class="hero-main panel">
			<p class="eyebrow">За бюджет {mln(budget)} млн грн</p>
			<h2 id="hero-h" class="hero-title">
				{num(sel.n)} {sel.n === 1 ? 'станція' : sel.n >= 2 && sel.n <= 4 ? 'станції' : 'станцій'} · {num(sel.kw)} кВт
				<span class="muted hero-of">з {num(all.n)} придатних будівель</span>
			</h2>
			<ul class="kpis">
				<li>
					<span>Вартість</span>
					<strong>{mln(sel.capex)} <em>млн грн</em></strong>
					<small>залишок бюджету {mln(plan.left, 2)} млн грн</small>
				</li>
				<li>
					<span>Економія</span>
					<strong>{mln(sel.save, 2)} <em>млн грн/рік</em></strong>
					<small>менше платимо за електроенергію щороку</small>
				</li>
				<li>
					<span>Медіанна окупність</span>
					<strong>{sel.med !== null ? num(sel.med, 1) : '—'} <em>року</em></strong>
					<small>половина станцій окупиться швидше</small>
				</li>
				<li>
					<span>Критичні заклади</span>
					<strong>{num(sel.health)} <em>з {num(healthTotal)}</em></strong>
					<small>медзакладів отримають СЕС; шкіл і садків — {num(sel.edu)}</small>
				</li>
			</ul>

			<div class="indep">
				<p class="indep-txt">
					<strong>Енергонезалежність громади: +{num(indSel * 100, 1)} %</strong>
					<span class="muted">
						електроенергії всіх {cityBuildings ? num(cityBuildings) : ''} комунальних будівель дасть власне сонце
						(уся програма — {num(indAll * 100, 1)} %)
					</span>
				</p>
				<div class="ibar" role="img" aria-label="Частка електроенергії з власних СЕС: бюджет {num(indSel * 100, 1)} %, уся програма {num(indAll * 100, 1)} %">
					<span class="ib-all" style:width="{indAll * 100}%"></span>
					<span class="ib-sel" style:width="{indSel * 100}%"></span>
					<span class="ib-30" style:left="30%"><b>~30 % — стеля для сонця</b></span>
				</div>
				<div class="ilegend small">
					<span><i class="sw sel"></i> у межах бюджету</span>
					<span><i class="sw all"></i> уся програма ({num(all.n)} будівель, {mln(all.capex)} млн грн)</span>
					<span><i class="sw grid"></i> з мережі</span>
				</div>
			</div>
		</div>

		<figure class="panel curve">
			<figcaption>
				<strong>Як росте незалежність із кожним мільйоном</strong>
				<span class="muted small">Будівлі додаються в порядку пріоритету; лінія — ваш бюджет.</span>
			</figcaption>
			<svg viewBox="0 0 {CW} {CH}" role="img" aria-label="Частка електроенергії громади з власного сонця залежно від вкладених коштів. За {mln(budget)} млн грн — {num(indSel * 100, 1)} %, за всю програму {mln(all.capex)} млн грн — {num(indAll * 100, 1)} %.">
				{#each curve.yTicks as t (t)}
					<line x1={CP.l} x2={CW - CP.r} y1={curve.Y(t / 100)} y2={curve.Y(t / 100)} class="grid" />
					<text x={CP.l - 6} y={curve.Y(t / 100)} class="ax" text-anchor="end" dominant-baseline="middle">{t} %</text>
				{/each}
				{#each curve.xTicks as t, i (i)}
					<text x={curve.X(t)} y={CH - CP.b + 16} class="ax" text-anchor={i === 0 ? 'start' : i === 4 ? 'end' : 'middle'}>{mln(t, 0)}</text>
				{/each}
				<text x={CW - CP.r} y={CH - 4} class="ax" text-anchor="end">млн грн</text>
				<rect x={CP.l} y={CP.t} width={Math.max(0, curve.X(curve.selCost) - CP.l)} height={CH - CP.t - CP.b} class="selzone" />
				<path d={curve.d} class="cline" />
				<line x1={curve.X(budget)} x2={curve.X(budget)} y1={CP.t} y2={CH - CP.b} class="bline" />
				<text x={Math.min(curve.X(budget) + 6, CW - 120)} y={CP.t + 12} class="blabel">бюджет {mln(budget)} млн</text>
				<circle cx={curve.X(curve.selCost)} cy={curve.Y(indSel)} r="5" class="bdot" />
			</svg>
		</figure>
	</section>

	<!-- ——— Перелік ——— -->
	<section class="card list" aria-labelledby="list-h">
		<div class="list-head">
			<div>
				<h2 id="list-h">Що встигнемо за {mln(budget)} млн грн</h2>
				<p class="muted small">
					Об’єкти в порядку пріоритету. Якщо наступна станція не вміщується в залишок бюджету, беремо меншу з черги.
					Підходить як додаток до бюджетного запиту чи заявки донору.
				</p>
			</div>
			<div class="list-actions no-print">
				<button type="button" class="btn" onclick={exportCsv} disabled={!plan.picked.length}>Завантажити CSV</button>
				<button type="button" class="btn btn-secondary" onclick={() => window.print()}>Друк / PDF</button>
			</div>
		</div>

		{#if plan.picked.length}
			<div class="table-wrap">
				<table>
					<caption class="visually-hidden">Перелік об’єктів у межах бюджету</caption>
					<thead>
						<tr>
							<th scope="col" class="num">№</th>
							<th scope="col">Будівля</th>
							<th scope="col" class="num">Станція, <span class="unit">кВт</span></th>
							<th scope="col" class="num">Покриття <span class="unit">потреби</span></th>
							<th scope="col" class="num">Вартість, <span class="unit">тис. грн</span></th>
							<th scope="col" class="num">Наростаючим, <span class="unit">млн грн</span></th>
							<th scope="col" class="num">Економія, <span class="unit">тис. грн/рік</span></th>
							<th scope="col" class="num">Окупність, <span class="unit">років</span></th>
						</tr>
					</thead>
					<tbody>
						{#each plan.picked as it, i (it.id)}
							<tr>
								<td class="num">{i + 1}</td>
								<td class="name">
									<a href="/solar/{it.id}{detailQs}">{it.name}</a>
									<div class="meta">
										<span class="muted small">{it.category_short}</span>
										{#if tier(it) === 0}<span class="tag crit">✚ критичний</span>{/if}
									</div>
								</td>
								<td class="num">{num(it.kw_recommended, 1)}</td>
								<td class="num">{it.coverage_pct !== null ? `${num(it.coverage_pct)} %` : '—'}</td>
								<td class="num">{num((it.capex_uah ?? 0) / 1000)}</td>
								<td class="num">{mln(it.cum, 2)}</td>
								<td class="num">{num((it.savings_uah_year ?? 0) / 1000)}</td>
								<td class="num"><strong>{num(it.payback_years, 1)}</strong></td>
							</tr>
						{/each}
					</tbody>
					<tfoot>
						<tr class="total">
							<th scope="row" colspan="2">Разом: {num(sel.n)} об’єктів</th>
							<td class="num">{num(sel.kw, 1)}</td>
							<td class="num">{sel.elec > 0 ? `${num((sel.self / sel.elec) * 100)} %` : '—'}</td>
							<td class="num">{num(sel.capex / 1000)}</td>
							<td class="num">{mln(sel.capex, 2)}</td>
							<td class="num">{num(sel.save / 1000)}</td>
							<td class="num">мед. {sel.med !== null ? num(sel.med, 1) : '—'}</td>
						</tr>
					</tfoot>
				</table>
			</div>
		{:else}
			<p class="notice notice-warn">Бюджету не вистачає на жодну станцію. Найдешевша коштує ≈ {num(Math.min(...items.map((i) => i.capex_uah ?? Infinity)))} грн.</p>
		{/if}

		{#if plan.rest.length}
			<details class="rest no-print">
				<summary>Наступні в черзі — не вмістилися в бюджет ({num(plan.rest.length)})</summary>
				<div class="table-wrap">
					<table>
						<thead>
							<tr>
								<th scope="col">Будівля</th>
								<th scope="col" class="num">Станція, <span class="unit">кВт</span></th>
								<th scope="col" class="num">Вартість, <span class="unit">тис. грн</span></th>
								<th scope="col" class="num">Економія, <span class="unit">тис. грн/рік</span></th>
								<th scope="col" class="num">Окупність, <span class="unit">років</span></th>
							</tr>
						</thead>
						<tbody>
							{#each plan.rest as it (it.id)}
								<tr>
									<td class="name">
										<a href="/solar/{it.id}{detailQs}">{it.name}</a>
										<div class="meta">
											<span class="muted small">{it.category_short}</span>
											{#if tier(it) === 0}<span class="tag crit">✚ критичний</span>{/if}
										</div>
									</td>
									<td class="num">{num(it.kw_recommended, 1)}</td>
									<td class="num">{num((it.capex_uah ?? 0) / 1000)}</td>
									<td class="num">{num((it.savings_uah_year ?? 0) / 1000)}</td>
									<td class="num">{it.payback_years !== null ? num(it.payback_years, 1) : 'не окупається'}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</details>
		{/if}
	</section>

	<!-- ——— Чому під власне споживання ——— -->
	<section class="why no-print" aria-labelledby="why-h">
		<div class="card why-txt">
			<h2 id="why-h">Чому станція — під власне споживання будівлі</h2>
			<p>
				Комунальний заклад <strong>не може продати надлишок</strong> електроенергії в мережу. Тому все, що панелі
				виробили понад денне споживання будівлі, просто пропадає — а гроші за ці панелі вже витрачено.
			</p>
			<p>
				Ми підбираємо найбільшу станцію, за якої <strong>навіть у найсонячніший місяць</strong> уся генерація
				споживається самою будівлею. Тому сонце покриває лише частину потреби — зазвичай до 30–40 %: уночі, взимку
				й у похмурі дні енергія все одно йде з мережі.
			</p>
			{#if sizes.length}
				<div class="sizes" role="img" aria-label="Окупність за різного розміру станції: {sizes.map((s) => `${s.label} ${num(s.kw, 0)} кВт — ${s.payback !== null ? num(s.payback, 1) : '—'} року, надлишок ${num(s.surplusShare * 100)} %`).join('; ')}">
					<p class="small muted sizes-cap">
						Приклад: {example?.item.name.length && example.item.name.length > 70 ? example.item.name.slice(0, 68) + '…' : example?.item.name}
					</p>
					{#each sizes as s (s.k)}
						<div class="srow" class:best={s.k === 1}>
							<span class="sl">{s.label}<br /><small class="muted">{num(s.kw, 0)} кВт</small></span>
							<span class="sbar"><i style:width="{((s.payback ?? 0) / sizeMax) * 100}%"></i></span>
							<span class="sv"><strong>{s.payback !== null ? num(s.payback, 1) : '—'} р.</strong><br /><small class="muted">надлишок {num(s.surplusShare * 100)} %</small></span>
						</div>
					{/each}
					<p class="small muted">Довжина смуги — термін окупності: що коротша, то краще.</p>
				</div>
			{/if}
		</div>
		<div class="why-side">
			<ForecastCard kw={null} />
		</div>
	</section>

	{#if data.excluded?.length}
		<details class="card no-print">
			<summary>Будівлі без розрахунку ({num(data.excluded.length)}) — чому</summary>
			<div class="table-wrap">
				<table>
					<thead><tr><th scope="col">Будівля</th><th scope="col">Категорія</th><th scope="col">Причина</th></tr></thead>
					<tbody>
						{#each data.excluded as e (e.id)}
							<tr><td class="name">{e.name}</td><td>{e.category_short}</td><td class="small">{e.reason}</td></tr>
						{/each}
					</tbody>
				</table>
			</div>
		</details>
	{/if}

	{#if data.params.source_notes?.length}
		<section class="card notes">
			<h2>Припущення та джерела</h2>
			<ul>
				{#each data.params.source_notes as n, i (i)}<li>{n}</li>{/each}
				<li>Енергонезалежність = електроенергія, яку будівлі споживуть із власних СЕС, ÷ уся електроенергія {cityBuildings ? `${num(cityBuildings)} ` : ''}комунальних будівель за {baseYear} рік{cityElec ? ` (${num(cityElec / 1e6, 2)} млн кВт·год)` : ''}.</li>
			</ul>
			<p class="muted small">Це аналітична оцінка для планування, а не проєкт станцій.</p>
		</section>
	{/if}
{/if}

<style>
	.print-only {
		display: none;
	}
	@media print {
		.print-only {
			display: block;
		}
		.page-head {
			display: none;
		}
		.hero .curve {
			display: none;
		}
	}
	.scenario {
		padding: 1rem 1.25rem 0.5rem;
	}
	.sc-top {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 1rem;
	}
	.sc-top h2 {
		margin: 0 0 0.75rem;
	}
	.linkbtn {
		font: inherit;
		font-size: 0.875rem;
		background: none;
		border: 0;
		color: var(--accent);
		text-decoration: underline;
		cursor: pointer;
		padding: 0.25rem;
	}
	.sc-grid {
		display: grid;
		grid-template-columns: minmax(260px, 1.6fr) minmax(300px, 1.8fr) repeat(3, minmax(120px, 1fr));
		gap: 0.75rem 1.25rem;
		align-items: start;
	}
	@media (max-width: 1250px) {
		.sc-grid {
			grid-template-columns: 1fr 1fr 1fr;
		}
		.budget,
		.prio {
			grid-column: span 3;
		}
	}
	@media (max-width: 640px) {
		.sc-grid {
			grid-template-columns: 1fr;
		}
		.budget,
		.prio {
			grid-column: auto;
		}
	}
	.sc-grid input[type='number'] {
		width: 100%;
		max-width: 11rem;
	}
	.brow {
		display: flex;
		gap: 0.75rem;
		align-items: center;
	}
	.brow input[type='range'] {
		flex: 1;
		min-width: 0;
		accent-color: var(--sun-strong);
	}
	.brow input[type='number'] {
		width: 6.5rem;
	}
	fieldset.prio {
		border: 0;
		padding: 0;
		margin: 0;
		min-width: 0;
	}
	.prio legend {
		font-weight: 600;
		font-size: 0.9rem;
		padding: 0;
		margin-bottom: 0.35rem;
	}
	.prio .seg {
		flex-wrap: wrap;
	}
	.prio .seg label {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0.4rem 0.75rem;
		border-radius: 9px;
		font-weight: 600;
		font-size: 0.9rem;
		cursor: pointer;
		margin: 0;
	}
	.prio .seg label.on {
		background: #fff;
		color: var(--navy);
		box-shadow: 0 1px 2px rgba(16, 24, 40, 0.1), 0 2px 6px -2px rgba(16, 24, 40, 0.15);
	}
	.prio .seg input {
		accent-color: var(--navy);
		margin: 0;
	}
	.prio .seg label:has(input:focus-visible) {
		outline: 3px solid var(--focus);
		outline-offset: 1px;
	}
	.sc-status {
		min-height: 1.3em;
		margin: 0.5rem 0 0;
	}

	.hero {
		display: grid;
		grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr);
		gap: 1.25rem;
		margin-bottom: 1.25rem;
		transition: opacity 0.2s;
	}
	.hero.dim {
		opacity: 0.65;
	}
	@media (max-width: 1100px) {
		.hero {
			grid-template-columns: 1fr;
		}
	}
	.hero-main {
		border-top: 5px solid var(--sun);
	}
	.eyebrow {
		margin: 0 0 0.25rem;
	}
	.hero-title {
		font-size: 1.6rem;
		margin-bottom: 1rem;
	}
	.hero-of {
		font-size: 1rem;
		font-weight: 500;
		margin-left: 0.35rem;
	}
	.kpis {
		list-style: none;
		padding: 0;
		margin: 0 0 1.25rem;
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 0.75rem;
	}
	@media (max-width: 700px) {
		.kpis {
			grid-template-columns: 1fr 1fr;
		}
	}
	.kpis li {
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
		padding: 0.6rem 0.75rem;
		border-radius: var(--radius);
		background: #f7f9fb;
		border: 1px solid #e6ebf1;
	}
	.kpis span {
		font-size: 0.8125rem;
		font-weight: 600;
		color: var(--muted);
	}
	.kpis strong {
		font-size: 1.5rem;
		font-variant-numeric: tabular-nums;
		line-height: 1.15;
	}
	.kpis em {
		font-style: normal;
		font-size: 0.85rem;
		color: var(--muted);
	}
	.kpis small {
		font-size: 0.8rem;
		color: var(--muted);
		line-height: 1.3;
	}
	.indep-txt {
		margin: 0 0 0.5rem;
	}
	.indep-txt strong {
		font-size: 1.1rem;
		color: var(--surplus-ink);
		margin-right: 0.35rem;
	}
	.ibar {
		position: relative;
		height: 22px;
		border-radius: 6px;
		background: repeating-linear-gradient(135deg, #eef2f6 0 6px, #e4e9ef 6px 8px);
		margin: 0.5rem 0 1.6rem;
	}
	.ibar span {
		position: absolute;
		top: 0;
		bottom: 0;
		left: 0;
		border-radius: 6px 0 0 6px;
	}
	.ib-all {
		background: #a7d7b4;
	}
	.ib-sel {
		background: var(--surplus);
	}
	.ib-30 {
		width: 0;
		border-left: 2px dashed var(--text);
		top: -4px !important;
		bottom: -4px !important;
		border-radius: 0 !important;
	}
	.ib-30 b {
		position: absolute;
		top: calc(100% + 2px);
		left: 4px;
		white-space: nowrap;
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--muted);
	}
	.ilegend {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem 1rem;
		color: var(--muted);
	}
	.ilegend span {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.sw {
		display: inline-block;
		width: 12px;
		height: 12px;
		border-radius: 3px;
	}
	.sw.sel {
		background: var(--surplus);
	}
	.sw.all {
		background: #a7d7b4;
	}
	.sw.grid {
		background: repeating-linear-gradient(135deg, #eef2f6 0 3px, #cfd6df 3px 4px);
		border: 1px solid #cfd6df;
	}

	.curve {
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.curve figcaption {
		display: flex;
		flex-direction: column;
	}
	.curve svg {
		width: 100%;
		height: auto;
	}
	.curve .grid {
		stroke: #e6ebf1;
	}
	.curve .ax {
		font-size: 11px;
		fill: var(--muted);
		font-variant-numeric: tabular-nums;
	}
	.selzone {
		fill: var(--surplus-soft);
	}
	.cline {
		fill: none;
		stroke: var(--surplus);
		stroke-width: 2.5;
		stroke-linejoin: round;
	}
	.bline {
		stroke: var(--sun-ink);
		stroke-width: 2;
		stroke-dasharray: 5 4;
	}
	.blabel {
		font-size: 12px;
		font-weight: 700;
		fill: var(--sun-ink);
	}
	.bdot {
		fill: #fff;
		stroke: var(--surplus-ink);
		stroke-width: 3;
	}

	.list-head {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		gap: 0.75rem 1.5rem;
		align-items: flex-start;
		margin-bottom: 0.75rem;
	}
	.list-head h2 {
		margin-bottom: 0.25rem;
	}
	.list-head p {
		margin: 0;
		max-width: 75ch;
	}
	.list-actions {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		align-items: center;
	}
	.tag {
		font-size: 0.75rem;
		font-weight: 700;
		padding: 0 0.4rem;
		border-radius: 4px;
	}
	.tag.crit {
		background: var(--bad-soft);
		color: var(--bad);
		border: 1px solid #f0c4c2;
	}
	tfoot .total th,
	tfoot .total td {
		font-weight: 700;
		border-top: 2px solid var(--line-strong);
		background: #f7f9fb;
	}
	.rest {
		margin-top: 1rem;
	}
	.rest summary {
		margin-bottom: 0.6rem;
	}

	.why {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(300px, 400px);
		gap: 1.25rem;
		align-items: start;
		margin-bottom: 1.25rem;
	}
	.why > .card {
		margin: 0;
	}
	@media (max-width: 1000px) {
		.why {
			grid-template-columns: 1fr;
		}
	}
	.why-txt p {
		max-width: 80ch;
	}
	.sizes {
		margin-top: 0.75rem;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}
	.sizes-cap {
		margin: 0 0 0.25rem;
	}
	.srow {
		display: grid;
		grid-template-columns: 11rem minmax(0, 1fr) 8rem;
		gap: 0.75rem;
		align-items: center;
		padding: 0.35rem 0.5rem;
		border-radius: 8px;
		line-height: 1.2;
	}
	.srow.best {
		background: var(--ok-soft);
		outline: 1px solid #bfe1c9;
	}
	.sl {
		font-size: 0.9rem;
		font-weight: 600;
	}
	.sbar {
		height: 14px;
		background: #eef1f5;
		border-radius: 4px;
		overflow: hidden;
	}
	.sbar i {
		display: block;
		height: 100%;
		background: var(--sol-surplus);
	}
	.srow.best .sbar i {
		background: var(--sol-self);
	}
	.sv {
		font-variant-numeric: tabular-nums;
	}
	.notes ul {
		margin: 0 0 0.5rem;
		padding-left: 1.2rem;
	}
	.print-head h1 {
		font-size: 16pt;
	}
</style>
