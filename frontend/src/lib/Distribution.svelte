<script lang="ts">
	// «Розподілення енергії» — для одного об'єкта або для громади (агреговані значення).
	// Головне: баланс до кінця дня (+/−) і дві смуги «є» vs «потрібно».
	// Під ним — акумулятор і сонце; пікове споживання й запас для мережі — у «Детальніше».
	import type { SiteDistribution } from './api.ts';
	import { num, signed, hh } from './format.ts';
	import { isReduced } from './motion.ts';
	import Icon from './Icon.svelte';
	import SocGauge from './SocGauge.svelte';
	import DemoPill from './DemoPill.svelte';
	import CountUp from './CountUp.svelte';
	import Disclosure from './Disclosure.svelte';
	import Term from './Term.svelte';

	let {
		d,
		hasSes = true,
		scope = 'site',
		solarHref = null,
		peakNote = ''
	}: {
		d: SiteDistribution;
		hasSes?: boolean;
		scope?: 'site' | 'community';
		solarHref?: string | null;
		peakNote?: string;
	} = $props();

	const bat = $derived(d.battery_kwh_now ?? 0);
	const sol = $derived(d.solar_kwh_rest_of_day ?? 0);
	const scale = $derived(Math.max(1, d.available_kwh, d.need_kwh_rest_of_day));
	const who = $derived(scope === 'community' ? 'об’єктам з СЕС' : 'закладу');
	const coverPct = $derived(
		d.need_kwh_rest_of_day > 0 ? Math.min(100, (d.available_kwh / d.need_kwh_rest_of_day) * 100) : 100
	);

	// Смуги «ростуть», коли блок з’являється на екрані
	let seen = $state(true); // смуги балансу видно одразу (без «набігання» ширини)
	function onView(node: HTMLElement) {
		if (isReduced() || typeof IntersectionObserver === 'undefined') {
			seen = true;
			return;
		}
		const io = new IntersectionObserver(
			(es) => {
				if (es.some((e) => e.isIntersecting)) {
					seen = true;
					io.disconnect();
				}
			},
			{ threshold: 0.25 }
		);
		io.observe(node);
		return () => io.disconnect();
	}
	const w = (v: number) => (seen ? `${(v / scale) * 100}%` : '0%');
</script>

