<script lang="ts">
	// «Що зробити»: індекс енергостійкості одним реченням, кроки (перший — головний),
	// а «чому такий індекс» і формула — у «Детальніше».
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
	import Disclosure from './Disclosure.svelte';

	let { d, solarHref = null }: { d: IndependenceDetail; solarHref?: string | null } = $props();

	const it = $derived(d.item);
	const hasBat = $derived((it.battery_kwh ?? 0) > 0);
	const self = $derived(it.self_sufficiency_pct ?? 0);

	const WORD: Record<string, number> = { висока: 1, середня: 2, низька: 3 };
	const prio = (p: Improvement['priority']) =>
		typeof p === 'number' ? p : (WORD[p] ?? (Number.parseFloat(p) || 9));
	const steps = $derived([...d.improve].sort((a, b) => prio(a.priority) - prio(b.priority)));

	/** Ефект кроку: перше речення — головне, решта — дрібним шрифтом */
	function split(t: string): [string, string] {
		const parts = t.split(/(?<=\.)\s+(?=[А-ЯІЇЄҐA-Z])/);
		return [parts[0] ?? t, parts.slice(1).join(' ')];
	}

	/** Мала добудова СЕС дорожча на 1 кВт: у вартість входять фіксовані витрати на підключення */
	function perKwNote(s: Improvement): string | null {
		if (!s.cost_uah || !/СЕС|сонячн/i.test(s.action)) return null;
		const m = s.action.match(/(\d+(?:[.,]\d+)?)\s*кВт(?!·)/);
		const kw = m ? Number.parseFloat(m[1].replace(',', '.')) : 0;
		if (!(kw > 0)) return null;
		const per = s.cost_uah / kw;
		if (per < 40000) return null;
		return `≈ ${money(per)} за 1 кВт — включно з фіксованими витратами на підключення ≈ 60 000 грн, тому малі доповнення дорожчі на кВт, ніж нова станція.`;
	}

	const indexText = $derived.by(() => {
		if (it.data_ok === false) return 'Індекс не розраховано — бракує даних про споживання.';
		if (it.index_class === 'відсутня') return 'Резерв не зафіксовано: у даних немає ні сонячної станції, ні акумулятора.';
		if (it.index_class === 'висока') return 'Заклад добре підготовлений до відключень. Можна стати ще незалежнішим.';
		if (it.index_class === 'середня') return 'Заклад частково готовий до відключень — є що покращити.';
		return 'Заклад слабо захищений від відключень.';
	});
</script>

