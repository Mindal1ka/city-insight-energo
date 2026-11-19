<script lang="ts">
	// Картка «Енергонезалежність закладу»: індекс, покриття сонцем, автономність і що зробити далі
	import {
		duration,
		money,
		years,
		type IndependenceDetail,
		type Improvement
	} from './api-independence.ts';
	import { num } from './format.ts';
	import IndexBadge from './IndexBadge.svelte';
	import DemoPill from './DemoPill.svelte';
	import Icon from './Icon.svelte';
	import Term from './Term.svelte';

	let { d, solarHref = null }: { d: IndependenceDetail; solarHref?: string | null } = $props();

	const it = $derived(d.item);
	const hasBat = $derived((it.battery_kwh ?? 0) > 0);
	const self = $derived(it.self_sufficiency_pct ?? 0);

	const headline = $derived.by(() => {
		if (!hasBat && !it.has_ses) return 'Власного резерву немає: якщо вимкнуть світло, заклад зупиниться одразу';
		if (it.autonomy_hours === null) return 'Акумулятор є, але без даних про споживання автономність не порахувати';
		if (!hasBat) return 'Сонце допомагає вдень, але без акумулятора відключення світла зупинить заклад';
		return `Якщо вимкнуть світло, заклад протримається ${duration(it.autonomy_hours)} вночі${
			it.has_ses ? ` і ${duration(it.autonomy_hours_with_sun)} вдень, коли світить сонце` : ''
		}`;
	});

	const WORD: Record<string, number> = { висока: 1, середня: 2, низька: 3 };
	const prio = (p: Improvement['priority']) =>
		typeof p === 'number' ? p : (WORD[p] ?? (Number.parseFloat(p) || 9));
	const steps = $derived([...d.improve].sort((a, b) => prio(a.priority) - prio(b.priority)));
</script>

