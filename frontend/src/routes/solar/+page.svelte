<script lang="ts">
	// «Де ставити СЕС»: одне питання — «скільки станцій поставимо за X млн грн?».
	// Бюджет і пріоритет → жадібний добір на клієнті. Тариф/ціни → перерахунок на сервері (/api/solar).
	// Енергонезалежність громади рахуємо ТАК САМО, як сторінка «Енергонезалежність» (/api/independence):
	// стартуємо з наявних станцій, а для будівель, де станція вже є, додаємо лише те, чого бракує.
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { untrack } from 'svelte';
	import { flip } from 'svelte/animate';
	import { Tween } from 'svelte/motion';
	import type { TransitionConfig } from 'svelte/transition';
	import { getJSON, qs, errMessage, ApiError, type SolarList, type SolarItem, type SolarDetail } from '#lib/api.ts';
	import type { IndependenceList, IndependenceItem } from '#lib/api-independence.ts';
	import { num } from '#lib/format.ts';
	import { catLabel } from '#lib/categories.ts';
	import { isReduced, cubicOut, DUR } from '#lib/motion.ts';
	import Status from '#lib/Status.svelte';
	import ForecastCard from '#lib/ForecastCard.svelte';
	import StatCard from '#lib/StatCard.svelte';
	import Disclosure from '#lib/Disclosure.svelte';
	import Reveal from '#lib/Reveal.svelte';
	import Term from '#lib/Term.svelte';
	import { simulate, plural, paybackWords } from '#lib/SolarScenario.svelte';

	type Excluded = { id: number; name: string; category_short: string; reason: string };
	type ListX = SolarList & {
		excluded?: Excluded[];
		params: SolarList['params'] & { capex_fixed_uah?: number; daytime_share?: number; base_year?: number };
	};
	/** Рядок програми: нова станція або доповнення до наявної */
	type Prog = SolarItem & {
		kw: number; // скільки кВт ставимо (для наявної СЕС — лише доповнення)
		cost: number;
		save: number;
		pb: number | null;
		gain: number; // +кВт·год/рік власного сонця
		existingKw: number | null;
		cover: number | null; // покриття потреби після встановлення, %
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
	let ind = $state<IndependenceList | null>(null);
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
		// untrack: інакше `data = d` у load() перезапускав би ефект → нескінченний цикл запитів
		const t = setTimeout(() => load(q), untrack(() => data) ? 350 : 0);
		return () => clearTimeout(t);
	});

	// Наявні станції й річна енергонезалежність громади — ті самі цифри, що на сторінці «Енергонезалежність»
	getJSON<IndependenceList>('/api/independence').then((x) => (ind = x)).catch(() => {});

	// Адреса сторінки зберігає сценарій (можна надіслати посилання) — без навігації й прокрутки
	$effect(() => {
		const p = new URLSearchParams();
		if (valid(tariff) && tariff !== DEF.tariff) p.set('tariff', String(tariff));
		if (valid(capex) && capex !== DEF.capex) p.set('capex', String(capex));
		if (valid(fixed, 0) && fixed !== DEF.fixed) p.set('fixed', String(fixed));
		if (valid(budgetM, 0) && budgetM !== DEF.budget) p.set('budget', String(budgetM));
		if (priority !== 'payback') p.set('priority', priority);
		const s = p.toString();
		const t = setTimeout(() => {
			const url = `${location.pathname}${s ? `?${s}` : ''}`;
			if (url === location.pathname + location.search) return;
			goto(url, { replace: true, shallow: true, reset: false, state: {} }).catch(() => {});
		}, 300);
		return () => clearTimeout(t);
	});

	function resetSettings() {
		tariff = DEF.tariff;
		capex = DEF.capex;
		fixed = DEF.fixed;
	}

	// ——— Дані програми ———
	function tier(it: SolarItem): number {
		if (it.category_short === HEALTH) return 0;
		if (EDU.includes(it.category_short)) return 1;
		return 2;
	}
	const indById = $derived(new Map<number, IndependenceItem>((ind?.items ?? []).map((e) => [e.id, e])));
	const P = $derived({
		tariff: data?.params.tariff_uah_kwh ?? DEF.tariff,
		capex: data?.params.capex_uah_per_kw ?? DEF.capex,
		fixed: data?.params.capex_fixed_uah ?? DEF.fixed
	});

	/** Перелік кандидатів + будівлі, де наявної станції вже досить */
	const prog = $derived.by(() => {
		const items: Prog[] = [];
		const covered: (SolarItem & { existingKw: number })[] = [];
		for (const it of data?.items ?? []) {
			const e = indById.get(it.id);
			if (e?.has_ses && e.ses_kw) {
				const add = e.potential_add_kw ?? 0;
				if (add <= 0) {
					covered.push({ ...it, existingKw: e.ses_kw });
					continue;
				}
				const gain = Math.max(0, (((e.potential_self_sufficiency_pct ?? 0) - (e.self_sufficiency_pct ?? 0)) / 100) * (e.elec_kwh_year ?? 0));
				const cost = P.fixed + add * P.capex;
				const save = gain * P.tariff;
				items.push({ ...it, kw: add, cost, save, pb: save > 0 ? cost / save : null, gain, existingKw: e.ses_kw, cover: e.potential_self_sufficiency_pct });
			} else {
				items.push({
					...it,
					kw: it.kw_recommended ?? 0,
					cost: it.capex_uah ?? Infinity,
					save: it.savings_uah_year ?? 0,
					pb: it.payback_years,
					gain: it.self_consumed_kwh_year ?? 0,
					existingKw: null,
					cover: it.coverage_pct
				});
			}
		}
		return { items, covered };
	});

	const pbOf = (it: Prog) => it.pb ?? Infinity;
	const ordered = $derived(
		[...prog.items].sort((a, b) =>
			priority === 'critical'
				? tier(a) - tier(b) || pbOf(a) - pbOf(b) || b.save - a.save
				: pbOf(a) - pbOf(b) || b.save - a.save
		)
	);
	const budget = $derived(Math.max(0, (budgetM ?? 0) * 1e6));
	const plan = $derived.by(() => {
		let left = budget;
		const picked: (Prog & { cum: number; fill: boolean })[] = [];
		const rest: Prog[] = [];
		let cum = 0;
		let skipped = false; // чи вже пропустили дорожчу станцію, що не вмістилася
		for (const it of ordered) {
			if (it.pb !== null && it.cost <= left) {
				left -= it.cost;
				cum += it.cost;
				picked.push({ ...it, cum, fill: skipped });
			} else {
				if (it.pb !== null) skipped = true;
				rest.push(it);
			}
		}
		return { picked, rest, left };
	});

	function stats(list: Prog[]) {
		const pbs = list.map((i) => i.pb).filter((v): v is number => v !== null).sort((a, b) => a - b);
		const med = pbs.length ? (pbs.length % 2 ? pbs[(pbs.length - 1) / 2] : (pbs[pbs.length / 2 - 1] + pbs[pbs.length / 2]) / 2) : null;
		return {
			n: list.length,
			kw: list.reduce((a, i) => a + i.kw, 0),
			cost: list.reduce((a, i) => a + (Number.isFinite(i.cost) ? i.cost : 0), 0),
			save: list.reduce((a, i) => a + i.save, 0),
			gain: list.reduce((a, i) => a + i.gain, 0),
			med,
			health: list.filter((i) => i.category_short === HEALTH).length,
			edu: list.filter((i) => EDU.includes(i.category_short)).length
		};
	}
	const all = $derived(stats(prog.items.filter((i) => i.pb !== null)));
	const sel = $derived(stats(plan.picked));
	const fills = $derived(plan.picked.filter((i) => i.fill).length);

	// ——— Енергонезалежність громади (узгоджено з /independence) ———
	const comm = $derived(ind?.community ?? null);
	/** Знаменник: уся електроенергія комунальних будівель за базовий рік */
	const denom = $derived(comm?.elec_kwh_year_2025 ?? (data?.items ?? []).reduce((a, i) => a + (i.elec_kwh_year ?? 0), 0));
	/** Зараз: частка від наявних станцій, % */
	const basePct = $derived(comm?.self_sufficiency_pct ?? 0);
	/** Уся програма, % — як «потенціал» на сторінці «Енергонезалежність» */
	const potPct = $derived(comm?.potential_self_sufficiency_pct ?? (denom > 0 ? basePct + (all.gain / denom) * 100 : 0));
	/** Поправка на округлення (частки будівель у API — з точністю 0,1 %), ≈ 1,00 */
	const kFix = $derived(denom > 0 && all.gain > 0 && comm ? ((potPct - basePct) / 100) * denom / all.gain : 1);
	const pctAt = (gainKwh: number) => (denom > 0 ? basePct + ((gainKwh * kFix) / denom) * 100 : basePct);
	const selPct = $derived(pctAt(sel.gain));

	const mln = (v: number, d = 1) => num(v / 1e6, d);
	const budgetMax = $derived(Math.max(5, Math.ceil(all.cost / 1e6)));
	const presets = $derived([2, 5, 10, 20].filter((v) => v < budgetMax));

	function money(v: number): string {
		if (!Number.isFinite(v)) return '—';
		return v >= 1e6 ? `${num(v / 1e6, 2)} млн грн` : `${num(Math.round(v / 1000))} тис. грн`;
	}
	const stations = (n: number) => plural(n, 'станція', 'станції', 'станцій');
	const buildings = (n: number) => plural(n, 'будівля', 'будівлі', 'будівель');

	// ——— Плавні значення для графіків ———
	const dur = isReduced() ? 0 : 520;
	const twCost = Tween.of(() => sel.cost, { duration: dur, easing: cubicOut });
	const twBudget = Tween.of(() => budget, { duration: dur, easing: cubicOut });
	const twPct = Tween.of(() => selPct, { duration: dur, easing: cubicOut });

	// ——— Крива «гроші → енергонезалежність» ———
	let curveW = $state(560);
	const CW = $derived(Math.round(Math.max(300, Math.min(560, curveW || 560))));
	const CH = $derived(CW < 480 ? 220 : 230);
	const CP = { l: 44, r: 16, t: 16, b: 34 };
	const curve = $derived.by(() => {
		const seq = [...plan.picked, ...plan.rest.filter((i) => i.pb !== null)];
		let x = 0;
		let g = 0;
		const pts = [{ x: 0, y: basePct }];
		for (const it of seq) {
			x += it.cost;
			g += it.gain;
			pts.push({ x, y: pctAt(g) });
		}
		const xMax = Math.max(x, budget, 1);
		const yTop = Math.max(5, Math.ceil(Math.max(potPct, pts[pts.length - 1].y) / 5) * 5);
		const X = (v: number) => CP.l + (Math.min(v, xMax) / xMax) * (CW - CP.l - CP.r);
		const Y = (pct: number) => CP.t + (1 - pct / yTop) * (CH - CP.t - CP.b);
		const d = pts.map((p, i) => `${i ? 'L' : 'M'}${X(p.x).toFixed(1)},${Y(p.y).toFixed(1)}`).join(' ');
		const xTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * xMax);
		const yTicks = [0, yTop / 2, yTop];
		return { d, X, Y, xMax, yTop, xTicks, yTicks };
	});

	// ——— Ілюстрація: окупність за різного розміру станції (на реальній будівлі-прикладі) ———
	const sizes = $derived.by(() => {
		if (!example || !data) return [];
		const kwRec = example.item.kw_recommended ?? 0;
		if (kwRec <= 0) return [];
		const p = { tariff: P.tariff, capex: P.capex, fixed: P.fixed, daytime: data.params.daytime_share ?? 0.6 };
		return [
			{ k: 1, label: 'Під споживання будівлі' },
			{ k: 2, label: 'Удвічі більша' },
			{ k: 3, label: 'Утричі більша' }
		].map(({ k, label }) => {
			const r = simulate(example!.monthly, kwRec, kwRec * k, p);
			return { k, label, ...r, surplusShare: r.gen > 0 ? r.surplus / r.gen : 0 };
		});
	});
	const sizeMax = $derived(Math.max(1, ...sizes.map((s) => s.payback ?? 0)));

	// ——— Анімація рядків переліку ———
	function rowIn(node: HTMLElement): TransitionConfig {
		if (isReduced()) return { duration: 0 };
		const h = node.offsetHeight;
		return {
			duration: DUR.slow,
			easing: cubicOut,
			css: (t, u) =>
				`overflow:hidden;height:${(Math.min(1, t * 1.6) * h).toFixed(1)}px;opacity:${t};transform:translateY(${(u * 10).toFixed(1)}px);background-color:rgba(245,165,36,${(0.28 * u).toFixed(3)})`
		};
	}
	function rowOut(node: HTMLElement): TransitionConfig {
		if (isReduced()) return { duration: 0 };
		const h = node.offsetHeight;
		return {
			duration: DUR.base,
			easing: cubicOut,
			css: (t) => `overflow:hidden;height:${(t * h).toFixed(1)}px;opacity:${t};padding-top:0;padding-bottom:0`
		};
	}
	const flipDur = isReduced() ? 0 : DUR.slow;

	// ——— Експорт (усі колонки — у CSV) ———
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
			[`Пріоритет`, priority === 'critical' ? 'спершу лікарні, школи й садки' : 'найшвидша окупність'],
			[`Тариф, грн/кВт·год`, P.tariff],
			[`Вартість монтажу, грн/кВт`, P.capex],
			[`Фіксована частина на об’єкт, грн`, P.fixed],
			[`Енергонезалежність громади зараз, %`, +basePct.toFixed(1)],
			[`Енергонезалежність після програми в межах бюджету, %`, +selPct.toFixed(1)],
			[],
			['№', 'ID', 'Будівля', 'Категорія', 'Наявна СЕС, кВт', 'Нова / додаткова потужність, кВт', 'Рекомендована сумарна потужність, кВт', 'Генерація рекомендованої станції, кВт·год/рік', 'Додаткове власне сонце, кВт·год/рік', 'Покриття потреби після встановлення, %', 'Вартість, грн', 'Наростаючим підсумком, грн', 'Економія, грн/рік', 'Окупність, років']
		];
		const rows = plan.picked.map((it, i) => [
			i + 1, it.id, it.name, it.category_short, it.existingKw ?? '', +it.kw.toFixed(1), it.kw_recommended, it.gen_kwh_year,
			Math.round(it.gain), it.cover, Math.round(it.cost), Math.round(it.cum), Math.round(it.save), it.pb !== null ? +it.pb.toFixed(1) : ''
		]);
		const tot = [['', '', 'Разом', `${sel.n} об’єктів`, '', +sel.kw.toFixed(1), '', '', Math.round(sel.gain), '', Math.round(sel.cost), '', Math.round(sel.save), sel.med !== null ? +sel.med.toFixed(1) : '']];
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
	const settingsChanged = $derived(tariff !== DEF.tariff || capex !== DEF.capex || fixed !== DEF.fixed);
	const today = new Date().toLocaleDateString('uk-UA');
	const budgetLabel = $derived(num(budgetM ?? 0, (budgetM ?? 0) % 1 ? 1 : 0));