<section class="panel ic" aria-label="Індекс енергостійкості і що зробити">
	<div class="ic-head">
		<IndexBadge index={it.index} cls={it.index_class} size="lg" />
		<div class="ic-title">
			<p class="ic-k">
				<Term key="індекс енергостійкості">Індекс енергостійкості</Term> — {it.index} зі 100
			</p>
			<p class="ic-t">{indexText}</p>
		</div>
		<DemoPill text="Станції й акумулятори в пакеті міста не вказані; індекс розраховано на змодельованих СЕС і реальному споживанні UMUNI 2025" />
	</div>

	{#if steps.length}
		<ol class="steps">
			{#each steps as s, i (i)}
				{@const [main, rest] = split(s.effect)}
				<li class="step" class:first={i === 0}>
					<span class="no" aria-hidden="true">{i + 1}</span>
					<div class="step-body">
						{#if i === 0}<p class="tag">Найперше</p>{/if}
						<p class="act">{s.action.replace(/^(.*СЕС.*?)\s+СЕС$/, '$1')}</p>
						<p class="eff"><Icon name="arrow-right" size={15} /> <span>{main}</span></p>
						{#if rest}<p class="rest">{rest}</p>{/if}
						{#if s.cost_uah || s.payback_years || (s.cost_uah && s.battery_kwh)}
							<dl class="facts">
								{#if s.cost_uah}<div><dt>Вартість</dt><dd>≈ {money(s.cost_uah)}</dd></div>{/if}
								{#if s.payback_years}
									<div><dt><Term key="окупність">Окупність</Term></dt><dd>{years(s.payback_years)}</dd></div>
								{:else if s.cost_uah && s.battery_kwh}
									<div><dt>Окупність</dt><dd class="soft">не про гроші — про безпеку</dd></div>
								{/if}
							</dl>
							{@const note = perKwNote(s)}
							{#if note}<p class="per-kw"><Icon name="info" size={14} /> <span>{note}</span></p>{/if}
						{/if}
					</div>
				</li>
			{/each}
		</ol>
	{/if}

	{#if solarHref}
		<p class="more-row">
			<a href={solarHref} class="btn btn-secondary">Детальний розрахунок сонячної станції для даху <Icon name="arrow-right" size={16} /></a>
		</p>
	{/if}

	<Disclosure summary="Чому такий індекс і як його рахують">
		<div class="why-stats">
			<div class="ws">
				<p class="ws-l">Сонце за рік покриває</p>
				<p class="ws-v tnum">{num(self, self < 10 ? 1 : 0)} %</p>
				<div class="bar" aria-hidden="true"><span style="--w: {Math.min(100, self)}%"></span></div>
				<p class="ws-s">
					<Term key="частка власної генерації">власної генерації</Term> від річного споживання
					{#if it.elec_kwh_year}({num(it.elec_kwh_year)} <Term key="кВт·год">кВт·год</Term>){/if}
				</p>
			</div>
			<div class="ws">
				<p class="ws-l">Без світла вночі</p>
				<p class="ws-v tnum">{hasBat ? duration(it.autonomy_hours) : '0 хв'}</p>
				<p class="ws-s">
					{#if hasBat}на <Term key="акумулятор">акумуляторі</Term> {num(it.battery_kwh, 1)} кВт·год{:else}акумулятор не зафіксовано{/if}
				</p>
			</div>
			<div class="ws">
				<p class="ws-l">Без світла вдень</p>
				<p class="ws-v tnum">{#if it.autonomy_with_sun_capped}понад {/if}{it.has_ses || hasBat ? duration(it.autonomy_hours_with_sun) : '0 хв'}</p>
				<p class="ws-s">
					{#if it.has_ses}<Term key="автономність">автономність</Term> з <Term key="СЕС">СЕС</Term> {num(it.ses_kw, 1)} кВт{:else}сонячну станцію не зафіксовано{/if}
				</p>
			</div>
		</div>
		{#if d.explain.length}
			<h4>Звідки ці цифри</h4>
			<ul class="why">
				{#each d.explain as e, i (i)}
					<li>{e}</li>
				{/each}
			</ul>
		{/if}
		{#if d.formula?.text}
			<h4>Формула</h4>
			<p class="formula">{d.formula.text}</p>
		{/if}
		{#if d.notes?.length}
			<ul class="w muted small">
				{#each d.notes as n, i (i)}<li>{n}</li>{/each}
			</ul>
		{/if}
	</Disclosure>
</section>

<style>
	.ic {
		display: grid;
		gap: 1.25rem;
	}
	.ic-head {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.75rem 1.25rem;
	}
	.ic-title {
		flex: 1 1 20rem;
		min-width: 0;
	}
	.ic-k {
		margin: 0;
		font-weight: 600;
		color: var(--muted);
	}
	.ic-t {
		margin: 0.1rem 0 0;
		font-size: 1.2rem;
		font-weight: 700;
		line-height: 1.35;
		color: var(--ink, #0f1b2d);
	}
	.steps {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 20rem), 1fr));
		gap: 1rem;
	}
	.step {
		display: flex;
		gap: 0.9rem;
		padding: 1.1rem 1.2rem;
		border-radius: var(--r-card);
		border: 1px solid #dbe3ec;
		background: #fff;
		box-shadow: var(--shadow);
		transition:
			transform var(--dur-base, 240ms) var(--ease-out, ease),
			box-shadow var(--dur-base, 240ms);
	}
	.step:hover {
		transform: translateY(-2px);
		box-shadow: var(--shadow-md);
	}
	.step.first {
		border: 2px solid var(--sun-strong);
		background: linear-gradient(180deg, #fffaf0, #fff);
	}
	.no {
		flex: none;
		display: grid;
		place-items: center;
		width: 2.1rem;
		height: 2.1rem;
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
	.tag {
		display: inline-block;
		margin: 0 0 0.25rem;
		padding: 0.05rem 0.55rem;
		border-radius: var(--r-pill);
		background: var(--sun-soft);
		color: var(--sun-ink);
		font-size: 0.75rem;
		font-weight: 600;
	}
	.act {
		margin: 0.1rem 0 0.35rem;
		font-weight: 700;
		font-size: 1.1rem;
		line-height: 1.35;
	}
	.eff {
		display: flex;
		gap: 0.35rem;
		align-items: flex-start;
		margin: 0;
		color: var(--surplus-ink);
		font-weight: 600;
	}
	.eff :global(.icon) {
		flex: none;
		margin-top: 0.25rem;
	}
	.rest {
		margin: 0.35rem 0 0;
		font-size: 0.875rem;
		color: var(--muted);
	}
	.per-kw {
		display: flex;
		gap: 0.35rem;
		align-items: flex-start;
		margin: 0.4rem 0 0;
		font-size: 0.8125rem;
		line-height: 1.4;
		color: var(--muted);
		max-width: 60ch;
	}
	.per-kw :global(.icon) {
		flex: none;
		margin-top: 0.15rem;
	}
	.facts {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem 1.5rem;
		margin: 0.7rem 0 0;
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
	.facts dd.soft {
		font-weight: 500;
		font-size: 0.875rem;
		color: var(--muted);
	}
	.more-row {
		margin: 0;
	}
	.why-stats {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 14rem), 1fr));
		gap: 0.75rem;
		margin-bottom: 1rem;
	}
	.ws {
		padding: 0.85rem 1rem;
		border-radius: var(--r-card);
		background: var(--surface-2, #f7f9fc);
		border: 1px solid var(--line-soft, #e6ebf1);
	}
	.ws-l {
		margin: 0;
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--muted);
	}
	.ws-v {
		margin: 0.1rem 0 0;
		font-size: 1.6rem;
		font-weight: 700;
	}
	.ws-s {
		margin: 0.3rem 0 0;
		font-size: 0.875rem;
		color: var(--text-2, #36425a);
	}
	.bar {
		height: 6px;
		border-radius: var(--r-sm);
		background: #e3e8ef;
		margin: 0.4rem 0 0;
		overflow: hidden;
	}
	.bar span {
		display: block;
		height: 100%;
		width: var(--w);
		background: var(--sun-strong);
		border-radius: var(--r-sm);
	}
	h4 {
		margin: 0.75rem 0 0.4rem;
		font-size: 1rem;
	}
	.why {
		margin: 0;
		padding-left: 1.2rem;
		display: grid;
		gap: 0.3rem;
		color: var(--text-2, #2b3645);
	}
	.formula {
		margin: 0 0 0.5rem;
		color: var(--text-2, #2b3645);
	}
	.w {
		margin: 0.5rem 0 0;
		padding-left: 1.2rem;
		display: grid;
		gap: 0.2rem;
	}
	/* Телефон: щільніше, кроки на всю ширину */
	@media (max-width: 640px) {
		.ic {
			gap: 1rem;
		}
		.ic-head {
			gap: 0.6rem 0.75rem;
		}
		.ic-head :global(.ib.lg) {
			font-size: 1.05rem;
		}
		.ic-t {
			font-size: 1.05rem;
		}
		.step {
			gap: 0.65rem;
			padding: 0.85rem 0.8rem;
		}
		.no {
			width: 1.75rem;
			height: 1.75rem;
			font-size: 0.9rem;
		}
		.act {
			font-size: 1rem;
		}
		.more-row :global(.btn) {
			width: 100%;
			justify-content: center;
			white-space: normal;
			text-align: center;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.step,
		.step:hover {
			transition: none;
			transform: none;
		}
	}
</style>