<section class="panel ic" aria-labelledby="ic-h">
	<div class="ic-head">
		<div class="ic-title">
			<p class="eyebrow"><Term key="енергонезалежність">Енергонезалежність</Term> закладу</p>
			<h2 id="ic-h">{headline}</h2>
		</div>
		<div class="ic-badges">
			<IndexBadge index={it.index} cls={it.index_class} size="lg" />
			{#if it.critical}
				<span class="crit">
					<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 4.5 6v5.5c0 4.6 3.2 8.3 7.5 9.5 4.3-1.2 7.5-4.9 7.5-9.5V6L12 3Z" /><path d="M12 8.5v6M9 11.5h6" /></svg>
					критичний заклад
				</span>
			{/if}
			<DemoPill text="Станції й акумулятори в пакеті міста не вказані; індекс розраховано на змодельованих СЕС і реальному споживанні UMUNI 2025" />
		</div>
	</div>

	{#if it.data_ok === false}
		<p class="notice notice-warn nodata">У UMUNI немає річного споживання електроенергії цієї будівлі, тому частку сонця й автономність не розраховано. Перший крок — внести дані лічильника.</p>
	{/if}

	<div class="stats">
		<div class="st">
			<p class="st-l"><span class="ki sun"><Icon name="sun" size={20} /></span>Сонце покриває</p>
			<p class="st-v"><span class="big-num">{num(self, self < 10 ? 1 : 0)}</span><span class="unit-s">%</span></p>
			<div class="bar" aria-hidden="true"><span style="width: {Math.min(100, self)}%"></span></div>
			<p class="st-s">
				<Term key="частка власної генерації">власної генерації</Term> від річного споживання
				{#if it.elec_kwh_year}({num(it.elec_kwh_year)} <Term key="кВт·год">кВт·год</Term>){/if}
			</p>
		</div>
		<div class="st">
			<p class="st-l"><span class="ki teal"><Icon name="battery" size={20} /></span>Без світла вночі</p>
			<p class="st-v"><span class="big-num dur">{hasBat ? duration(it.autonomy_hours) : '0 хв'}</span></p>
			<p class="st-s">
				{#if hasBat}
					вистачить <Term key="акумулятор">акумулятора</Term> на {num(it.battery_kwh, 0)} кВт·год
				{:else}
					<Term key="акумулятор">акумулятора</Term> немає — резерву на ніч нуль
				{/if}
			</p>
		</div>
		<div class="st">
			<p class="st-l"><span class="ki green"><Icon name="clock" size={20} /></span>Без світла вдень</p>
			<p class="st-v">
				<span class="big-num dur">{#if it.autonomy_with_sun_capped}<small class="over">понад</small> {/if}{it.has_ses || hasBat ? duration(it.autonomy_hours_with_sun) : '0 хв'}</span>
			</p>
			<p class="st-s">
				{#if it.has_ses}
					<Term key="автономність">автономність</Term>: акумулятор + <Term key="СЕС">СЕС</Term> {num(it.ses_kw, 1)} <Term key="кВт">кВт</Term>
				{:else}
					сонячної станції немає — вдень так само, як уночі
				{/if}
			</p>
		</div>
	</div>

	{#if d.explain.length}
		<div class="why">
			<h3>Чому такий індекс</h3>
			<ul>
				{#each d.explain as e, i (i)}
					<li>{e}</li>
				{/each}
			</ul>
		</div>
	{/if}

	{#if steps.length}
		<div class="todo">
			<div class="todo-head">
				<h3>Що зробити, щоб стати незалежнішим</h3>
				{#if solarHref}
					<a href={solarHref} class="more">Детальний розрахунок СЕС для даху <Icon name="arrow-right" size={16} /></a>
				{/if}
			</div>
			<ol class="steps">
				{#each steps as s, i (i)}
					<li class="step" class:first={i === 0}>
						<span class="no" aria-hidden="true">{i + 1}</span>
						<div class="step-body">
							<p class="act">
								{#if i === 0}<span class="visually-hidden">Найперше: </span>{/if}{s.action}
							</p>
							<p class="eff"><Icon name="arrow-right" size={15} /> {s.effect}</p>
							<dl class="facts">
								{#if s.kw}<div><dt>СЕС</dt><dd>{num(s.kw, 1)} кВт</dd></div>{/if}
								{#if s.battery_kwh}<div><dt>Акумулятор</dt><dd>{num(s.battery_kwh, 0)} кВт·год</dd></div>{/if}
								{#if s.cost_uah}<div><dt>Вартість</dt><dd>≈ {money(s.cost_uah)}</dd></div>{/if}
								{#if s.payback_years}
									<div><dt><Term key="окупність">Окупність</Term></dt><dd>{years(s.payback_years)}</dd></div>
								{:else if s.cost_uah && s.battery_kwh}
									<div><dt>Окупність</dt><dd class="muted">не про гроші — про безпеку</dd></div>
								{/if}
							</dl>
						</div>
					</li>
				{/each}
			</ol>
		</div>
	{/if}

	{#if d.formula?.text}
		<details class="formula">
			<summary>Як рахується індекс</summary>
			<p>{d.formula.text}</p>
			{#if d.notes?.length}
				<ul class="w muted small">
					{#each d.notes as n, i (i)}<li>{n}</li>{/each}
				</ul>
			{/if}
		</details>
	{/if}
</section>

<style>
	.ic {
		position: relative;
		overflow: hidden;
		display: grid;
		gap: 1.4rem;
		border-top: 5px solid var(--navy-3);
		background:
			radial-gradient(700px 200px at 100% 0%, rgba(245, 165, 36, 0.1), transparent 70%),
			var(--surface);
	}
	.ic-head {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: flex-start;
		gap: 0.75rem 2rem;
	}
	.ic-title {
		flex: 1 1 30rem;
		min-width: 0;
	}
	.ic-title .eyebrow {
		margin: 0 0 0.3rem;
	}
	.ic-title h2 {
		font-size: 1.55rem;
		line-height: 1.3;
		margin: 0;
		max-width: 46ch;
	}
	.ic-badges {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.6rem;
	}
	.crit {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0.25rem 0.75rem;
		border-radius: 999px;
		background: #fbe9e8;
		color: #8f1414;
		border: 1px solid #f0b8b5;
		font-weight: 700;
		font-size: 0.875rem;
	}
	.stats {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 1rem;
	}
	.st {
		padding: 1rem 1.15rem;
		border-radius: 14px;
		background: #f7f9fc;
		border: 1px solid #e6ebf1;
		display: flex;
		flex-direction: column;
	}
	.st-l {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		margin: 0 0 0.45rem;
		font-weight: 600;
		color: #2b3645;
	}
	.ki {
		display: grid;
		place-items: center;
		width: 2.2rem;
		height: 2.2rem;
		border-radius: 11px;
		flex: none;
	}
	.ki.sun {
		background: var(--sun-soft);
		color: var(--sun-ink);
	}
	.ki.teal {
		background: #dff3f0;
		color: #0f766e;
	}
	.ki.green {
		background: var(--surplus-soft);
		color: var(--surplus-ink);
	}
	.st-v {
		margin: 0;
	}
	.st-v .big-num {
		font-size: 2.5rem;
	}
	.st-v .dur {
		font-size: 2.1rem;
	}
	.over {
		font-size: 1rem;
		font-weight: 600;
		color: var(--muted);
	}
	.nodata {
		margin: 0;
	}
	.bar {
		height: 8px;
		border-radius: 999px;
		background: #e3e8ef;
		margin: 0.55rem 0 0;
		overflow: hidden;
	}
	.bar span {
		display: block;
		height: 100%;
		background: var(--sun-strong);
		border-radius: 999px;
	}
	.st-s {
		margin: 0.5rem 0 0;
		color: #3d4857;
		font-size: 0.925rem;
	}
	h3 {
		font-size: 1.1rem;
		margin: 0 0 0.6rem;
	}
	.why ul {
		margin: 0;
		padding-left: 1.2rem;
		display: grid;
		gap: 0.25rem;
		color: #2b3645;
	}
	.todo-head {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: baseline;
		gap: 0.25rem 1rem;
	}
	.more {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		font-weight: 600;
	}
	.steps {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 19rem), 1fr));
		gap: 0.9rem;
	}
	.step {
		display: flex;
		gap: 0.8rem;
		padding: 1rem 1.1rem;
		border-radius: 14px;
		border: 1px solid #dbe3ec;
		background: #fff;
		box-shadow: var(--shadow);
	}
	.step.first {
		border: 2px solid var(--sun-strong);
		background: linear-gradient(180deg, #fffaf0, #fff);
	}
	.no {
		flex: none;
		display: grid;
		place-items: center;
		width: 2rem;
		height: 2rem;
		border-radius: 50%;
		background: var(--navy);
		color: #fff;
		font-weight: 800;
	}
	.first .no {
		background: var(--sun-strong);
		color: #2b1a00;
	}
	.step-body {
		min-width: 0;
	}
	.act {
		margin: 0.15rem 0 0.3rem;
		font-weight: 700;
		font-size: 1.05rem;
		line-height: 1.35;
	}
	.eff {
		display: flex;
		gap: 0.35rem;
		align-items: flex-start;
		margin: 0 0 0.6rem;
		color: var(--surplus-ink);
		font-weight: 600;
	}
	.eff :global(.icon) {
		flex: none;
		margin-top: 0.2rem;
	}
	.facts {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 1.25rem;
		margin: 0;
	}
	.facts div {
		display: flex;
		flex-direction: column;
	}
	.facts dt {
		font-size: 0.78rem;
		color: var(--muted);
	}
	.facts dd {
		margin: 0;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}
	.facts dd.muted {
		font-weight: 500;
		font-size: 0.875rem;
	}
	.formula {
		border-top: 1px solid #e6ebf1;
		padding-top: 0.9rem;
	}
	.formula p {
		margin: 0.6rem 0 0.4rem;
	}
	.formula .w {
		margin: 0;
		padding-left: 1.2rem;
		display: grid;
		gap: 0.2rem;
	}
	@media (max-width: 1000px) {
		.stats {
			grid-template-columns: 1fr;
		}
		.st {
			display: grid;
			grid-template-columns: minmax(0, 1fr) auto;
			align-items: center;
			column-gap: 1rem;
		}
		.st-l {
			grid-column: 1;
		}
		.st-v {
			grid-column: 2;
			grid-row: 1 / span 3;
		}
		.bar,
		.st-s {
			grid-column: 1;
		}
	}
	@media (max-width: 560px) {
		.ic-title h2 {
			font-size: 1.3rem;
		}
	}
</style>