<div class="dist">
	<!-- Баланс розподілу -->
	<section class="panel balance {!hasSes || !d.enough ? 'none' : 'ok'}" class:seen aria-labelledby="bal-h-{scope}" {@attach onView}>
		<div class="bal-main">
			<div class="sign" aria-hidden="true">{!hasSes || !d.enough ? '↓' : '+'}</div>
			<div>
				<p class="eyebrow"><Term key="надлишок">Баланс</Term> до кінця дня</p>
				<h2 id="bal-h-{scope}" class="bal-title">
					{#if !hasSes}
						Власних джерел не зафіксовано — енергія з мережі
					{:else if d.enough}
						Енергії вистачить
					{:else}
						Решту докупимо з мережі
					{/if}
				</h2>
				<p class="bal-num">
					<span class="big-num"><CountUp value={d.balance_kwh} format={(n) => signed(n, 1)} /></span><span class="unit-s">кВт·год</span>
				</p>
				<p class="bal-text">
					{#if !hasSes}
						До кінця дня {who} потрібно ще {num(d.need_kwh_rest_of_day, 1)} кВт·год — усе буде куплено з мережі.
					{:else if d.enough}
						Акумулятор і сонце покривають потребу до кінця дня, ще й лишається {num(d.balance_kwh, 1)} кВт·год.
					{:else}
						Акумулятор і сонце покриють приблизно {num(coverPct, 0)} % потреби. Решту — {num(Math.abs(d.balance_kwh), 1)} кВт·год — докупимо з мережі.
					{/if}
				</p>
			</div>
		</div>

		<div class="compare" role="group" aria-label="Порівняння: скільки енергії є і скільки потрібно до кінця дня">
			{#if hasSes}
			<div class="row">
				<div class="row-head">
					<span>Є: акумулятор + сонце</span>
					<span class="tnum"><b><CountUp value={d.available_kwh} decimals={1} /></b> кВт·год</span>
				</div>
				<div class="track">
					{#if bat > 0}<span class="seg-bat" style:width={w(bat)}></span>{/if}
					{#if sol > 0}<span class="seg-sol" style:width={w(sol)}></span>{/if}
				</div>
				{#if hasSes}
					<p class="parts">
						<span><i class="k bat" aria-hidden="true"></i>в акумуляторі {num(bat, 1)}</span>
						<span class="plus" aria-hidden="true">+</span>
						<span><i class="k sol" aria-hidden="true"></i>дасть сонце до вечора {num(sol, 1)}</span>
					</p>
				{/if}
			</div>
			{/if}
			<div class="row">
				<div class="row-head">
					<span>Потрібно до кінця дня</span>
					<span class="tnum"><b><CountUp value={d.need_kwh_rest_of_day} decimals={1} /></b> кВт·год</span>
				</div>
				<div class="track">
					<span class="seg-need" style:width={w(d.need_kwh_rest_of_day)}></span>
				</div>
			</div>
		</div>
	</section>

	<div class="cards" class:solo={!hasSes}>
		{#if hasSes}
			<!-- а) Акумулятори -->
			<section class="panel kcard">
				<p class="k-label"><span class="ic teal"><Icon name="battery" size={18} /></span>В акумуляторах зараз</p>
				<div class="bat-row">
					<SocGauge pct={d.battery_soc_pct} size={170} />
					<div>
						<p class="k-val"><span class="big-num"><CountUp value={d.battery_kwh_now} decimals={1} /></span><span class="unit-s">кВт·год</span></p>
						<p class="k-hint">Стільки енергії запасено на випадок, коли зникне світло. <Term key="рівень заряду">Заряд</Term> — у відсотках від повного.</p>
					</div>
				</div>
			</section>

			<!-- б) Сонячні батареї -->
			<section class="panel kcard">
				<p class="k-label"><span class="ic sun"><Icon name="sun" size={18} /></span>Сонячні панелі</p>
				<div class="two">
					<div>
						<p class="k-mini">дають зараз</p>
						<p class="k-val"><span class="big-num"><CountUp value={d.solar_kw_now} decimals={1} /></span><span class="unit-s"><Term key="кВт" plain>кВт</Term></span></p>
					</div>
					<div>
						<p class="k-mini">дадуть до вечора</p>
						<p class="k-val"><span class="big-num"><CountUp value={d.solar_kwh_rest_of_day} decimals={1} /></span><span class="unit-s"><Term key="кВт·год" plain>кВт·год</Term></span></p>
					</div>
				</div>
				<p class="k-hint">«Зараз» — потужність у цю мить, «до вечора» — скільки енергії ще наберуть панелі.</p>
			</section>
		{:else}
			<section class="panel kcard cta">
				<span class="cta-ic" aria-hidden="true"><Icon name="sun" size={30} /></span>
				<div>
					<h3>Сонячну станцію не зафіксовано</h3>
					<p>У даних немає ні акумуляторів, ні власної генерації. Подивіться, скільки міг би дати дах.</p>
					{#if solarHref}
						<a class="btn btn-secondary" href={solarHref}>Подивитися розрахунок для даху <Icon name="arrow-right" size={18} /></a>
					{/if}
				</div>
			</section>
		{/if}
	</div>

	<Disclosure summary="Детальніше: пікове споживання і запас для мережі" class="dist-more">
		<div class="more">
			<div class="mcard">
				<p class="k-label"><span class="ic navy"><Icon name="gauge" size={18} /></span>Найбільше споживання за день</p>
				<p class="k-val"><span class="big-num">{num(d.peak_kw, 1)}</span><span class="unit-s">кВт</span></p>
				<p class="k-sub"><Icon name="clock" size={15} /> о {hh(d.peak_hour)}</p>
				<p class="k-hint">
					<Term key="пікова потужність">Пікова потужність</Term> — коли одночасно працює найбільше техніки.
					{#if peakNote}{peakNote}{/if}
				</p>
			</div>
			<div class="mcard">
				<p class="k-label"><span class="ic green"><Icon name="grid" size={18} /></span>Запас, який можна віддати в мережу</p>
				<p class="k-val"><span class="big-num">{num(d.reserve_to_grid_kwh, 1)}</span><span class="unit-s">кВт·год</span></p>
				<p class="k-hint">
					{#if d.reserve_to_grid_kwh > 0}Надлишок понад власні потреби.{:else}Сьогодні надлишку немає — усе споживається на місці.{/if}
					Зараз комунальні заклади не можуть продавати надлишок у мережу — це потенціал для енергокооперативу громади.
				</p>
			</div>
		</div>
	</Disclosure>

	{#if hasSes}
		<p class="foot"><DemoPill align="left" /> <span>Заряд, генерація й прогноз до кінця дня змодельовано.</span></p>
	{/if}
</div>

<style>
	.dist {
		display: grid;
		gap: 1.25rem;
	}
	.balance {
		display: grid;
		grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr);
		gap: 1.5rem 2.5rem;
		align-items: center;
		position: relative;
		overflow: hidden;
	}
	.balance::before {
		content: '';
		position: absolute;
		inset: 0 auto 0 0;
		width: 6px;
	}
	.ok::before {
		background: var(--surplus);
	}
	.none::before {
		background: var(--navy-3, #1f4f84);
	}
	.none .sign {
		background: radial-gradient(circle at 30% 25%, #2f6db0, #1f4f84 70%);
		box-shadow: 0 0 0 10px #e6eef8;
		font-size: 3.6rem;
		padding-bottom: 0;
	}
	.none .bal-title,
	.none .bal-num {
		color: var(--navy, #0f2f52);
	}
	.bal-main {
		display: flex;
		gap: 1.5rem;
		align-items: center;
	}
	.sign {
		flex: none;
		display: grid;
		place-items: center;
		width: 6.5rem;
		height: 6.5rem;
		border-radius: 50%;
		font-size: 4.75rem;
		font-weight: 700;
		line-height: 1;
		color: #fff;
		padding-bottom: 0.35rem;
	}
	.ok .sign {
		background: radial-gradient(circle at 30% 25%, #2e9a4f, var(--surplus) 70%);
		box-shadow: 0 0 0 10px var(--surplus-soft);
	}
	.eyebrow {
		margin: 0;
	}
	.bal-title {
		font-size: 1.6rem;
		margin: 0.15rem 0 0.2rem;
	}
	.ok .bal-title,
	.ok .bal-num {
		color: var(--surplus-ink);
	}
	.bal-num {
		margin: 0;
	}
	.bal-num .big-num {
		font-size: 2.6rem;
	}
	.bal-text {
		margin: 0.35rem 0 0;
		color: #3d4857;
		max-width: 46ch;
	}
	.compare {
		display: grid;
		gap: 1.1rem;
	}
	.row-head {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
		font-weight: 600;
		color: #2b3645;
		margin-bottom: 0.35rem;
	}
	.row-head b {
		font-size: 1.15rem;
	}
	.track {
		display: flex;
		height: 18px;
		border-radius: var(--r-sm);
		background: #edf1f5;
		overflow: hidden;
		gap: 2px;
	}
	.track span {
		height: 100%;
	}
	.seg-bat {
		background: #0f766e;
	}
	.seg-sol {
		background: linear-gradient(90deg, #f7b23b, #ef9a12);
	}
	.seg-need {
		background: repeating-linear-gradient(-45deg, #1f4f84 0 7px, #2a5d96 7px 14px);
		border-radius: var(--r-sm);
	}
	.parts {
		display: flex;
		flex-wrap: wrap;
		gap: 0.3rem 0.6rem;
		margin: 0.4rem 0 0;
		font-size: 0.875rem;
		color: var(--muted);
	}
	.parts span {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.k {
		width: 0.8rem;
		height: 0.8rem;
		border-radius: var(--r-sm);
	}
	.k.bat {
		background: #0f766e;
	}
	.k.sol {
		background: #f0a020;
	}
	.cards {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 1.25rem;
	}
	.cards.solo {
		grid-template-columns: 1fr;
	}
	.kcard {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		padding: 1.25rem 1.35rem;
	}
	.k-label {
		display: flex;
		align-items: center;
		gap: 0.55rem;
		font-weight: 600;
		color: #2b3645;
		margin: 0 0 0.5rem;
		line-height: 1.3;
	}
	.ic {
		display: grid;
		place-items: center;
		width: 2rem;
		height: 2rem;
		border-radius: var(--r-btn);
		flex: none;
	}
	.ic.navy {
		background: #e6eef8;
		color: var(--navy-3);
	}
	.ic.teal {
		background: #dff3f0;
		color: #0f766e;
	}
	.ic.sun {
		background: var(--sun-soft);
		color: var(--sun-ink);
	}
	.ic.green {
		background: var(--surplus-soft);
		color: var(--surplus-ink);
	}
	.k-val {
		margin: 0;
	}
	.k-val .big-num {
		font-size: 2.3rem;
	}
	.k-sub {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		margin: 0.15rem 0 0;
		font-weight: 600;
		color: #3d4857;
	}
	.k-hint {
		margin: 0.5rem 0 0;
		font-size: 0.9rem;
		line-height: 1.45;
		color: var(--muted);
	}
	.k-mini {
		margin: 0;
		font-size: 0.8125rem;
		font-weight: 600;
		color: var(--muted);


	}
	.two {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 0.75rem;
	}
	.bat-row {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem 1.25rem;
		align-items: center;
	}
	.bat-row > div {
		flex: 1 1 12rem;
	}
	.cta {
		flex-direction: row;
		align-items: flex-start;
		gap: 1.1rem;
		background: linear-gradient(135deg, #fffaf0, #fff4dc);
		border-color: #f3dcae;
	}
	.cta h3 {
		margin: 0.2rem 0 0.35rem;
		font-size: 1.2rem;
	}
	.cta p {
		color: #3d4857;
	}
	.cta-ic {
		display: grid;
		place-items: center;
		width: 3.5rem;
		height: 3.5rem;
		flex: none;
		border-radius: var(--r-card);
		background: var(--sun);
		color: #3b2400;
	}
	.dist :global(.dist-more) {
		margin-top: -0.5rem;
	}
	.more {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 18rem), 1fr));
		gap: 1rem;
	}
	.mcard {
		padding: 1rem 1.15rem;
		border-radius: var(--r-card);
		background: var(--surface);
		border: 1px solid var(--card-line, #e2e7ee);
	}
	.foot {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.6rem;
		margin: -0.5rem 0 0;
		font-size: 0.875rem;
		color: var(--muted);
	}
	@media (prefers-reduced-motion: no-preference) {
		.sign {
			transform: scale(0.6);
			opacity: 0;
			transition:
				transform 0.6s cubic-bezier(0.34, 1.56, 0.64, 1),
				opacity 0.3s;
		}
		.seen .sign {
			transform: none;
			opacity: 1;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.track span {
			transition: none;
		}
	}
	@media (max-width: 1000px) {
		.balance {
			grid-template-columns: 1fr;
		}
	}
	@media (max-width: 760px) {
		.cards {
			grid-template-columns: 1fr;
		}
	}
	@media (max-width: 620px) {
		.sign {
			width: 4.5rem;
			height: 4.5rem;
			font-size: 3.2rem;
		}
		.bal-main {
			gap: 1rem;
		}
	}
	/* Телефон: знак — маленький кружок угорі, текст на всю ширину картки */
	@media (max-width: 640px) {
		.bal-main {
			align-items: flex-start;
			gap: 0.8rem;
		}
		.sign,
		.none .sign {
			width: 2.75rem;
			height: 2.75rem;
			font-size: 1.9rem;
			padding-bottom: 0.15rem;
			margin-top: 0.15rem;
		}
		.ok .sign {
			box-shadow: 0 0 0 5px var(--surplus-soft);
		}
		.none .sign {
			box-shadow: 0 0 0 5px #e6eef8;
		}
		.bal-title {
			font-size: 1.25rem;
			line-height: 1.25;
		}
		.bal-num .big-num {
			font-size: 2rem;
		}
		.bal-text {
			font-size: 0.9375rem;
		}
	}
</style>
