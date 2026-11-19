<script lang="ts">
	// Дашборд «Розподілення енергії» — для одного об'єкта або для громади (агреговані значення)
	import type { SiteDistribution } from './api.ts';
	import { num, signed, hh } from './format.ts';
	import Icon from './Icon.svelte';
	import SocGauge from './SocGauge.svelte';
	import DemoPill from './DemoPill.svelte';

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
	const who = $derived(scope === 'community' ? 'об’єктам з СЕС' : 'об’єкту');
</script>

<div class="dist">
	<!-- Баланс розподілу -->
	<section class="panel balance {d.enough ? 'ok' : 'bad'}" aria-labelledby="bal-h-{scope}">
		<div class="bal-main">
			<div class="sign" aria-hidden="true">{d.enough ? '+' : '−'}</div>
			<div>
				<p class="eyebrow">Баланс розподілу до кінця дня</p>
				<h2 id="bal-h-{scope}" class="bal-title">
					{#if !hasSes}
						Власних джерел немає — уся енергія з мережі
					{:else if d.enough}
						Енергії достатньо
					{:else}
						Енергії не вистачає
					{/if}
				</h2>
				<p class="bal-num">
					<span class="big-num">{signed(d.balance_kwh, 1)}</span><span class="unit-s">кВт·год</span>
				</p>
				<p class="bal-text">
					{#if !hasSes}
						До кінця дня {who} потрібно {num(d.need_kwh_rest_of_day, 1)} кВт·год — усе буде куплено з мережі.
					{:else if d.enough}
						Акумулятор і сонце покривають потребу до кінця дня з запасом {num(d.balance_kwh, 1)} кВт·год.
					{:else}
						Бракує {num(Math.abs(d.balance_kwh), 1)} кВт·год — їх буде докуплено з мережі.
					{/if}
				</p>
			</div>
		</div>

		<div class="compare" aria-label="Порівняння доступної і потрібної енергії">
			<div class="row">
				<div class="row-head">
					<span>Доступно</span>
					<span class="tnum"><b>{num(d.available_kwh, 1)}</b> кВт·год</span>
				</div>
				<div class="track">
					{#if bat > 0}<span class="seg-bat" style="width: {(bat / scale) * 100}%" title="Акумулятор"></span>{/if}
					{#if sol > 0}<span class="seg-sol" style="width: {(sol / scale) * 100}%" title="Сонце до кінця дня"></span>{/if}
				</div>
				{#if hasSes}
					<p class="parts">
						<span><i class="k bat" aria-hidden="true"></i>акумулятор {num(bat, 1)}</span>
						<span class="plus" aria-hidden="true">+</span>
						<span><i class="k sol" aria-hidden="true"></i>сонце до кінця дня {num(sol, 1)}</span>
					</p>
				{/if}
			</div>
			<div class="row">
				<div class="row-head">
					<span>Потрібно до кінця дня</span>
					<span class="tnum"><b>{num(d.need_kwh_rest_of_day, 1)}</b> кВт·год</span>
				</div>
				<div class="track">
					<span class="seg-need" style="width: {(d.need_kwh_rest_of_day / scale) * 100}%"></span>
				</div>
			</div>
		</div>
	</section>

	<div class="cards">
		<!-- Пікове споживання -->
		<section class="panel kcard">
			<p class="k-label"><span class="ic navy"><Icon name="gauge" size={18} /></span>Макс. споживання протягом дня</p>
			<p class="k-val"><span class="big-num">{num(d.peak_kw, 1)}</span><span class="unit-s">кВт</span></p>
			<p class="k-sub"><Icon name="clock" size={15} /> о {hh(d.peak_hour)}</p>
			{#if peakNote}<p class="k-note">{peakNote}</p>{/if}
		</section>

		{#if hasSes}
			<!-- а) Акумулятори -->
			<section class="panel kcard">
				<p class="k-label"><span class="ic teal"><Icon name="battery" size={18} /></span>а) Накопичено в акумуляторах</p>
				<div class="bat-row">
					<p class="k-val"><span class="big-num">{num(d.battery_kwh_now, 1)}</span><span class="unit-s">кВт·год</span></p>
					<SocGauge pct={d.battery_soc_pct} size={170} />
				</div>
			</section>

			<!-- б) Сонячні батареї -->
			<section class="panel kcard">
				<p class="k-label"><span class="ic sun"><Icon name="sun" size={18} /></span>б) В сонячних батареях</p>
				<div class="two">
					<div>
						<p class="k-mini">зараз</p>
						<p class="k-val"><span class="big-num">{num(d.solar_kw_now, 1)}</span><span class="unit-s">кВт</span></p>
					</div>
					<div>
						<p class="k-mini">до кінця дня</p>
						<p class="k-val"><span class="big-num">{num(d.solar_kwh_rest_of_day, 1)}</span><span class="unit-s">кВт·год</span></p>
					</div>
				</div>
			</section>
		{:else}
			<section class="panel kcard cta">
				<span class="cta-ic" aria-hidden="true"><Icon name="sun" size={30} /></span>
				<div>
					<h3>Сонячної станції немає</h3>
					<p>Акумуляторів і власної генерації на цьому об’єкті немає. Подивіться, скільки міг би дати дах.</p>
					{#if solarHref}
						<a class="btn" href={solarHref}>СЕС немає — подивитися рекомендацію <Icon name="arrow-right" size={18} /></a>
					{/if}
				</div>
			</section>
		{/if}

		<!-- Запас розподілу -->
		<section class="panel kcard grid-card">
			<p class="k-label"><span class="ic green"><Icon name="grid" size={18} /></span>Запас розподілу · можна видати в мережу</p>
			<p class="k-val"><span class="big-num">{num(d.reserve_to_grid_kwh, 1)}</span><span class="unit-s">кВт·год</span></p>
			<p class="note">
				<Icon name="info" size={16} />
				<span>Зараз комунальні заклади не можуть продавати надлишок у мережу — це потенціал для енергокооперативу громади.</span>
			</p>
		</section>
	</div>
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
	.bad::before {
		background: var(--deficit);
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
		width: 7.5rem;
		height: 7.5rem;
		border-radius: 50%;
		font-size: 5.5rem;
		font-weight: 700;
		line-height: 1;
		color: #fff;
		padding-bottom: 0.4rem;
	}
	.ok .sign {
		background: radial-gradient(circle at 30% 25%, #2e9a4f, var(--surplus) 70%);
		box-shadow: 0 0 0 10px var(--surplus-soft);
	}
	.bad .sign {
		background: radial-gradient(circle at 30% 25%, #e0602a, var(--deficit) 70%);
		box-shadow: 0 0 0 10px var(--deficit-soft);
	}
	.bal-title {
		font-size: 1.75rem;
		margin: 0.15rem 0 0.2rem;
	}
	.ok .bal-title,
	.ok .bal-num {
		color: var(--surplus-ink);
	}
	.bad .bal-title,
	.bad .bal-num {
		color: var(--deficit-ink);
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
		border-radius: 999px;
		background: #edf1f5;
		overflow: hidden;
		gap: 2px;
	}
	.track span {
		height: 100%;
		transition: width 0.8s var(--ease);
	}
	.seg-bat {
		background: #0f766e;
	}
	.seg-sol {
		background: linear-gradient(90deg, #f7b23b, #ef9a12);
	}
	.seg-need {
		background: repeating-linear-gradient(-45deg, #1f4f84 0 7px, #2a5d96 7px 14px);
		border-radius: 999px;
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
		border-radius: 3px;
	}
	.k.bat {
		background: #0f766e;
	}
	.k.sol {
		background: #f0a020;
	}
	.cards {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 1.25rem;
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
		min-height: 2.6em;
	}
	.ic {
		display: grid;
		place-items: center;
		width: 2rem;
		height: 2rem;
		border-radius: 10px;
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
		font-size: 2.4rem;
	}
	.k-sub {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		margin: 0.15rem 0 0;
		font-weight: 600;
		color: #3d4857;
	}
	.k-note {
		margin: auto 0 0;
		padding-top: 0.5rem;
		font-size: 0.8125rem;
		color: var(--muted);
	}
	.k-mini {
		margin: 0;
		font-size: 0.8125rem;
		font-weight: 600;
		color: var(--muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.two {
		display: grid;
		gap: 0.75rem;
	}
	.bat-row {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		align-items: flex-start;
	}
	.bat-row :global(.g) {
		align-self: center;
	}
	.note {
		display: flex;
		gap: 0.45rem;
		margin: auto 0 0;
		padding: 0.65rem 0.75rem;
		border-radius: 10px;
		background: #f3f6fa;
		font-size: 0.8125rem;
		line-height: 1.45;
		color: #3d4857;
	}
	.note :global(.icon) {
		margin-top: 0.1rem;
		color: var(--navy-3);
	}
	.cta {
		grid-column: span 2;
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
		border-radius: 16px;
		background: var(--sun);
		color: #3b2400;
	}
	.foot {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.6rem;
		margin: 0;
		font-size: 0.875rem;
		color: var(--muted);
	}
	@media (max-width: 1200px) {
		.cards {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
	@media (max-width: 900px) {
		.balance {
			grid-template-columns: 1fr;
		}
	}
	@media (max-width: 620px) {
		.cards {
			grid-template-columns: 1fr;
		}
		.cta {
			grid-column: auto;
		}
		.sign {
			width: 5rem;
			height: 5rem;
			font-size: 3.6rem;
		}
	}
</style>