</script>

<svelte:head><title>Де ставити СЕС · City Insight Map · Енергія</title></svelte:head>

<!-- Шапка для друку -->
<div class="print-only print-head">
	<h1>Перелік об’єктів для встановлення сонячних станцій</h1>
	<p>
		Бюджет програми: {mln(budget)} млн грн · пріоритет: {priority === 'critical' ? 'спершу лікарні, школи й садки' : 'найшвидша окупність'}
		· тариф {num(P.tariff, 2)} грн/кВт·год · монтаж {num(P.capex)} грн/кВт + {num(P.fixed)} грн на об’єкт · сформовано {today}
	</p>
</div>

<!-- ——— Головне питання ——— -->
<section class="ask no-print" aria-labelledby="ask-h">
	<p class="kicker"><span class="sundot" aria-hidden="true"></span> Де ставити сонячні станції</p>
	<h1 id="ask-h" class="ask-h">
		Скільки сонячних станцій поставимо за
		<span class="ask-sum"><span class="ask-num">{budgetLabel}</span> млн грн</span>?
	</h1>

	<div class="slider-wrap">
		<label for="s-budget-range" class="visually-hidden">Бюджет програми, млн грн</label>
		<!-- {#key}: коли зміниться максимум (дані завантажились, інші ціни), браузер інакше лишив би «обрізане» значення -->
		{#key budgetMax}<input
			id="s-budget-range"
			class="big-range"
			type="range"
			min="0"
			max={budgetMax}
			step="0.5"
			bind:value={budgetM}
			style:--fill="{Math.min(100, ((budgetM ?? 0) / budgetMax) * 100)}%"
			aria-valuetext="{num(budgetM, 1)} мільйонів гривень"
		/>{/key}
		<div class="range-scale" aria-hidden="true">
			<span>0</span>
			<span>≈ {mln(all.cost)} млн грн — уся програма</span>
		</div>
	</div>

	<div class="quick">
		<div class="chip-row quick-chips" role="group" aria-label="Швидкий вибір бюджету">
			{#each presets as v (v)}
				<button type="button" class="chip press" aria-pressed={budgetM === v} onclick={() => (budgetM = v)}>{v} млн</button>
			{/each}
			<button type="button" class="chip press" aria-pressed={budgetM === budgetMax} onclick={() => (budgetM = budgetMax)}>Уся програма</button>
		</div>
		<label class="exact">
			<span>Точна сума</span>
			<input type="number" min="0" step="0.5" inputmode="decimal" bind:value={budgetM} aria-label="Бюджет програми, млн грн (точна сума)" />
			<span>млн грн</span>
		</label>
	</div>

	<fieldset class="prio">
		<legend>Кого ставимо першими?</legend>
		<div class="prio-opts">
			<label class="opt" class:on={priority === 'payback'}>
				<input type="radio" name="prio" value="payback" bind:group={priority} />
				<span class="opt-mark" aria-hidden="true"></span>
				<span class="opt-txt">
					<strong>Найшвидша окупність</strong>
					<small>Спершу там, де гроші повернуться найшвидше.</small>
				</span>
			</label>
			<label class="opt" class:on={priority === 'critical'}>
				<input type="radio" name="prio" value="critical" bind:group={priority} />
				<span class="opt-mark" aria-hidden="true"></span>
				<span class="opt-txt">
					<strong>Спершу лікарні й школи</strong>
					<small>Критичні заклади першими, далі — усі інші.</small>
				</span>
			</label>
		</div>
	</fieldset>

	<Disclosure summary="Налаштування розрахунку" hint="тариф {num(P.tariff, 2)} грн · монтаж {num(P.capex)} грн/кВт{settingsChanged ? ' · змінено' : ''}">
		<div class="settings">
			<div class="field">
				<label for="s-tariff">Тариф, грн за 1 кВт·год</label>
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
			<button type="button" class="btn btn-secondary" onclick={resetSettings} disabled={!settingsChanged}>Скинути до типових</button>
		</div>
		<p class="muted small sc-status" aria-live="polite">
			{#if refreshing}Перераховуємо…{:else if data}Розрахунок оновлено для цих цін.{/if}
		</p>
	</Disclosure>
</section>

<Status {loading} {error} retry={() => load(query)} />

{#if notReady && !loading}
	<div class="notice notice-warn" role="status">
		<p><strong>Розрахунок ще не готовий.</strong> Модуль оцінки сонячних станцій зараз доробляється. Спробуйте трохи пізніше.</p>
	</div>
{/if}

{#if data && !loading}
	<!-- ——— Відповідь: три картки ——— -->
	<section class="answer" aria-labelledby="ans-h" class:dim={refreshing}>
		<h2 id="ans-h" class="visually-hidden">Що дасть бюджет {mln(budget)} млн грн</h2>
		<div class="stats">
			<Reveal delay={0} class="stat-cell">
				<StatCard
					label="Скільки закладів"
					value={sel.n}
					unit={buildings(sel.n)}
					icon="building"
					hint={sel.n
						? `${num(sel.kw)} кВт панелей. Серед них ${sel.health} ${plural(sel.health, 'медзаклад', 'медзаклади', 'медзакладів')} і ${sel.edu} ${plural(sel.edu, 'заклад освіти', 'заклади освіти', 'закладів освіти')}.`
						: 'Бюджету поки не вистачає на жодну станцію.'}
				/>
			</Reveal>
			<Reveal delay={80} class="stat-cell">
				<StatCard
					label="Енергонезалежність громади"
					value={selPct}
					decimals={1}
					unit="%"
					icon="sun"
					demo
					tone={sel.n ? 'good' : 'neutral'}
					toneLabel="зросте"
					hint="Зараз {num(basePct, 1)} %. Уся програма дасть {num(potPct, 1)} %."
				>
					<span class="ibar" aria-hidden="true">
						<span class="ib-pot" style:width="{(potPct / Math.max(potPct, 1)) * 100}%"></span>
						<span class="ib-sel" style:width="{(twPct.current / Math.max(potPct, 1)) * 100}%"></span>
						<span class="ib-base" style:width="{(basePct / Math.max(potPct, 1)) * 100}%"></span>
					</span>
					<span class="ilegend" aria-hidden="true">
						<span><i class="sw base"></i>вже є</span>
						<span><i class="sw sel"></i>+ цей бюджет</span>
						<span><i class="sw pot"></i>уся програма</span>
					</span>
				</StatCard>
			</Reveal>
			<Reveal delay={160} class="stat-cell">
				<StatCard
					label="Економія на рік"
					value={sel.save / 1e6}
					decimals={2}
					unit="млн грн"
					icon="wallet"
					hint={sel.med !== null ? `Менше платимо за світло щороку. Типова станція ${paybackWords(sel.med)}.` : 'Менше платимо за світло щороку.'}
				/>
			</Reveal>
		</div>
	</section>

	<!-- ——— Перелік ——— -->
	<Reveal>
		<section class="card list" aria-labelledby="list-h">
			<div class="list-head">
				<div>
					<h2 id="list-h">Що встигнемо за {mln(budget)} млн грн</h2>
					<p class="muted small">
						{priority === 'critical' ? 'Спершу лікарні, потім школи й садки, далі решта.' : 'Від найшвидшої окупності.'}
						Натисніть на будівлю, щоб побачити розрахунок.
					</p>
				</div>
				<div class="list-actions no-print">
					<button type="button" class="btn press" onclick={exportCsv} disabled={!plan.picked.length}>Завантажити CSV</button>
					<button type="button" class="btn btn-secondary press" onclick={() => window.print()}><span class="hide-phone">Друк / PDF</span><span class="only-phone">Зберегти PDF</span></button>
				</div>
			</div>

			<div class="used">
				<div class="used-txt small">
					<span>Використано <strong>{mln(twCost.current, 2)}</strong> з {mln(budget, budget % 1e6 ? 1 : 0)} млн грн</span>
					{#if plan.left >= 10000 && plan.picked.length}<span class="muted">залишок {mln(plan.left, 2)} млн — на наступну станцію не вистачає</span>{/if}
				</div>
				<div class="used-bar" aria-hidden="true">
					<span style:width="{budget > 0 ? Math.min(100, (twCost.current / budget) * 100) : 0}%"></span>
				</div>
			</div>

			{#if plan.picked.length}
				<div class="rows-head" aria-hidden="true">
					<span>№</span><span>Будівля</span><span class="r">Станція</span><span class="r">Вартість</span><span>Окупність</span>
				</div>
				<ol class="rows" aria-label="Перелік будівель у межах бюджету">
					{#each plan.picked as it, i (it.id)}
						<li class="row" class:crit={tier(it) === 0} animate:flip={{ duration: flipDur, easing: cubicOut }} in:rowIn out:rowOut>
							<span class="r-no" aria-hidden="true">{i + 1}</span>
							<span class="r-name">
								<a href="/solar/{it.id}{detailQs}" title={it.name}>{it.name}</a>
								<span class="r-type">
									{catLabel(it.category_short)}
									{#if tier(it) === 0}<span class="tag crit"><span aria-hidden="true">✚</span> критичний</span>{/if}
									{#if it.existingKw}<span class="tag ext">доповнення до наявної {num(it.existingKw, 1)} кВт</span>{/if}
									{#if it.fill}<span class="tag fill" title="Наступна за чергою станція не вмістилася в залишок бюджету, тому добрали цю, меншу">у залишок бюджету</span>{/if}
								</span>
							</span>
							<span class="r-kw r"><span class="lbl">Станція: </span><b>{it.existingKw ? '+' : ''}{num(it.kw, it.kw < 10 ? 1 : 0)}</b> кВт</span>
							<span class="r-cost r"><span class="lbl">Вартість: </span>{money(it.cost)}</span>
							<span class="r-pb"><span class="pb-ico" aria-hidden="true"></span>{paybackWords(it.pb)}</span>
						</li>
					{/each}
				</ol>
				{#if fills}
					<p class="small muted fill-note">
						<span class="tag fill">у залишок бюджету</span> — наступна за чергою станція не вміщалася в залишок, тому добрали меншу, що вмістилася. Порядок черги від цього не змінюється.
					</p>
				{/if}
				<p class="total">
					<strong>Разом: {num(sel.n)} {buildings(sel.n)}</strong> · {num(sel.kw)} кВт · {money(sel.cost)} · економія {money(sel.save)} на рік
				</p>
			{:else}
				<p class="notice notice-warn">
					Бюджету не вистачає на жодну станцію. Найдешевша коштує ≈ {money(Math.min(...prog.items.map((i) => i.cost)))}.
				</p>
			{/if}

			{#if plan.rest.length}
				<div class="no-print">
					<Disclosure summary="Наступні в черзі — не вмістилися в бюджет" hint="{num(plan.rest.length)} {buildings(plan.rest.length)}">
						<ol class="rows rest" aria-label="Будівлі, що не вмістилися в бюджет">
							{#each plan.rest as it (it.id)}
								<li class="row">
									<span class="r-no" aria-hidden="true"></span>
									<span class="r-name">
										<a href="/solar/{it.id}{detailQs}" title={it.name}>{it.name}</a>
										<span class="r-type">{catLabel(it.category_short)}{#if tier(it) === 0}<span class="tag crit"><span aria-hidden="true">✚</span> критичний</span>{/if}</span>
									</span>
									<span class="r-kw r"><span class="lbl">Станція: </span><b>{it.existingKw ? '+' : ''}{num(it.kw, it.kw < 10 ? 1 : 0)}</b> кВт</span>
									<span class="r-cost r"><span class="lbl">Вартість: </span>{money(it.cost)}</span>
									<span class="r-pb">{paybackWords(it.pb)}</span>
								</li>
							{/each}
						</ol>
					</Disclosure>
				</div>
			{/if}
		</section>
	</Reveal>

	<!-- ——— Графік і прогноз ——— -->
	<div class="duo no-print">
		<Reveal class="duo-main">
			<figure class="card curve">
				<figcaption>
					<h2>Як росте енергонезалежність із кожним мільйоном</h2>
					<p class="muted small">Будівлі додаються в тому самому порядку, що й у переліку. Пунктир — ваш бюджет.</p>
				</figcaption>
				<div class="cv-box" bind:clientWidth={curveW}>
				<svg
					viewBox="0 0 {CW} {CH}"
					role="img"
					aria-label="Частка електроенергії комунальних будівель із власного сонця: зараз {num(basePct, 1)} %, за {mln(budget)} млн грн — {num(selPct, 1)} %, за всю програму {mln(all.cost)} млн грн — {num(potPct, 1)} %."
				>
					{#each curve.yTicks as t (t)}
						<line x1={CP.l} x2={CW - CP.r} y1={curve.Y(t)} y2={curve.Y(t)} class="grid" />
						<text x={CP.l - 6} y={curve.Y(t)} class="ax" text-anchor="end" dominant-baseline="middle">{num(t, t % 1 ? 1 : 0)} %</text>
					{/each}
					{#each curve.xTicks as t, i (i)}
						<text x={curve.X(t)} y={CH - CP.b + 16} class="ax" text-anchor={i === 0 ? 'start' : i === 4 ? 'end' : 'middle'}>{mln(t, 0)}</text>
					{/each}
					<text x={CW - CP.r} y={CH - 3} class="ax" text-anchor="end">млн грн</text>
					<rect x={CP.l} y={curve.Y(basePct)} width={CW - CP.l - CP.r} height={Math.max(0, curve.Y(0) - curve.Y(basePct))} class="basezone" />
					<text x={CW - CP.r - 4} y={curve.Y(basePct) - 5} class="baselabel" text-anchor="end">вже є: {num(basePct, 1)} %</text>
					<rect x={CP.l} y={CP.t} width={Math.max(0, curve.X(twCost.current) - CP.l)} height={CH - CP.t - CP.b} class="selzone" />
					<path d={curve.d} class="cline" pathLength="1" />
					<line x1={curve.X(twBudget.current)} x2={curve.X(twBudget.current)} y1={CP.t} y2={CH - CP.b} class="bline" />
					<text x={Math.min(curve.X(twBudget.current) + 6, CW - 152)} y={CP.t + 12} class="blabel">бюджет {mln(budget)} млн → {num(selPct, 1)} %</text>
					<circle cx={curve.X(twCost.current)} cy={curve.Y(twPct.current)} r="6" class="bdot" />
				</svg>
				</div>
			</figure>
		</Reveal>
		<Reveal class="duo-side" delay={100}>
			<ForecastCard kw={null} />
		</Reveal>
	</div>

	<!-- ——— Чому станції не більші ——— -->
	<Reveal>
		<section class="card why no-print" aria-labelledby="why-h">
			<h2 id="why-h">Чому станції не більші?</h2>
			<p class="why-lead">
				Школа чи лікарня <strong>не може вигідно продати зайву електроенергію</strong> в мережу. Тому ми ставимо рівно стільки
				панелей, скільки будівля сама спожиє вдень. Більша станція коштує дорожче, а заощаджує майже стільки ж.
			</p>
			{#if sizes.length}
				<div class="sizes" role="img" aria-label="Окупність на прикладі однієї будівлі: {sizes.map((s) => `${s.label} — ${s.payback !== null ? num(s.payback, 1) : '—'} року`).join('; ')}">
					{#each sizes as s (s.k)}
						<div class="srow" class:best={s.k === 1}>
							<span class="sl">{s.label}<small class="muted sl-kw">{num(s.kw, 0)} кВт{#if s.k === 1} · <span class="best-tag">✓ наш вибір</span>{/if}</small></span>
							<span class="sbar"><i style:--w="{((s.payback ?? 0) / sizeMax) * 100}%"></i></span>
							<span class="sv"><strong>{paybackWords(s.payback)}</strong>{#if s.surplusShare > 0.01}<br /><small class="muted">{num(s.surplusShare * 100)} % енергії пропадає</small>{/if}</span>
						</div>
					{/each}
					<p class="small muted">Приклад: {example?.item.name.length && example.item.name.length > 80 ? example.item.name.slice(0, 78) + '…' : example?.item.name}. Коротша смуга — швидше окупиться.</p>
				</div>
			{/if}
		</section>
	</Reveal>

	<!-- ——— Методика ——— -->
	<section class="card notes" aria-labelledby="notes-h">
		<h2 id="notes-h">Як ми рахуємо</h2>
		<p class="muted small">Це аналітична оцінка для планування, а не проєкт станцій.</p>
		<Disclosure summary="Як рахуємо енергонезалежність громади">
			<ul>
				<li>
					<Term key="енергонезалежність">Енергонезалежність</Term> громади тут — яку частку всієї електроенергії
					{comm ? num((comm as { sites_with_data?: number }).sites_with_data ?? comm.sites) : ''} комунальних будівель за рік дає власне сонце
					{#if denom}(усього {num(denom / 1e6, 2)} млн кВт·год за 2025 рік){/if}.
				</li>
				<li>
					<strong>Стартуємо не з нуля:</strong> {comm ? num(comm.ses_sites) : ''} будівель уже мають станції
					{comm ? `(${num(comm.ses_kw_total)} кВт)` : ''} — це дає {num(basePct, 1)} %. Наявні станції — демонстраційні дані.
				</li>
				<li>
					Якщо станція на будівлі вже є, ставимо лише те, чого бракує до рекомендованої потужності, і рахуємо
					вартість саме цього доповнення.
					{#if prog.covered.length}{num(prog.covered.length)} {buildings(prog.covered.length)} уже мають достатню станцію, тому їх у переліку немає.{/if}
				</li>
				<li>
					Уся програма ({num(all.n)} {buildings(all.n)}, ≈ {mln(all.cost)} млн грн) піднімає частку до {num(potPct, 1)} % —
					та сама цифра, що й на сторінці «Енергонезалежність».
				</li>
			</ul>
		</Disclosure>
		{#if data.params.source_notes?.length}
			<Disclosure summary="Припущення та джерела даних" hint="{data.params.source_notes.length} пунктів">
				<ul>
					{#each data.params.source_notes as n, i (i)}<li>{n}</li>{/each}
				</ul>
			</Disclosure>
		{/if}
		{#if data.excluded?.length}
			<Disclosure summary="Будівлі без розрахунку — чому" hint="{num(data.excluded.length)} {buildings(data.excluded.length)}">
				<p class="small">
					Як складаються {num(data.items.length + data.excluded.length)} {buildings(data.items.length + data.excluded.length)}:
					{num(all.n)} — у переліку програми{#if prog.covered.length}, {num(prog.covered.length)} уже мають достатню станцію (доповнення не потрібне){/if}{#if prog.items.length - all.n > 0}, {num(prog.items.length - all.n)} — станція не окупиться{/if},
					{num(data.excluded.length)} — без розрахунку (причини нижче).
				</p>
				<div class="table-wrap">
					<table>
						<thead><tr><th scope="col">Будівля</th><th scope="col">Категорія</th><th scope="col">Причина</th></tr></thead>
						<tbody>
							{#each data.excluded as e (e.id)}
								<tr><td class="name">{e.name}</td><td>{catLabel(e.category_short)}</td><td class="small">{e.reason}</td></tr>
							{/each}
						</tbody>
					</table>
				</div>
			</Disclosure>
		{/if}
	</section>
{/if}

<style>
	.print-only {
		display: none;
	}
	@media print {
		.print-only {
			display: block;
		}
		.print-head h1 {
			font-size: 16pt;
		}
	}

	/* ——— Питання ——— */
	.ask {
		background:
			radial-gradient(120% 140% at 100% 0%, var(--sun-soft) 0%, transparent 55%),
			var(--surface);
		border: 1px solid var(--line);
		border-radius: var(--radius-lg);
		box-shadow: var(--shadow-md);
		padding: clamp(1.1rem, 3vw, 2rem) clamp(1rem, 3vw, 2.25rem) 0.5rem;
		margin-bottom: 1.25rem;
	}
	.kicker {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin: 0 0 0.5rem;
		font-weight: 700;
		font-size: 0.9rem;
		letter-spacing: 0.02em;
		color: var(--sun-ink);
		text-transform: uppercase;
	}
	.sundot {
		width: 12px;
		height: 12px;
		border-radius: 50%;
		background: var(--sun);
		box-shadow: 0 0 0 4px var(--sun-soft);
		animation: pulse 2.8s ease-in-out 3;
	}
	@keyframes pulse {
		50% {
			box-shadow: 0 0 0 8px rgba(245, 165, 36, 0.12);
		}
	}
	.ask-h {
		font-size: clamp(1.55rem, 3.2vw, 2.6rem);
		line-height: 1.18;
		letter-spacing: -0.01em;
		margin: 0 0 1.25rem;
		max-width: 30ch;
		text-wrap: balance;
	}
	.ask-sum {
		white-space: nowrap;
		color: var(--sun-ink);
	}
	.ask-num {
		display: inline-block;
		min-width: 1.6ch;
		padding: 0 0.3rem;
		border-radius: 10px;
		background: var(--sun-soft);
		box-shadow: inset 0 -3px 0 var(--sun);
		font-variant-numeric: tabular-nums;
		text-align: center;
	}
	.slider-wrap {
		max-width: 920px;
	}
	.big-range {
		-webkit-appearance: none;
		appearance: none;
		width: 100%;
		height: 44px;
		background: transparent;
		cursor: pointer;
		margin: 0;
	}
	.big-range::-webkit-slider-runnable-track {
		height: 12px;
		border-radius: 999px;
		background: linear-gradient(90deg, var(--sun-strong) 0 var(--fill), #e7eaef var(--fill) 100%);
	}
	.big-range::-moz-range-track {
		height: 12px;
		border-radius: 999px;
		background: #e7eaef;
	}
	.big-range::-moz-range-progress {
		height: 12px;
		border-radius: 999px;
		background: var(--sun-strong);
	}
	.big-range::-webkit-slider-thumb {
		-webkit-appearance: none;
		width: 32px;
		height: 32px;
		margin-top: -10px;
		border-radius: 50%;
		background: #fff;
		border: 4px solid var(--sun-strong);
		box-shadow: 0 2px 8px rgba(138, 79, 0, 0.3);
		transition: transform var(--dur-fast, 150ms) var(--ease-out, ease);
	}
	.big-range::-moz-range-thumb {
		width: 26px;
		height: 26px;
		border-radius: 50%;
		background: #fff;
		border: 4px solid var(--sun-strong);
		box-shadow: 0 2px 8px rgba(138, 79, 0, 0.3);
	}
	.big-range:hover::-webkit-slider-thumb,
	.big-range:active::-webkit-slider-thumb {
		transform: scale(1.12);
	}
	.big-range:focus-visible {
		outline: 3px solid var(--focus);
		outline-offset: 4px;
		border-radius: 8px;
	}
	.range-scale {
		display: flex;
		justify-content: space-between;
		font-size: 0.8125rem;
		color: var(--muted);
		margin-top: -2px;
	}
	.quick {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
		margin: 0.9rem 0 1.25rem;
	}
	.chip {
		font: inherit;
		font-size: 0.9rem;
		font-weight: 600;
		padding: 0.4rem 0.85rem;
		min-height: 36px;
		border-radius: 999px;
		border: 1px solid var(--line-strong);
		background: #fff;
		color: var(--text);
		cursor: pointer;
		transition:
			background var(--dur-fast, 150ms),
			border-color var(--dur-fast, 150ms);
	}
	.chip:hover {
		border-color: var(--sun-strong);
	}
	.chip[aria-pressed='true'] {
		background: var(--sun-soft);
		border-color: var(--sun-strong);
		color: var(--sun-ink);
		box-shadow: inset 0 0 0 1px var(--sun-strong);
	}
	.exact {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		margin-left: auto;
		font-size: 0.875rem;
		color: var(--muted);
	}
	.exact input {
		width: 5.5rem;
	}
	@media (max-width: 640px) {
		.exact {
			margin-left: 0;
		}
	}

	fieldset.prio {
		border: 0;
		padding: 0;
		margin: 0 0 0.25rem;
		min-width: 0;
	}
	.prio legend {
		font-weight: 700;
		font-size: 1rem;
		padding: 0;
		margin-bottom: 0.5rem;
	}
	.prio-opts {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.6rem;
		max-width: 920px;
	}
	@media (max-width: 640px) {
		.prio-opts {
			grid-template-columns: 1fr;
		}
	}
	.opt {
		position: relative;
		display: flex;
		align-items: flex-start;
		gap: 0.7rem;
		padding: 0.75rem 0.9rem;
		border: 1.5px solid var(--line);
		border-radius: var(--radius);
		background: #fff;
		cursor: pointer;
		margin: 0;
		transition:
			border-color var(--dur-fast, 150ms),
			background var(--dur-fast, 150ms),
			box-shadow var(--dur-base, 240ms);
	}
	.opt:hover {
		border-color: var(--line-strong);
	}
	.opt.on {
		border-color: var(--navy-3);
		background: var(--accent-soft);
		box-shadow: 0 0 0 1px var(--navy-3);
	}
	.opt input {
		position: absolute;
		opacity: 0;
		width: 1px;
		height: 1px;
	}
	.opt:has(input:focus-visible) {
		outline: 3px solid var(--focus);
		outline-offset: 2px;
	}
	.opt-mark {
		flex: none;
		width: 20px;
		height: 20px;
		margin-top: 2px;
		border-radius: 50%;
		border: 2px solid var(--line-strong);
		background: #fff;
		display: grid;
		place-items: center;
		transition: border-color var(--dur-fast, 150ms);
	}
	.opt-mark::after {
		content: '';
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background: var(--navy-3);
		transform: scale(0);
		transition: transform var(--dur-base, 240ms) var(--ease-spring, ease);
	}
	.opt.on .opt-mark {
		border-color: var(--navy-3);
	}
	.opt.on .opt-mark::after {
		transform: scale(1);
	}
	.opt-txt {
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
	}
	.opt-txt small {
		color: var(--muted);
		font-size: 0.875rem;
	}
	.settings {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem 1.25rem;
		align-items: flex-end;
	}
	.settings input {
		width: 10rem;
	}
	.sc-status {
		min-height: 1.3em;
		margin: 0.5rem 0 0;
	}

	/* ——— Відповідь ——— */
	.answer {
		margin-bottom: 1.25rem;
		transition: opacity var(--dur-base, 240ms);
	}
	.answer.dim {
		opacity: 0.6;
	}
	.stats {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 1rem;
	}
	.stats :global(.stat-cell) {
		display: flex;
		flex-direction: column;
	}
	.stats :global(.stat-cell > *) {
		flex: 1;
	}
	@media (max-width: 860px) {
		.stats {
			gap: 0.6rem;
		}
	}
	@media (max-width: 640px) {
		.stats {
			grid-template-columns: 1fr;
		}
	}
	.ibar {
		position: relative;
		display: block;
		height: 12px;
		border-radius: 999px;
		background: var(--neutral-soft);
		overflow: hidden;
		margin-top: 0.15rem;
	}
	.ibar > span {
		position: absolute;
		inset: 0 auto 0 0;
		border-radius: 999px;
	}
	.ib-pot {
		background: #bfe3c9;
	}
	.ib-sel {
		background: var(--surplus);
	}
	.ib-base {
		background: repeating-linear-gradient(135deg, var(--navy-3) 0 3px, #3d6aa0 3px 6px);
	}
	.ilegend {
		display: flex;
		flex-wrap: wrap;
		gap: 0.2rem 0.8rem;
		margin-top: 0.4rem;
		font-size: 0.78rem;
		color: var(--muted);
	}
	.ilegend span {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
	}
	.sw {
		display: inline-block;
		width: 11px;
		height: 11px;
		border-radius: 3px;
	}
	.sw.base {
		background: repeating-linear-gradient(135deg, var(--navy-3) 0 2px, #3d6aa0 2px 4px);
	}
	.sw.sel {
		background: var(--surplus);
	}
	.sw.pot {
		background: #bfe3c9;
	}

	/* ——— Перелік ——— */
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
	}
	.list-actions {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.used {
		margin-bottom: 0.9rem;
	}
	.used-txt {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		gap: 0.25rem 1rem;
		margin-bottom: 0.35rem;
		font-variant-numeric: tabular-nums;
	}
	.used-bar {
		height: 8px;
		border-radius: 999px;
		background: var(--neutral-soft);
		overflow: hidden;
	}
	.used-bar span {
		display: block;
		height: 100%;
		border-radius: 999px;
		background: linear-gradient(90deg, var(--sun), var(--sun-strong));
	}
	.rows-head,
	.row {
		display: grid;
		grid-template-columns: 2rem minmax(0, 1fr) 6.5rem 8.5rem 11.5rem;
		gap: 0.75rem;
		align-items: center;
	}
	.rows-head {
		padding: 0 0.75rem 0.4rem;
		font-size: 0.8125rem;
		font-weight: 700;
		color: var(--muted);
		border-bottom: 1px solid var(--line);
	}
	.r {
		text-align: right;
	}
	.rows {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.row {
		padding: 0.65rem 0.75rem;
		border-bottom: 1px solid #edf0f4;
		border-radius: 8px;
		background-color: transparent;
	}
	.row:hover {
		background-color: #f7f9fb;
	}
	.row.crit {
		box-shadow: inset 3px 0 0 var(--bad);
	}
	.r-no {
		font-weight: 700;
		color: var(--muted);
		font-variant-numeric: tabular-nums;
	}
	.r-name {
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
		min-width: 0;
	}
	.r-name a {
		font-weight: 600;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
	.r-type {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		align-items: center;
		font-size: 0.8125rem;
		color: var(--muted);
	}
	.r-kw,
	.r-cost {
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
	.r-kw b {
		font-size: 1.05rem;
	}
	.r-pb {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-weight: 600;
		color: var(--surplus-ink);
	}
	.pb-ico {
		flex: none;
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--surplus);
	}
	.lbl {
		display: none;
	}
	.tag {
		font-size: 0.75rem;
		font-weight: 700;
		padding: 0 0.4rem;
		border-radius: 4px;
		white-space: nowrap;
	}
	.tag.crit {
		background: var(--bad-soft);
		color: var(--bad);
		border: 1px solid #f0c4c2;
	}
	.tag.fill {
		background: var(--sun-soft);
		color: var(--sun-ink);
		border: 1px solid #f0d7a6;
	}
	.fill-note {
		margin: 0.6rem 0 0;
	}
	.tag.ext {
		background: var(--accent-soft);
		color: var(--navy-3);
		border: 1px solid #c4d6ea;
	}
	.total {
		margin: 0.75rem 0 0;
		padding: 0.7rem 0.75rem;
		border-radius: var(--radius);
		background: #f7f9fb;
		font-variant-numeric: tabular-nums;
	}
	.rest .row {
		padding-top: 0.5rem;
		padding-bottom: 0.5rem;
	}
	.rest .r-pb {
		color: var(--muted);
		font-weight: 500;
	}
	@media (max-width: 900px) {
		.rows-head {
			display: none;
		}
		.row {
			grid-template-columns: 1.6rem minmax(0, 1fr) auto;
			grid-template-areas:
				'no name name'
				'. kw cost'
				'. pb pb';
			gap: 0.3rem 0.75rem;
		}
		.r-no {
			grid-area: no;
		}
		.r-name {
			grid-area: name;
		}
		.r-kw {
			grid-area: kw;
			text-align: left;
		}
		.r-cost {
			grid-area: cost;
		}
		.r-pb {
			grid-area: pb;
		}
		.lbl {
			display: inline;
			margin-right: 0.3em;
			color: var(--muted);
			font-size: 0.8125rem;
		}
	}
	@media print {
		.row {
			break-inside: avoid;
		}
		.used {
			display: none;
		}
	}

	/* ——— Графік + прогноз ——— */
	.duo {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(300px, 400px);
		gap: 1.25rem;
		align-items: start;
		margin-bottom: 1.25rem;
	}
	.duo :global(.card) {
		margin: 0;
	}
	@media (max-width: 1000px) {
		.duo {
			grid-template-columns: 1fr;
		}
	}
	.curve {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.curve figcaption h2 {
		margin-bottom: 0.15rem;
	}
	.curve figcaption p {
		margin: 0;
	}
	.cv-box {
		width: 100%;
		min-width: 0;
	}
	.curve svg {
		display: block;
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
	.basezone {
		fill: rgba(31, 79, 132, 0.1);
	}
	.baselabel {
		font-size: 11px;
		font-weight: 700;
		fill: var(--navy-3);
	}
	.selzone {
		fill: var(--surplus-soft);
	}
	.cline {
		fill: none;
		stroke: var(--surplus);
		stroke-width: 3;
		stroke-linejoin: round;
		stroke-dasharray: 1;
		stroke-dashoffset: 0;
	}
	@media (prefers-reduced-motion: no-preference) {
		.cline {
			animation: draw 0.6s var(--ease-out, ease-out) both 0.1s;
		}
	}
	@keyframes draw {
		from {
			stroke-dashoffset: 1;
		}
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

	/* ——— Чому не більші ——— */
	.why-lead {
		max-width: 75ch;
	}
	.sizes {
		margin-top: 0.75rem;
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		max-width: 820px;
	}
	.srow {
		display: grid;
		grid-template-columns: 13rem minmax(0, 1fr) 13rem;
		gap: 0.75rem;
		align-items: center;
		padding: 0.45rem 0.6rem;
		border-radius: 8px;
		line-height: 1.25;
	}
	@media (max-width: 700px) {
		.srow {
			grid-template-columns: 1fr;
			gap: 0.3rem;
		}
	}
	.srow.best {
		background: var(--ok-soft);
		outline: 1px solid #bfe1c9;
	}
	.best-tag {
		font-size: 0.75rem;
		color: var(--ok);
		font-weight: 700;
	}
	.sl {
		font-size: 0.9rem;
		font-weight: 600;
		display: flex;
		flex-direction: column;
	}
	.sl-kw {
		font-weight: 500;
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
		width: var(--w);
		background: repeating-linear-gradient(135deg, var(--sol-surplus) 0 6px, #d99a2b 6px 9px);
		transform-origin: left;
	}
	.srow.best .sbar i {
		background: var(--sol-self);
	}
	@media (prefers-reduced-motion: no-preference) {
		.sbar i {
			animation: grow 0.5s var(--ease-out, ease-out) both 0.15s;
		}
	}
	@keyframes grow {
		from {
			transform: scaleX(0);
		}
	}
	.sv {
		font-size: 0.9rem;
	}
	.notes ul {
		margin: 0;
		padding-left: 1.2rem;
	}
	.notes li {
		margin-bottom: 0.35rem;
		max-width: 90ch;
	}

	.quick-chips {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
	}

	/* ---------- Телефон (≤640): питання + бюджет — головний екран ---------- */
	@media (max-width: 640px) {
		.ask {
			padding: 1rem 1rem 0.25rem;
			border-radius: 14px;
			box-shadow: var(--shadow);
			margin-bottom: 0.875rem;
		}
		.kicker {
			font-size: 0.75rem;
			margin-bottom: 0.35rem;
		}
		.ask-h {
			font-size: 1.4rem;
			line-height: 1.22;
			margin-bottom: 0.6rem;
		}
		.ask-sum {
			display: inline-block;
		}
		.big-range {
			height: 52px;
			touch-action: pan-y;
		}
		.big-range::-webkit-slider-runnable-track {
			height: 10px;
		}
		.big-range::-webkit-slider-thumb {
			width: 36px;
			height: 36px;
			margin-top: -13px;
			border-width: 5px;
		}
		.big-range::-moz-range-thumb {
			width: 30px;
			height: 30px;
		}
		.range-scale {
			font-size: 0.75rem;
		}
		.quick {
			display: block;
			margin: 0.6rem 0 1rem;
		}
		.quick-chips {
			flex-wrap: nowrap;
			margin-bottom: 0.6rem;
		}
		.chip {
			min-height: 40px;
			padding: 0.4rem 0.95rem;
		}
		.exact {
			margin-left: 0;
			justify-content: flex-start;
		}
		.exact input {
			width: 6.5rem;
		}
		/* Пріоритет — сегментований перемикач */
		.prio legend {
			font-size: 0.9rem;
			margin-bottom: 0.4rem;
		}
		.prio-opts {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 0;
			padding: 3px;
			border-radius: 12px;
			background: var(--bg-2);
		}
		.opt {
			justify-content: center;
			align-items: center;
			min-height: 48px;
			padding: 0.4rem 0.5rem;
			border: 0;
			border-radius: 10px;
			background: transparent;
			text-align: center;
		}
		.opt:hover {
			border-color: transparent;
		}
		.opt.on {
			background: var(--surface);
			box-shadow: 0 1px 3px rgba(15, 35, 65, 0.16);
		}
		.opt-mark,
		.opt-txt small {
			display: none;
		}
		.opt-txt strong {
			font-size: 0.875rem;
			line-height: 1.2;
		}
		.opt.on .opt-txt strong {
			color: var(--navy);
		}
		.settings {
			display: grid;
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 0.6rem;
			align-items: end;
		}
		.settings input {
			width: 100%;
		}
		.settings .btn {
			grid-column: 1 / -1;
		}

		/* Відповідь: енергонезалежність на всю ширину, далі дві картки поруч */
		.answer {
			margin-bottom: 0.875rem;
		}
		.stats {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 0.625rem;
		}
		.stats > :global(.stat-cell:nth-child(2)) {
			grid-column: 1 / -1;
			order: -1;
		}

		/* Перелік — компактні рядки */
		.list-head h2 {
			font-size: 1.1rem;
		}
		.list-actions {
			display: grid;
			grid-template-columns: repeat(2, minmax(0, 1fr));
			width: 100%;
		}
		.list-actions .btn {
			justify-content: center;
			padding-inline: 0.5rem;
			font-size: 0.9rem;
		}
		.row {
			grid-template-columns: 1.4rem minmax(0, 1fr) auto;
			grid-template-areas:
				'no name name'
				'. kw cost'
				'. pb pb';
			gap: 0.2rem 0.5rem;
			padding: 0.6rem 0.25rem 0.6rem 0.5rem;
			border-radius: 0;
		}
		.r-name a {
			font-size: 0.95rem;
			line-height: 1.3;
		}
		.r-kw,
		.r-cost,
		.r-pb {
			font-size: 0.875rem;
		}
		.r-kw b {
			font-size: 0.95rem;
		}
		.total {
			font-size: 0.9rem;
		}
		.duo {
			gap: 0.875rem;
			margin-bottom: 0.875rem;
		}
		.curve figcaption h2 {
			font-size: 1.05rem;
		}
	}
</style>
