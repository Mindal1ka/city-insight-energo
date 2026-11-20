<script lang="ts">
	// Презентація команди: 16:9 слайди (макет 1920×1080), режим доповідача, друк у PDF.
	// Текст і цифри — у lib/pitch/slides.ts. Сторінка публічна і не звертається до /api.
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { SLIDES, FOOTER, BRAND, type IconName } from '#lib/pitch/slides.ts';

	const W = 1920;
	const H = 1080;
	const N = SLIDES.length;

	let cur = $state(0);
	let dir = $state(1);
	let vw = $state(1920);
	let vh = $state(1080);
	const printMode = $derived(page.url.searchParams.get('print') === '1');
	const stacked = $derived(!printMode && vw < 768);
	const scale = $derived(stacked ? (vw - 32) / W : Math.min(vw / W, (vh - 64) / H));

	function go(n: number) {
		const next = Math.max(0, Math.min(N - 1, n));
		if (next === cur) return;
		dir = next > cur ? 1 : -1;
		cur = next;
		history.replaceState(history.state, '', `#${cur + 1}`);
	}
	const fromHash = () => {
		const n = parseInt(location.hash.slice(1), 10);
		if (n >= 1 && n <= N) {
			dir = n - 1 >= cur ? 1 : -1;
			cur = n - 1;
		}
	};

	function onKey(e: KeyboardEvent) {
		if (printMode || stacked || e.ctrlKey || e.metaKey || e.altKey) return;
		const k = e.key;
		if (k === 'ArrowRight' || k === 'PageDown' || k === ' ' || k === 'ArrowDown') {
			e.preventDefault();
			go(cur + 1);
		} else if (k === 'ArrowLeft' || k === 'PageUp' || k === 'ArrowUp') {
			e.preventDefault();
			go(cur - 1);
		} else if (k === 'Home') go(0);
		else if (k === 'End') go(N - 1);
		else if (k === 'f' || k === 'F' || k === 'а' || k === 'А') toggleFs();
	}
	function toggleFs() {
		if (document.fullscreenElement) document.exitFullscreen();
		else document.documentElement.requestFullscreen?.().catch(() => {});
	}
	function onStageClick(e: MouseEvent) {
		if (stacked || printMode) return;
		const t = e.target as HTMLElement;
		if (t.closest('a, button')) return;
		go(e.clientX < vw * 0.3 ? cur - 1 : cur + 1);
	}
	let tx = 0;
	let ty = 0;
	function onTouchStart(e: TouchEvent) {
		tx = e.touches[0].clientX;
		ty = e.touches[0].clientY;
	}
	function onTouchEnd(e: TouchEvent) {
		if (stacked || printMode) return;
		const dx = e.changedTouches[0].clientX - tx;
		const dy = e.changedTouches[0].clientY - ty;
		if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy)) go(cur + (dx < 0 ? 1 : -1));
	}
	const hideImg = (e: Event) => ((e.currentTarget as HTMLElement).style.display = 'none');

	onMount(() => {
		fromHash();
		window.addEventListener('hashchange', fromHash);
		return () => window.removeEventListener('hashchange', fromHash);
	});

	// Діаграма «джерела → Insight → ролі»: координати в межах блока 1680×700
	const FLOW_H = 660;
	const CORE_Y = 140;
	const srcY = (i: number) => 38 + i * 96;
	const roleY = (i: number) => 128 + i * 70;

	const maxBar = (vals: number[]) => Math.max(...vals);
</script>

{#snippet icon(name: IconName, size: number)}
	<svg class="ico" viewBox="0 0 24 24" width={size} height={size} aria-hidden="true">
		{#if name === 'bolt'}<path d="M13 2 4 14h7l-1 8 9-12h-7z" />
		{:else if name === 'book'}<path d="M3 5h6a3 3 0 0 1 3 3v12a2 2 0 0 0-2-2H3zM21 5h-6a3 3 0 0 0-3 3v12a2 2 0 0 1 2-2h7z" />
		{:else if name === 'cross'}<path d="M9 3h6v6h6v6h-6v6H9v-6H3V9h6z" />
		{:else if name === 'wallet'}<path d="M3 7h17v13H3zM3 7l13-4v4M15 13.5h5" />
		{:else if name === 'building'}<path d="M4 21V6l8-3 8 3v15M2 21h20M9 21v-5h6v5M8 9h1M15 9h1M8 12.5h1M15 12.5h1" />
		{:else if name === 'sun'}<circle cx="12" cy="12" r="4" /><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8" />
		{:else if name === 'coin'}<circle cx="12" cy="12" r="9" /><path d="M8.5 10.5h7M8.5 13.5h7M14.5 8.2c-1-1-4.5-1.2-5 .8-.6 2.4 5.6 2.4 5 5.2-.5 2-4 2-5.2.8" />
		{:else if name === 'gov'}<path d="M3 9.5 12 4l9 5.5M4 10h16M6 10v8M10 10v8M14 10v8M18 10v8M3 20.5h18" />
		{:else if name === 'culture'}<path d="M9 18V6l11-2v12M9 18a3 3 0 1 1-3-3 3 3 0 0 1 3 3zM20 16a3 3 0 1 1-3-3 3 3 0 0 1 3 3zM9 10l11-2" />
		{:else if name === 'sport'}<circle cx="12" cy="12" r="9" /><path d="M3.5 9.5c4 1.5 13 1.5 17 0M3.5 14.5c4-1.5 13-1.5 17 0M12 3c-3 4-3 14 0 18" />
		{:else if name === 'house'}<path d="M3 11 12 4l9 7M5 9.5V20h14V9.5M10 20v-6h4v6" />
		{:else}<circle cx="12" cy="12" r="9" /><path d="M12 7v5l3.5 2" />{/if}
	</svg>
{/snippet}

<svelte:window bind:innerWidth={vw} bind:innerHeight={vh} onkeydown={onKey} />
<svelte:head>
	<title>CITY INSIGHT MAP · презентація команди Insight</title>
</svelte:head>

<div
	class="deck"
	class:stacked
	class:print={printMode}
	style:--s={scale}
	ontouchstart={onTouchStart}
	ontouchend={onTouchEnd}
	role="presentation"
>
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div class="stage" onclick={onStageClick}>
		{#each SLIDES as s, i (i)}
			<div
				class="frame"
				class:on={i === cur}
				class:before={i < cur}
				class:after={i > cur}
				style:--dir={dir}
				aria-hidden={!stacked && !printMode && i !== cur}
			>
				<section class="slide k-{s.kind}" aria-label="Слайд {i + 1} з {N}">
					{#if s.kind === 'title'}
						<div class="t-grid">
							<img class="t-banner r" style:--i={0} src={s.logos.banner} alt={s.logos.bannerAlt} width="2000" height="1125" />
							<div class="t-right">
								<div class="city r" style:--i={1}>
									<img src={s.logos.gerb} alt="Герб Полтави" onerror={hideImg} />
									<img src={s.logos.emblem} alt="Емблема Полтавської міської ради" onerror={hideImg} />
								</div>
								<h1 class="r" style:--i={1}>{s.title}</h1>
								<p class="t-tag r" style:--i={2} lang="en">{s.tagline}</p>
								<p class="t-sub r" style:--i={3}>{s.subtitle}</p>
								<p class="t-lead r" style:--i={4}>{s.lead}</p>
								<div class="t-meta r" style:--i={5}>
									<p>{s.track}</p>
									<p>{s.direction}</p>
								</div>
							</div>
						</div>
						<div class="team r" style:--i={6}>
							{#each s.team as m (m.name)}
								<div class="tm"><b>{m.name}</b><span>{m.role}</span></div>
							{/each}
						</div>
					{:else if s.kind === 'problem'}
						<h2 class="r" style:--i={0}>{s.title}</h2>
						<div class="stats r" style:--i={1}>
							{#each s.stats as f (f.label)}
								<div class="st"><div class="st-v">{f.value}{#if f.unit}<small>{f.unit}</small>{/if}</div><div class="st-l">{f.label}</div></div>
							{/each}
						</div>
						<div class="p-grid">
							<div class="p-problem r" style:--i={2}>
								<h3>{s.problemTitle}</h3>
								<ul class="dash">{#each s.problems as pr (pr)}<li>{pr}</li>{/each}</ul>
							</div>
							<div class="p-value r" style:--i={3}>
								<h3>{s.valueTitle}</h3>
								<ul>{#each s.values as v (v)}<li>{v}</li>{/each}</ul>
							</div>
						</div>
						<div class="users r" style:--i={4}>
							<span class="users-t">{s.usersTitle}</span>
							{#each s.users as u (u.label)}
								<div class="user">
									<span class="ava">
										<svg viewBox="0 0 64 64" width="64" height="64" aria-hidden="true">
											<circle cx="32" cy="24" r="10" />
											<path d="M12 54c2-11 10-16 20-16s18 5 20 16" />
										</svg>
										<span class="badge">{@render icon(u.icon, 20)}</span>
									</span>
									<span class="user-l">{u.label}</span>
								</div>
							{/each}
						</div>
					{:else if s.kind === 'profile'}
						<h2 class="r" style:--i={0}>{s.title}</h2>
						<p class="lead r" style:--i={1}>{s.lead}</p>
						<div class="pr-grid">
							<div class="figs">
								{#each s.figures as f, j (j)}
									<div class="fig r" style:--i={2 + j}>
										<div class="fig-v">{f.value}{#if f.unit}<small>{f.unit}</small>{/if}</div>
										<div class="fig-l">{f.label}</div>
									</div>
								{/each}
							</div>
							<div class="chart card r" style:--i={6}>
								<h3>{s.chartTitle}</h3>
								<svg viewBox="0 0 760 420" width="760" height="420" role="img" aria-label={s.chartTitle}>
									{#each s.bars as b, j (b.label)}
										{@const y = j * 70}
										{@const w = Math.max(4, (b.value / maxBar(s.bars.map((x) => x.value))) * 360)}
										<text x="0" y={y + 36} class="bl">{b.label}</text>
										<rect x="270" y={y + 12} width={w} height="36" rx="4" class="cbar" class:first={j === 0} />
										<text x={270 + w + 14} y={y + 40} class="bv">{b.display}</text>
									{/each}
								</svg>
							</div>
						</div>
						<div class="defects r" style:--i={7}>
							<span class="def-t">{s.defectsTitle}</span>
							{#each s.defects as d (d.label)}
								<div class="def"><b>{d.value}</b><span>{d.label}</span></div>
							{/each}
						</div>
					{:else if s.kind === 'flow'}
						<h2 class="r" style:--i={0}>{s.title}</h2>
						<div class="flow" style:height="{FLOW_H}px">
							<svg class="wires r" style:--i={3} viewBox="0 0 1680 {FLOW_H}" width="1680" height={FLOW_H} aria-hidden="true">
								{#each s.sources as _, j (j)}
									<path d="M 470 {srcY(j)} C 590 {srcY(j)}, 590 {CORE_Y}, 680 {CORE_Y}" />
								{/each}
								{#each s.roles as _, j (j)}
									<path d="M 1120 {CORE_Y} C 1210 {CORE_Y}, 1210 {roleY(j)}, 1300 {roleY(j)}" />
								{/each}
							</svg>
							<div class="col src">
								{#each s.sources as src, j (src.name)}
									<div class="node r" style:--i={1 + j * 0.3} style:top="{srcY(j) - 38}px">
										<b>{src.name}</b><span>{src.detail}</span>
									</div>
								{/each}
							</div>
							<div class="center">
								<div class="core r" style:--i={4}>
									<div class="core-t">{s.coreTitle}</div>
									<ul>{#each s.core as c (c)}<li>{c}</li>{/each}</ul>
								</div>
								<div class="cstats r" style:--i={5}>
									{#each s.stats as f (f.label)}
										<div class="st"><div class="st-v">{f.value}</div><div class="st-l">{f.label}</div></div>
									{/each}
								</div>
							</div>
							<div class="col roles">
								<div class="roles-h r" style:--i={5}><b>{s.rolesTitle}</b><span>{s.rolesSub}</span></div>
								{#each s.roles as r, j (r.label)}
									<div class="node role r" style:--i={5 + j * 0.3} style:top="{roleY(j) - 28}px">
										<span class="role-ic">{@render icon(r.icon, 22)}</span>{r.label}
									</div>
								{/each}
							</div>
						</div>
					{:else if s.kind === 'finance'}
						<h2 class="r" style:--i={0}>{s.title}</h2>
						<p class="lead r" style:--i={1}>{s.lead}</p>
						<div class="fin">
							<div class="years">
								{#each s.years as y, j (y.year)}
									<div class="yr r" style:--i={2 + j}>
										<div class="yr-n">{y.year}</div>
										<div class="yr-bars">
											<div class="yb">
												<span class="yb-l">План</span>
												<div class="track"><div class="fill plan" style:width="{(y.plan / 92.5) * 100}%"></div></div>
												<span class="yb-v">{y.planText}</span>
											</div>
											<div class="yb">
												<span class="yb-l">Факт</span>
												<div class="track"><div class="fill fact" style:width="{(y.fact / 92.5) * 100}%"></div></div>
												<span class="yb-v">{y.factText}</span>
											</div>
											<div class="yr-note">{y.factNote}</div>
										</div>
									</div>
								{/each}
							</div>
							<div class="fin-figs">
								{#each s.figures as f, j (j)}
									<div class="fig r" style:--i={4 + j}>
										<div class="fig-v">{f.value}{#if f.unit}<small>{f.unit}</small>{/if}{#if f.demo}<span class="demo">ДЕМО</span>{/if}</div>
										<div class="fig-l">{f.label}</div>
									</div>
								{/each}
							</div>
						</div>
						<p class="note r" style:--i={7}>{s.note}</p>
					{:else if s.kind === 'solar'}
						<h2 class="r" style:--i={0}>{s.title}</h2>
						<div class="so-grid">
							<div class="so-left">
								<div class="kbox r" style:--i={1}>
									<span class="k-big">{s.kTitle}</span>
									<span class="k-f">{s.kFormula}</span>
								</div>
								<div class="so-figs">
									{#each s.figures as f, j (j)}
										<div class="fig sm r" style:--i={2 + j}>
											<div class="fig-v">{f.value}{#if f.demo}<span class="demo">ДЕМО</span>{/if}</div>
											<div class="fig-l">{f.label}</div>
										</div>
									{/each}
								</div>
								<div class="r" style:--i={5}>
									<svg class="kchart" viewBox="0 0 860 300" width="860" height="300" role="img" aria-label="Індекс K по місяцях">
										{#each s.months as m, j (j)}
											{@const h = (m.k / 2.4) * 240}
											<rect x={j * 72 + 6} y={250 - h} width="52" height={h} rx="4" class={m.k >= s.threshold ? 'kb ok' : 'kb low'} />
											<text x={j * 72 + 32} y="284" class="kx">{m.m}</text>
										{/each}
										<line x1="0" x2="860" y1={250 - (s.threshold / 2.4) * 240} y2={250 - (s.threshold / 2.4) * 240} class="thr" />
										<text x="860" y={250 - (s.threshold / 2.4) * 240 - 10} class="thr-t">K = 0,8</text>
									</svg>
								</div>
							</div>
							<div class="so-right">
								<figure class="shot r" style:--i={3}>
									<img src={s.shot} alt={s.shotCaption} />
									<figcaption>{s.shotCaption}</figcaption>
								</figure>
								<div class="auto card r" style:--i={6}>
									<div class="auto-main">
										<span class="auto-ic">{@render icon('clock', 34)}</span>
										<div>
											<div class="auto-t">{s.autonomy.title} <span class="demo">ДЕМО</span></div>
											<div class="auto-v">{s.autonomy.value}<small>год</small></div>
											<div class="auto-l">{s.autonomy.label}</div>
										</div>
									</div>
									<div class="auto-bars">
										{#each s.autonomy.bars as b (b.label)}
											<div class="ab">
												<span class="ab-l">{b.label}</span>
												<div class="ab-track"><div class="ab-fill" style:width="{(b.hours / 10) * 100}%"></div><div class="ab-goal"></div></div>
												<span class="ab-v">{b.display}</span>
											</div>
										{/each}
										<div class="ab-note">Риска — {s.autonomy.target}</div>
									</div>
								</div>
							</div>
						</div>
						<p class="note r" style:--i={7}>{s.autonomy.outage}</p>
					{:else if s.kind === 'econ'}
						<h2 class="r" style:--i={0}>{s.title}</h2>
						<div class="ec-grid">
							<table class="params r" style:--i={1}>
								<tbody>
									{#each s.params as p (p.name)}
										<tr><th>{p.name}</th><td class="pv">{p.value}</td><td class="ps">{p.source}</td></tr>
									{/each}
								</tbody>
							</table>
							<div class="ec-res">
								{#each s.result as f, j (j)}
									<div class="fig r" style:--i={2 + j}>
										<div class="fig-v">{f.value}{#if f.unit}<small>{f.unit}</small>{/if}{#if f.demo}<span class="demo">ДЕМО</span>{/if}</div>
										<div class="fig-l">{f.label}</div>
									</div>
								{/each}
							</div>
						</div>
						<div class="plain r" style:--i={5}>
							<span class="plain-t">{s.plainTitle}</span>
							{#each s.plain as pl (pl.big)}
								<div class="pl">
									<span class="pl-ic">{@render icon(pl.icon, 30)}</span>
									<div><b>{pl.big}</b><span>{pl.text}</span></div>
								</div>
							{/each}
						</div>
					{:else if s.kind === 'poc'}
						<h2 class="r" style:--i={0}>{s.title}</h2>
						<p class="lead r" style:--i={1}>{s.subtitle}</p>
						<div class="legend r" style:--i={2}>
							<span><i class="lg real"></i>{s.legendReal}</span>
							<span><i class="lg dm"></i>{s.legendDemo}</span>
						</div>
						<div class="poc">
							<div class="poc-col r" style:--i={3}>
								<h3><span class="cnt-b real">{s.real.length}</span>{s.realTitle}</h3>
								<div class="chips">{#each s.real as d (d)}<span class="chip real">{d}</span>{/each}</div>
							</div>
							<div class="poc-col r" style:--i={4}>
								<h3><span class="cnt-b dm">{s.demo.length}</span>{s.demoTitle}</h3>
								<div class="chips">{#each s.demo as d (d)}<span class="chip dm">{d}</span>{/each}</div>
							</div>
						</div>
					{:else if s.kind === 'plan'}
						<h2 class="r" style:--i={0}>{s.title}</h2>
						<p class="lead r" style:--i={1}>{s.lead}</p>
						<ol class="tl" style:grid-template-columns="repeat({s.steps.length}, 1fr)">
							{#each s.steps as st, j (j)}
								<li class="r" style:--i={2 + j}>
									<span class="dot">{j + 1}</span>
									<span class="when">{st.when}</span>
									<b>{st.title}</b>
									<span class="tx">{st.text}</span>
								</li>
							{/each}
						</ol>
						<p class="closing r" style:--i={8}>{s.closing}</p>
					{:else if s.kind === 'growth'}
						<h2 class="r" style:--i={0}>{s.title}</h2>
						<ol class="grow">
							{#each s.items as g, j (j)}
								<li class="r g{j + 1}" style:--i={1 + j}>
									<span class="g-n">{j + 1}</span>
									<h3>{g.title}</h3>
									<p class="g-t">{g.text}</p>
									<div class="g-v">{#each g.value as v (v)}<span class="gchip">{v}</span>{/each}</div>
								</li>
							{/each}
						</ol>
					{/if}
					<span class="corner">{BRAND}</span>
					<footer class="foot"><span>{FOOTER}</span><span>{i + 1} / {N}</span></footer>
				</section>
			</div>
		{/each}
	</div>

	{#if !printMode}
		<nav class="bar" aria-label="Керування презентацією">
			{#if !stacked}
				<div class="prog" aria-hidden="true"><div style:width="{((cur + 1) / N) * 100}%"></div></div>
				<button type="button" onclick={() => go(cur - 1)} disabled={cur === 0} aria-label="Попередній слайд">←</button>
				<span class="cnt" aria-live="polite">{cur + 1} / {N}</span>
				<button type="button" onclick={() => go(cur + 1)} disabled={cur === N - 1} aria-label="Наступний слайд">→</button>
				<button type="button" class="ghost" onclick={toggleFs} title="Повний екран (F)">Повний екран</button>
			{/if}
			<button type="button" class="pdf" onclick={() => window.print()}>Завантажити PDF</button>
		</nav>
	{/if}
</div>

<style>
	.deck {
		--navy: #0b2545;
		--navy-2: #133a66;
		--paper: #ffffff;
		--paper-2: #f3f6fa;
		--ink-p: #0f1b2d;
		--muted-p: #4f5b6b;
		position: fixed;
		inset: 0;
		background: #0a1626;
		overflow: hidden;
		font-family: var(--font);
		color: var(--ink-p);
	}
	.stage {
		position: absolute;
		left: 50%;
		top: calc(50% - 32px);
		width: calc(1920px * var(--s));
		height: calc(1080px * var(--s));
		transform: translate(-50%, -50%);
	}
	.frame {
		position: absolute;
		inset: 0;
		opacity: 0;
		visibility: hidden;
		transform: translateX(calc(12px * var(--dir)));
		transition:
			opacity 220ms var(--ease-out),
			transform 220ms var(--ease-out),
			visibility 0s linear 220ms;
	}
	.frame.before {
		transform: translateX(calc(-12px * var(--dir)));
	}
	.frame.on {
		opacity: 1;
		visibility: visible;
		transform: none;
		transition:
			opacity 220ms var(--ease-out),
			transform 220ms var(--ease-out),
			visibility 0s;
	}
	.slide {
		position: absolute;
		top: 0;
		left: 0;
		width: 1920px;
		height: 1080px;
		transform: scale(var(--s));
		transform-origin: 0 0;
		background: var(--paper);
		padding: 96px 120px 120px;
		box-sizing: border-box;
		overflow: hidden;
		display: flex;
		flex-direction: column;
		font-size: 30px;
		line-height: 1.4;
	}
	/* Поява елементів слайда: каскад ≤ 40 мс */
	.r {
		opacity: 0;
		transform: translateY(10px);
		transition:
			opacity 260ms var(--ease-out),
			transform 260ms var(--ease-out);
		transition-delay: calc(var(--i, 0) * 40ms + 60ms);
	}
	.frame.on .r,
	.stacked .r,
	.print .r {
		opacity: 1;
		transform: none;
	}

	h1,
	h2,
	h3 {
		font-family: var(--font-display);
		margin: 0;
		text-wrap: balance;
	}
	h2 {
		font-size: 64px;
		line-height: 1.1;
		font-weight: 650;
		letter-spacing: -0.01em;
		color: var(--navy);
		max-width: 1500px;
	}
	h3 {
		font-size: 34px;
		font-weight: 650;
		color: var(--navy);
	}
	.lead {
		margin: 20px 0 0;
		font-size: 30px;
		color: var(--muted-p);
	}
	.note {
		margin: auto 0 0;
		font-size: 24px;
		color: var(--muted-p);
		max-width: 1500px;
		padding-top: 24px;
	}
	.foot {
		position: absolute;
		left: 120px;
		right: 120px;
		bottom: 40px;
		display: flex;
		justify-content: space-between;
		font-size: 20px;
		color: var(--muted-p);
		border-top: 1px solid #d6dce4;
		padding-top: 16px;
	}
	.demo {
		display: inline-block;
		vertical-align: middle;
		margin-left: 16px;
		font-size: 18px;
		font-weight: 700;
		letter-spacing: 0.02em;
		color: #8a4f00;
		background: #fff4dc;
		border: 1px solid #f5a524;
		border-radius: var(--r-sm);
		padding: 2px 10px;
		line-height: 1.4;
	}

	/* Великі цифри */
	.fig-v {
		font-family: var(--font-display);
		font-size: 96px;
		line-height: 1;
		font-weight: 700;
		color: var(--navy);
		letter-spacing: -0.02em;
		font-variant-numeric: tabular-nums;
	}
	.fig-v small {
		font-size: 30px;
		font-weight: 600;
		margin-left: 12px;
		letter-spacing: 0;
		color: var(--navy-2);
	}
	.fig-l {
		margin-top: 10px;
		font-size: 24px;
		line-height: 1.35;
		color: var(--muted-p);
	}
	.fig.sm .fig-v {
		font-size: 72px;
	}

	/* 1 — титул */
	.k-title {
		background: var(--navy);
		color: #fff;
		padding: 0;
	}
	.logos {
		background: #fff;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 48px;
		padding: 28px 120px;
		height: 190px;
		box-sizing: border-box;
	}
	.partners {
		height: 130px;
		width: auto;
		max-width: 1300px;
		object-fit: contain;
	}
	.city {
		display: flex;
		gap: 36px;
		align-items: center;
	}
	.city img {
		height: 130px;
		width: auto;
	}
	.t-body {
		padding: 90px 120px 0;
	}
	.sunbar {
		width: 120px;
		height: 10px;
		background: var(--sun);
		border-radius: var(--r-sm);
		margin-bottom: 40px;
	}
	h1 {
		font-size: 140px;
		line-height: 0.95;
		font-weight: 750;
		letter-spacing: -0.02em;
		color: #fff;
	}
	.t-sub {
		margin: 36px 0 0;
		font-size: 46px;
		line-height: 1.2;
		max-width: 1500px;
		color: #fff;
		font-weight: 500;
	}
	.t-lead {
		margin: 28px 0 0;
		font-size: 34px;
		color: #f5c060;
	}
	.t-meta {
		margin-top: auto;
		padding: 0 120px 120px;
		font-size: 28px;
		color: #c9d6e8;
	}
	.t-meta p {
		margin: 6px 0 0;
	}
	.k-title .foot {
		color: #9fb3cc;
		border-color: #23446f;
	}

	/* 2 — проблема і цінність */
	.p-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 72px;
		margin-top: 40px;
	}
	.p-problem {
		background: var(--navy);
		color: #fff;
		border-radius: var(--r-card);
		padding: 48px 52px;
	}
	.p-problem h3 {
		color: #f5c060;
	}
	.p-problem p {
		margin: 20px 0 0;
		font-size: 29px;
		line-height: 1.45;
	}
	.p-value ul {
		margin: 20px 0 0;
		padding: 0;
		list-style: none;
	}
	.p-value li {
		font-size: 26px;
		line-height: 1.32;
		padding: 10px 0 10px 36px;
		border-bottom: 1px solid #e6ebf1;
		position: relative;
	}
	.p-value li::before {
		content: '';
		position: absolute;
		left: 0;
		top: 22px;
		width: 14px;
		height: 14px;
		border-radius: 3px;
		background: var(--sun);
	}
	.users {
		margin-top: auto;
		margin-bottom: 0;
		padding-top: 24px;
		display: flex;
		flex-wrap: wrap;
		gap: 14px;
		align-items: center;
	}
	.users-t {
		font-weight: 650;
		color: var(--navy);
		margin-right: 12px;
	}
	.user {
		font-size: 22px;
		background: #e8f1fb;
		color: #084684;
		border-radius: var(--r-btn);
		padding: 8px 18px;
	}

	/* 3 — профіль */
	.pr-grid {
		display: grid;
		grid-template-columns: 840px 1fr;
		gap: 80px;
		margin-top: 52px;
	}
	.figs {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 52px 48px;
	}
	.chart h3 {
		font-size: 26px;
		font-weight: 600;
		color: var(--muted-p);
		margin-bottom: 24px;
	}
	.chart svg {
		width: 100%;
		height: auto;
		overflow: visible;
	}
	.bl {
		font-size: 24px;
		fill: var(--ink-p);
	}
	.bv {
		font-size: 24px;
		font-weight: 650;
		fill: var(--navy);
	}
	.cbar {
		fill: #7aa3cf;
	}
	.cbar.first {
		fill: var(--navy-2);
	}

	/* 4 — потік даних */
	.flow {
		position: relative;
		margin-top: 36px;
		width: 1680px;
	}
	.wires {
		position: absolute;
		inset: 0;
	}
	.wires path {
		fill: none;
		stroke: #9aa6b4;
		stroke-width: 2;
	}
	.col {
		position: absolute;
		top: 0;
		bottom: 0;
	}
	.col.src {
		left: 0;
		width: 480px;
	}
	.col.roles {
		left: 1300px;
		width: 380px;
	}
	.node {
		position: absolute;
		left: 0;
		right: 0;
		height: 80px;
		box-sizing: border-box;
		background: var(--paper-2);
		border: 1px solid #d6dce4;
		border-radius: var(--r-btn);
		padding: 0 22px;
		display: flex;
		flex-direction: column;
		justify-content: center;
		font-size: 21px;
		line-height: 1.25;
		color: var(--muted-p);
	}
	.node b {
		font-size: 25px;
		color: var(--ink-p);
	}
	.node.role {
		height: 92px;
		font-size: 24px;
		color: var(--ink-p);
		background: #e8f1fb;
		border-color: #b9d1ec;
	}
	.roles-t {
		position: absolute;
		top: -44px;
		font-size: 22px;
		color: var(--muted-p);
	}
	.core {
		position: absolute;
		left: 690px;
		width: 420px;
		top: 50%;
		transform: translateY(-50%);
		background: var(--navy);
		color: #fff;
		border-radius: var(--r-card);
		padding: 40px 44px;
		box-sizing: border-box;
	}
	.frame.on .core.r,
	.stacked .core.r,
	.print .core.r {
		transform: translateY(-50%);
	}
	.core-t {
		font-family: var(--font-display);
		font-size: 60px;
		font-weight: 750;
		border-bottom: 6px solid var(--sun);
		display: inline-block;
		padding-bottom: 6px;
	}
	.core ul {
		margin: 24px 0 0;
		padding: 0;
		list-style: none;
		font-size: 27px;
		line-height: 1.3;
	}
	.core li {
		padding: 8px 0;
	}

	/* 5 — фінанси */
	.fin {
		display: grid;
		grid-template-columns: 1fr 560px;
		gap: 96px;
		margin-top: 56px;
	}
	.years {
		display: flex;
		flex-direction: column;
		gap: 56px;
	}
	.yr {
		display: grid;
		grid-template-columns: 150px 1fr;
		gap: 24px;
		align-items: start;
	}
	.yr-n {
		font-family: var(--font-display);
		font-size: 64px;
		font-weight: 700;
		color: var(--navy);
		line-height: 1;
	}
	.yb {
		display: grid;
		grid-template-columns: 90px 1fr 230px;
		gap: 20px;
		align-items: center;
		margin-bottom: 14px;
	}
	.yb-l {
		font-size: 24px;
		color: var(--muted-p);
	}
	.yb-v {
		font-size: 28px;
		font-weight: 650;
		font-variant-numeric: tabular-nums;
	}
	.track {
		height: 40px;
		background: #eef2f6;
		border-radius: var(--r-sm);
		overflow: hidden;
	}
	.fill {
		height: 100%;
		border-radius: var(--r-sm);
	}
	.fill.plan {
		background: #b9d1ec;
	}
	.fill.fact {
		background: var(--navy-2);
	}
	.yr-note {
		font-size: 22px;
		color: var(--muted-p);
		margin-left: 110px;
	}
	.fin-figs {
		display: flex;
		flex-direction: column;
		gap: 44px;
	}
	.fin-figs .fig-v {
		font-size: 80px;
	}

	/* 6 — сонце */
	.so-grid {
		display: grid;
		grid-template-columns: 860px 1fr;
		gap: 64px;
		margin-top: 40px;
	}
	.kbox {
		display: flex;
		align-items: baseline;
		gap: 24px;
	}
	.k-big {
		font-family: var(--font-display);
		font-size: 40px;
		font-weight: 700;
		color: var(--navy);
		white-space: nowrap;
	}
	.k-f {
		font-size: 25px;
		color: var(--muted-p);
	}
	.so-figs {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 32px;
		margin: 24px 0 8px;
	}
	.so-left svg {
		width: auto;
		height: 230px;
	}
	.so-figs .fig-v {
		font-size: 64px;
	}
	.so-figs .demo {
		display: block;
		width: fit-content;
		margin: 10px 0 0;
	}
	.kb.ok {
		fill: var(--surplus);
	}
	.kb.low {
		fill: var(--deficit);
	}
	.kx {
		font-size: 22px;
		text-anchor: middle;
		fill: var(--muted-p);
	}
	.thr {
		stroke: var(--ink-p);
		stroke-width: 2;
		stroke-dasharray: 8 6;
	}
	.thr-t {
		font-size: 20px;
		text-anchor: end;
		fill: var(--ink-p);
		font-weight: 600;
	}
	.shot {
		margin: 0;
	}
	.shot img {
		width: 100%;
		height: 500px;
		object-fit: cover;
		object-position: 72% 60%;
		border-radius: var(--r-card);
		border: 1px solid #d6dce4;
		display: block;
	}
	.shot figcaption {
		font-size: 22px;
		color: var(--muted-p);
		margin-top: 12px;
	}

	/* 7 — економіка */
	.ec-grid {
		display: grid;
		grid-template-columns: 1fr 520px;
		gap: 96px;
		margin-top: 48px;
	}
	.params {
		border-collapse: collapse;
		width: 100%;
		font-size: 25px;
	}
	.params th,
	.params td {
		text-align: left;
		padding: 20px 20px 20px 0;
		border-bottom: 1px solid #e6ebf1;
		vertical-align: baseline;
	}
	.params th {
		font-weight: 500;
		color: var(--muted-p);
		width: 300px;
	}
	.params .pv {
		font-weight: 700;
		font-size: 30px;
		color: var(--navy);
		white-space: nowrap;
	}
	.params .ps {
		font-size: 21px;
		color: var(--muted-p);
	}
	.ec-res {
		display: flex;
		flex-direction: column;
		gap: 34px;
	}
	.formula {
		margin: 0;
		font-size: 25px;
		background: #fff4dc;
		border-left: 6px solid var(--sun);
		padding: 18px 24px;
		border-radius: 0 var(--r-btn) var(--r-btn) 0;
	}
	.ec-res .fig-v {
		font-size: 76px;
	}

	/* 8 — PoC */
	.poc {
		display: grid;
		grid-template-columns: 1.15fr 1fr;
		gap: 56px;
		margin-top: 52px;
	}
	.poc-col {
		border-radius: var(--r-card);
		padding: 40px 48px;
	}
	.poc-col.real {
		background: #e3f4e8;
	}
	.poc-col.real h3 {
		color: var(--surplus-ink);
	}
	.poc-col.demo-col {
		background: #fff4dc;
	}
	.poc-col.demo-col h3 {
		color: #8a4f00;
	}
	.poc ul {
		list-style: none;
		margin: 20px 0 0;
		padding: 0;
	}
	.poc li {
		display: grid;
		grid-template-columns: 260px 1fr;
		gap: 16px;
		padding: 13px 0;
		border-bottom: 1px solid rgba(15, 27, 45, 0.1);
		font-size: 25px;
	}
	.poc li span {
		color: var(--text-2);
	}

	/* 9 — план */
	.tl {
		list-style: none;
		padding: 0;
		margin: 80px 0 0;
		display: grid;
		grid-template-columns: repeat(5, 1fr);
		gap: 32px;
		position: relative;
	}
	.tl::before {
		content: '';
		position: absolute;
		left: 28px;
		right: 28px;
		top: 27px;
		height: 3px;
		background: #b9d1ec;
	}
	.tl li {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.dot {
		width: 56px;
		height: 56px;
		border-radius: 50%;
		background: var(--navy);
		color: #fff;
		display: grid;
		place-items: center;
		font-weight: 700;
		font-size: 26px;
		margin-bottom: 16px;
		position: relative;
	}
	.tl li:first-child .dot {
		background: var(--sun);
		color: var(--navy);
	}
	.when {
		font-size: 22px;
		color: var(--muted-p);
	}
	.tl b {
		font-size: 30px;
		line-height: 1.2;
		color: var(--navy);
	}
	.tx {
		font-size: 23px;
		line-height: 1.4;
		color: var(--text-2);
	}
	.closing {
		margin: auto 0 0;
		font-family: var(--font-display);
		font-size: 44px;
		font-weight: 650;
		color: var(--navy);
		border-left: 8px solid var(--sun);
		padding-left: 28px;
	}

	.t-tag {
		margin: 20px 0 0;
		font-size: 38px;
		font-weight: 500;
		color: #f5c060;
		letter-spacing: 0.005em;
	}

	/* 10 — масштабування */
	.grow {
		list-style: none;
		padding: 0;
		margin: 56px 0 0;
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 40px;
		flex: 1;
		margin-bottom: 40px;
	}
	.grow li {
		display: flex;
		flex-direction: column;
		background: var(--paper-2);
		border-top: 6px solid var(--navy);
		border-radius: 0 0 var(--r-card) var(--r-card);
		padding: 32px 36px;
	}
	.grow li:nth-child(3) {
		border-top-color: var(--sun);
	}
	.g-n {
		font-family: var(--font-display);
		font-size: 56px;
		font-weight: 750;
		color: var(--navy-2);
		line-height: 1;
		margin-bottom: 18px;
	}
	.grow h3 {
		font-size: 30px;
		line-height: 1.2;
	}
	.g-t {
		font-size: 23px;
		line-height: 1.4;
		color: var(--text-2);
		margin: 16px 0 0;
	}
	.g-v {
		margin-top: auto;
		padding-top: 20px;
		border-top: 1px solid #d6dce4;
		font-size: 22px;
		line-height: 1.4;
	}
	.g-v b {
		color: #8a4f00;
	}
	.g-v p {
		margin: 6px 0 0;
	}

	/* ——— Ревізія 2: бренд у куті, команда, піктограми, картки ——— */
	h2 {
		font-size: 58px;
		max-width: 1560px;
	}
	.corner {
		position: absolute;
		top: 40px;
		right: 120px;
		font-size: 20px;
		font-weight: 600;
		color: var(--muted-p);
		letter-spacing: 0.01em;
	}
	.k-title .corner {
		top: 214px;
		color: #9fb3cc;
	}
	.ico {
		fill: none;
		stroke: currentColor;
		stroke-width: 1.8;
		stroke-linecap: round;
		stroke-linejoin: round;
		display: block;
	}
	.card {
		background: var(--paper-2);
		border: 1px solid #d6dce4;
		border-radius: var(--r-card);
		padding: 32px 36px;
	}

	/* 1 */
	.t-body {
		padding: 64px 120px 0;
	}
	h1 {
		font-size: 120px;
	}
	.t-tag {
		margin-top: 16px;
		font-size: 34px;
	}
	.t-sub {
		margin-top: 28px;
		font-size: 38px;
	}
	.t-lead {
		margin-top: 16px;
		font-size: 28px;
	}
	.t-meta {
		padding: 0 120px;
		font-size: 24px;
	}
	.team {
		display: grid;
		grid-template-columns: repeat(5, 1fr);
		gap: 28px;
		margin: 26px 120px 110px;
		padding-top: 22px;
		border-top: 1px solid #23446f;
	}
	.tm b {
		display: block;
		font-size: 20px;
		color: #fff;
		line-height: 1.25;
	}
	.tm span {
		display: block;
		margin-top: 6px;
		font-size: 16px;
		line-height: 1.4;
		color: #b7c6da;
	}

	/* 2 */
	.stats {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 32px;
		margin-top: 28px;
	}
	.st {
		border-left: 4px solid var(--sun);
		padding-left: 18px;
	}
	.st-v {
		font-family: var(--font-display);
		font-size: 60px;
		font-weight: 700;
		line-height: 1;
		color: var(--navy);
		font-variant-numeric: tabular-nums;
	}
	.st-v small {
		font-size: 24px;
		font-weight: 600;
		margin-left: 8px;
	}
	.st-l {
		margin-top: 6px;
		font-size: 20px;
		color: var(--muted-p);
		line-height: 1.3;
	}
	.k-problem .p-grid {
		margin-top: 32px;
		gap: 56px;
	}
	.k-problem .p-problem {
		padding: 30px 40px;
	}
	.dash {
		list-style: none;
		margin: 14px 0 0;
		padding: 0;
	}
	.dash li {
		position: relative;
		font-size: 25px;
		line-height: 1.35;
		padding: 6px 0 6px 38px;
	}
	.dash li::before {
		content: '—';
		position: absolute;
		left: 0;
		color: var(--sun);
	}
	.k-problem .p-value ul {
		margin-top: 8px;
	}
	.k-problem .p-value li {
		font-size: 23px;
		padding: 7px 0 7px 32px;
	}
	.k-problem .p-value li::before {
		top: 17px;
	}
	.k-problem .users {
		display: grid;
		grid-template-columns: repeat(8, 1fr);
		gap: 14px;
		align-items: start;
		padding-top: 18px;
	}
	.k-problem .users-t {
		grid-column: 1 / -1;
		font-size: 24px;
		margin: 0;
	}
	.k-problem .user {
		background: none;
		padding: 0;
		border-radius: 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 10px;
		text-align: center;
	}
	.ava {
		position: relative;
		width: 72px;
		height: 72px;
		border-radius: 50%;
		background: #e8f1fb;
		display: grid;
		place-items: center;
		color: var(--navy-2);
	}
	.ava > svg {
		fill: none;
		stroke: currentColor;
		stroke-width: 3;
		stroke-linecap: round;
		width: 48px;
		height: 48px;
	}
	.badge {
		position: absolute;
		right: -8px;
		bottom: -4px;
		width: 34px;
		height: 34px;
		border-radius: 50%;
		background: var(--sun);
		color: var(--navy);
		display: grid;
		place-items: center;
		border: 3px solid #fff;
	}
	.user-l {
		font-size: 18px;
		line-height: 1.25;
		color: var(--ink-p);
	}

	/* 3 */
	.k-profile .pr-grid {
		grid-template-columns: 800px 1fr;
		gap: 64px;
		margin-top: 40px;
	}
	.k-profile .chart h3 {
		margin-bottom: 18px;
	}
	.defects {
		margin-top: auto;
		margin-bottom: 8px;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 14px 18px;
	}
	.def-t {
		width: 100%;
		font-size: 22px;
		color: var(--muted-p);
	}
	.def {
		display: flex;
		align-items: baseline;
		gap: 12px;
		background: #fdebe2;
		border-radius: var(--r-btn);
		padding: 10px 22px;
	}
	.def b {
		font-size: 36px;
		color: #9a330a;
		font-variant-numeric: tabular-nums;
	}
	.def span {
		font-size: 22px;
	}

	/* 4 */
	.k-flow .flow {
		margin-top: 32px;
	}
	.k-flow .node {
		height: 76px;
	}
	.k-flow .node.role {
		height: 56px;
		flex-direction: row;
		align-items: center;
		justify-content: flex-start;
		gap: 14px;
		font-size: 20px;
	}
	.role-ic {
		color: var(--navy-2);
		flex: none;
	}
	.roles-h {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.roles-h b {
		font-size: 30px;
		color: var(--navy);
		font-family: var(--font-display);
	}
	.roles-h span {
		font-size: 19px;
		line-height: 1.3;
		color: var(--muted-p);
	}
	.center {
		position: absolute;
		left: 680px;
		width: 440px;
		top: 0;
		bottom: 0;
	}
	.k-flow .core {
		position: relative;
		left: auto;
		top: auto;
		width: 100%;
		transform: none;
		padding: 30px 36px;
	}
	.frame.on .k-flow .core.r,
	.stacked .k-flow .core.r,
	.print .k-flow .core.r {
		transform: none;
	}
	.k-flow .core-t {
		font-size: 40px;
	}
	.k-flow .core ul {
		margin-top: 16px;
		font-size: 24px;
	}
	.k-flow .core li {
		padding: 5px 0;
	}
	.cstats {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 14px;
		margin-top: 20px;
	}
	.cstats .st {
		background: var(--paper-2);
		border-radius: var(--r-btn);
		padding: 14px 18px;
	}
	.cstats .st-v {
		font-size: 46px;
	}
	.cstats .st-l {
		font-size: 19px;
	}

	/* 6 */
	.k-solar .so-grid {
		grid-template-columns: 820px 1fr;
		gap: 56px;
		margin-top: 30px;
	}
	.k-solar .so-figs .fig-v {
		font-size: 56px;
	}
	.kchart {
		width: auto !important;
		height: 230px !important;
	}
	.so-right {
		display: flex;
		flex-direction: column;
		gap: 18px;
	}
	.k-solar .shot img {
		height: 320px;
		object-view-box: inset(3% 0 3% 16%);
		object-position: 50% 60%;
	}
	.k-solar .shot figcaption {
		margin-top: 8px;
		font-size: 19px;
	}
	.auto {
		display: grid;
		grid-template-columns: 290px 1fr;
		gap: 28px;
		align-items: center;
		padding: 22px 28px;
	}
	.auto-main {
		display: flex;
		gap: 14px;
		align-items: flex-start;
	}
	.auto-ic {
		color: var(--navy);
		margin-top: 2px;
	}
	.auto-t {
		font-size: 22px;
		font-weight: 650;
		color: var(--navy);
	}
	.auto-t .demo {
		margin-left: 8px;
		font-size: 14px;
	}
	.auto-v {
		font-family: var(--font-display);
		font-size: 84px;
		font-weight: 700;
		line-height: 1;
		color: var(--navy);
		margin-top: 6px;
	}
	.auto-v small {
		font-size: 30px;
		margin-left: 8px;
	}
	.auto-l {
		font-size: 17px;
		line-height: 1.35;
		color: var(--muted-p);
		margin-top: 6px;
	}
	.ab {
		display: grid;
		grid-template-columns: 190px 1fr 86px;
		gap: 12px;
		align-items: center;
		margin-bottom: 12px;
		font-size: 18px;
	}
	.ab-track {
		position: relative;
		height: 18px;
		background: #e2e8ef;
		border-radius: var(--r-sm);
	}
	.ab-fill {
		height: 100%;
		background: #0b5cad;
		border-radius: var(--r-sm);
	}
	.ab-goal {
		position: absolute;
		top: -5px;
		bottom: -5px;
		left: 80%;
		width: 3px;
		background: var(--ink-p);
	}
	.ab-v {
		font-weight: 650;
		text-align: right;
		font-variant-numeric: tabular-nums;
	}
	.ab-note {
		font-size: 16px;
		color: var(--muted-p);
	}

	/* 7 */
	.k-econ .ec-grid {
		margin-top: 36px;
		gap: 80px;
	}
	.k-econ .params th,
	.k-econ .params td {
		padding: 14px 20px 14px 0;
	}
	.k-econ .ec-res {
		gap: 22px;
	}
	.k-econ .ec-res .fig-v {
		font-size: 64px;
	}
	.plain {
		margin-top: auto;
		margin-bottom: 8px;
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 24px;
	}
	.plain-t {
		grid-column: 1 / -1;
		font-size: 22px;
		color: var(--muted-p);
	}
	.pl {
		display: flex;
		gap: 18px;
		align-items: flex-start;
		background: #fff4dc;
		border-radius: var(--r-card);
		padding: 20px 24px;
	}
	.pl-ic {
		flex: none;
		width: 56px;
		height: 56px;
		border-radius: 50%;
		background: #fff;
		color: #8a4f00;
		display: grid;
		place-items: center;
	}
	.pl b {
		display: block;
		font-size: 28px;
		color: var(--navy);
	}
	.pl span {
		display: block;
		font-size: 20px;
		line-height: 1.35;
		color: var(--text-2);
		margin-top: 4px;
	}

	/* 8 */
	.legend {
		display: flex;
		gap: 36px;
		margin-top: 24px;
		font-size: 22px;
		color: var(--text-2);
	}
	.lg {
		display: inline-block;
		width: 18px;
		height: 18px;
		border-radius: var(--r-sm);
		margin-right: 10px;
		vertical-align: -2px;
	}
	.lg.real,
	.cnt-b.real {
		background: #1a7f37;
	}
	.lg.dm,
	.cnt-b.dm {
		background: var(--sun);
	}
	.k-poc .poc {
		grid-template-columns: 1.3fr 1fr;
		gap: 40px;
		margin-top: 32px;
	}
	.k-poc .poc-col {
		background: var(--paper-2);
		padding: 36px 40px;
	}
	.k-poc .poc-col h3 {
		display: flex;
		align-items: center;
		gap: 16px;
	}
	.cnt-b {
		width: 52px;
		height: 52px;
		border-radius: 50%;
		display: grid;
		place-items: center;
		color: #fff;
		font-size: 26px;
	}
	.cnt-b.dm {
		color: #1a1200;
	}
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 14px;
		margin-top: 24px;
	}
	.chip {
		font-size: 24px;
		padding: 12px 20px;
		border-radius: var(--r-btn);
	}
	.chip.real {
		background: #e3f4e8;
		color: #14632b;
		border: 1px solid #a7d8b5;
	}
	.chip.dm {
		background: #fff4dc;
		color: #8a4f00;
		border: 1px solid #f5c060;
	}

	/* 9 */
	.tl li:nth-child(2) .dot {
		background: var(--navy);
	}
	.tl li:nth-child(3) .dot {
		background: #1a7f37;
	}
	.tl li:nth-child(4) .dot {
		background: #0b5cad;
	}
	.tl li:nth-child(5) .dot {
		background: #0f766e;
	}

	/* 10 */
	.k-growth .grow {
		grid-template-columns: 1.35fr 1fr;
		grid-template-rows: 1fr 1fr;
		gap: 28px;
		margin: 40px 0 36px;
	}
	.k-growth .grow li {
		border-top: none;
		border-radius: var(--r-card);
		padding: 26px 34px;
	}
	.k-growth .grow li.g1 {
		grid-row: 1 / span 2;
		background: var(--navy);
		color: #fff;
		padding: 48px 52px;
	}
	.k-growth .grow li.g2 {
		background: #e8f1fb;
	}
	.k-growth .grow li.g3 {
		background: #f1f6fc;
	}
	.k-growth .g-n {
		font-size: 34px;
		margin-bottom: 8px;
	}
	.k-growth .g1 .g-n {
		font-size: 72px;
		color: var(--sun);
		margin-bottom: 24px;
	}
	.k-growth .grow h3 {
		font-size: 26px;
	}
	.k-growth .g1 h3 {
		font-size: 42px;
		line-height: 1.15;
		color: #fff;
	}
	.k-growth .g-t {
		font-size: 18px;
		margin-top: 10px;
	}
	.k-growth .g1 .g-t {
		font-size: 26px;
		line-height: 1.45;
		color: #d5e0ee;
		margin-top: 24px;
	}
	.k-growth .g-v {
		margin-top: auto;
		padding-top: 14px;
		border-top: none;
		display: flex;
		flex-wrap: wrap;
		gap: 10px;
	}
	.gchip {
		font-size: 18px;
		padding: 6px 14px;
		border-radius: var(--r-btn);
		background: #fff;
		color: var(--navy-2);
		border: 1px solid #b9d1ec;
	}
	.g1 .gchip {
		font-size: 22px;
		padding: 10px 18px;
		background: #173a64;
		color: #fff;
		border-color: #2f5788;
	}
	@media print {
		.k-flow .core {
			transform: none !important;
		}
	}

	/* Ревізія 3: титул = повний банер хакатону зліва + назва справа, команда внизу */
	.t-grid {
		display: grid;
		grid-template-columns: 1000px 1fr;
		gap: 56px;
		padding: 80px 120px 0;
		align-items: start;
	}
	.t-banner {
		display: block;
		width: 1000px;
		height: 563px;
		object-fit: contain;
		background: #000;
		border-radius: var(--r-card);
		box-shadow: 0 6px 24px rgba(0, 0, 0, 0.35);
	}
	.t-right {
		display: flex;
		flex-direction: column;
		min-height: 563px;
	}
	.k-title .city {
		gap: 20px;
	}
	.k-title .city img {
		height: 72px;
		margin-bottom: 20px;
	}
	.k-title h1 {
		font-size: 84px;
		line-height: 1;
	}
	.k-title .t-tag {
		margin-top: 18px;
		font-size: 27px;
		line-height: 1.3;
	}
	.k-title .t-sub {
		margin-top: 26px;
		font-size: 28px;
		line-height: 1.3;
	}
	.k-title .t-lead {
		margin-top: 14px;
		font-size: 22px;
		line-height: 1.4;
	}
	.k-title .t-meta {
		margin-top: auto;
		padding: 0;
		font-size: 19px;
		line-height: 1.4;
	}
	.k-title .corner {
		top: 34px;
	}
	.k-title .team {
		margin-top: auto;
	}
	.tl li:nth-child(6) .dot {
		background: #8a4f00;
	}
	.tl {
		gap: 26px;
	}
	.tl b {
		font-size: 27px;
	}
	.tx {
		font-size: 21px;
	}

	/* Панель керування */
	.bar {
		position: absolute;
		left: 0;
		right: 0;
		bottom: 0;
		height: 64px;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 12px;
		color: #c9d6e8;
		font-size: 15px;
	}
	.prog {
		position: absolute;
		left: 0;
		right: 0;
		top: 0;
		height: 3px;
		background: #1b2f4a;
	}
	.prog div {
		height: 100%;
		background: var(--sun);
		transition: width 440ms var(--ease-out);
	}
	.bar button {
		font: inherit;
		color: #fff;
		background: #18304f;
		border: 1px solid #2a4a74;
		border-radius: var(--r-btn);
		padding: 8px 14px;
		cursor: pointer;
		min-height: 40px;
	}
	.bar button:disabled {
		opacity: 0.4;
		cursor: default;
	}
	.bar button:hover:not(:disabled) {
		background: #22406a;
	}
	.bar .pdf {
		background: var(--sun);
		color: #1a1200;
		border-color: var(--sun);
		font-weight: 600;
		margin-left: 12px;
	}
	.bar .pdf:hover {
		background: var(--sun-strong);
	}
	.cnt {
		min-width: 64px;
		text-align: center;
		font-variant-numeric: tabular-nums;
	}

	/* Вузький екран: слайди один під одним */
	.deck.stacked {
		position: static;
		min-height: 100vh;
		overflow: visible;
		padding: 16px 16px 88px;
		box-sizing: border-box;
	}
	.stacked .stage {
		position: static;
		transform: none;
		width: auto;
		height: auto;
		display: flex;
		flex-direction: column;
		gap: 16px;
	}
	.stacked .frame {
		position: relative;
		inset: auto;
		opacity: 1;
		visibility: visible;
		transform: none;
		width: calc(1920px * var(--s));
		height: calc(1080px * var(--s));
		overflow: hidden;
		border-radius: 6px;
	}
	.stacked .bar {
		position: fixed;
		background: #0a1626;
	}

	@media (prefers-reduced-motion: reduce) {
		.frame,
		.frame.on,
		.r,
		.prog div {
			transition: none !important;
		}
	}

	/* Друк і ?print=1: кожен слайд — окрема сторінка 1920×1080 */
	@page {
		size: 1920px 1080px;
		margin: 0;
	}
	.deck.print,
	.deck.print .stage,
	.deck.print .frame {
		position: static;
		transform: none;
		width: 1920px;
		height: auto;
		overflow: visible;
		background: #fff;
	}
	.deck.print .frame,
	.deck.print .slide {
		opacity: 1;
		visibility: visible;
		transition: none;
		transform: none;
	}
	.deck.print .frame {
		height: 1080px;
		position: relative;
	}
	@media print {
		:global(html),
		:global(body) {
			margin: 0 !important;
			padding: 0 !important;
			background: #fff !important;
		}
		.deck,
		.stage,
		.frame {
			position: static !important;
			transform: none !important;
			width: 1920px !important;
			height: auto !important;
			min-height: 0 !important;
			padding: 0 !important;
			overflow: visible !important;
			background: #fff !important;
			display: block !important;
		}
		.frame {
			height: 1080px !important;
			position: relative !important;
			opacity: 1 !important;
			visibility: visible !important;
			break-after: page;
			page-break-after: always;
			border-radius: 0 !important;
		}
		.frame:last-child {
			break-after: auto;
			page-break-after: auto;
		}
		.slide {
			transform: none !important;
		}
		.r,
		.frame,
		.prog div {
			transition: none !important;
			opacity: 1 !important;
		}
		.r:not(.core) {
			transform: none !important;
		}
		.bar {
			display: none !important;
		}
		* {
			-webkit-print-color-adjust: exact !important;
			print-color-adjust: exact !important;
			animation: none !important;
		}
	}
</style>
