<!--
	СТАНДАРТНА ПРОСТА КАРТКА ПОКАЗНИКА: назва → велике анімоване число → одне речення пояснення.
	Стан (tone) показано кольором І значком І прихованим текстом — ніколи лише кольором.

	ВИКОРИСТАННЯ
	  import StatCard from '#lib/StatCard.svelte';
	  <div class="stat-grid">                                   // готова адаптивна сітка з app.css
	    <StatCard label="Будівель у громаді" value={312} icon="building"
	              hint="Школи, садочки, лікарні та адмінбудівлі." />
	    <StatCard label="Споживання за рік" value={4.8} decimals={1} unit="млн кВт·год"
	              tone="warn" hint="На 6 % більше, ніж торік." href="/overview" />
	    <StatCard label="Тримає без світла" value={14} unit="год" tone="good" demo
	              hint="Стільки школа № 5 протримається на батареї." />
	  </div>

	Props:
	  label: string                       — коротка назва (2–4 слова)
	  value: number | null                — null → «—»
	  unit?: string                       — одиниця біля числа
	  decimals?: number = 0
	  hint?: string                       — ОДНЕ просте речення
	  tone?: 'neutral'|'good'|'warn'|'bad' = 'neutral'
	  icon?: назва з Icon.svelte          — значок категорії ('building','sun','battery','bolt',…)
	  href?: string                       — уся картка стає посиланням (стрілка при наведенні)
	  demo?: boolean                      — маленька позначка «ДЕМО» (змодельовані дані)
	  format?: (n:number)=>string         — власне форматування числа (необов'язково)
	  toneLabel?: string                  — текст стану для екранних зчитувачів (типово «добре»/«увага»/«погано»)
	  children?: snippet                  — необов'язковий маленький додаток під текстом (напр. Meter)
-->
<script lang="ts">
	import type { ComponentProps, Snippet } from 'svelte';
	import Icon from './Icon.svelte';
	import CountUp from './CountUp.svelte';

	type IconName = ComponentProps<typeof Icon>['name'];
	type Tone = 'neutral' | 'good' | 'warn' | 'bad';

	let {
		label,
		value,
		unit = '',
		decimals = 0,
		hint = '',
		tone = 'neutral',
		icon,
		href,
		demo = false,
		format,
		toneLabel,
		children
	}: {
		label: string;
		value: number | null | undefined;
		unit?: string;
		decimals?: number;
		hint?: string;
		tone?: Tone;
		icon?: IconName;
		href?: string;
		demo?: boolean;
		format?: (n: number) => string;
		toneLabel?: string;
		children?: Snippet;
	} = $props();

	const TONE_TEXT: Record<Tone, string> = {
		neutral: '',
		good: 'добре',
		warn: 'потребує уваги',
		bad: 'погано'
	};
	const srTone = $derived(toneLabel ?? TONE_TEXT[tone]);

	// На телефоні пояснення обрізане до 2 рядків — дотик по картці розгортає його
	// (екранні зчитувачі завжди отримують повний текст: обрізання лише візуальне)
	let open = $state(false);
</script>

{#snippet body()}
	<span class="sc-top">
		{#if icon}
			<span class="sc-ico" aria-hidden="true"><Icon name={icon} size={20} /></span>
		{/if}
		<span class="sc-label">{label}</span>
		{#if demo}
			<span class="sc-demo" title="Змодельовані (демонстраційні) дані">ДЕМО</span>
		{/if}
	</span>

	<span class="sc-value">
		<span class="sc-num"><CountUp {value} {decimals} {format} /></span>
		{#if unit && value !== null && value !== undefined}<span class="sc-unit">{unit}</span>{/if}
		{#if tone !== 'neutral'}
			<span class="sc-tone" aria-hidden="true">
				{#if tone === 'good'}
					<svg viewBox="0 0 20 20" width="18" height="18"><path d="m5.5 10.5 3 3 6-7" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" /></svg>
				{:else if tone === 'warn'}
					<svg viewBox="0 0 20 20" width="18" height="18"><path d="M10 5.5v5.5" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" /><circle cx="10" cy="14.6" r="1.4" fill="currentColor" /></svg>
				{:else}
					<svg viewBox="0 0 20 20" width="18" height="18"><path d="m6.5 6.5 7 7m0-7-7 7" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" /></svg>
				{/if}
			</span>
			<span class="visually-hidden">({srTone})</span>
		{/if}
	</span>

	{#if hint}<span class="sc-hint">{hint}</span>{/if}
	{#if children}<span class="sc-extra">{@render children()}</span>{/if}

	{#if href}
		<span class="sc-go" aria-hidden="true">
			<svg viewBox="0 0 20 20" width="18" height="18"><path d="M4 10h11m-4.5-4.5L15 10l-4.5 4.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" /></svg>
		</span>
	{/if}
{/snippet}

{#if href}
	<a class="sc tone-{tone} is-link" {href}>{@render body()}</a>
{:else}
	<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions (лише візуальне розгортання підказки) -->
	<div class="sc tone-{tone}" class:open onclick={() => hint && (open = !open)}>{@render body()}</div>
{/if}

<style>
	.sc {
		--t-fg: var(--navy-3, #1f4f84);
		--t-bg: var(--accent-soft, #e6f0fa);
		--t-line: transparent;
		position: relative;
		display: flex;
		flex-direction: column;
		gap: 0.55rem;
		min-width: 0;
		padding: 1.15rem 1.25rem 1.2rem;
		background: var(--surface, #fff);
		border: 1px solid var(--card-line, #e3e8ef);
		border-radius: var(--radius-lg, 16px);
		box-shadow: var(--shadow, 0 1px 2px rgba(16, 24, 40, 0.06));
		color: var(--text);
		text-decoration: none;
		overflow: hidden;
		isolation: isolate;
		transition:
			transform var(--dur-base, 240ms) var(--ease-out, ease),
			box-shadow var(--dur-base, 240ms) var(--ease-out, ease),
			border-color var(--dur-base, 240ms);
	}
	/* Тонка кольорова смуга зверху — підсилює стан, але значок і текст лишаються головними */
	.sc::before {
		content: '';
		position: absolute;
		inset: 0 0 auto 0;
		height: 3px;
		background: var(--t-line);
	}
	.tone-good {
		--t-fg: var(--surplus-ink, #14632b);
		--t-bg: var(--surplus-soft, #e3f4e8);
		--t-line: var(--surplus, #1a7f37);
	}
	.tone-warn {
		--t-fg: var(--sun-ink, #8a4f00);
		--t-bg: var(--sun-soft, #fff4dc);
		--t-line: var(--sun, #f5a524);
	}
	.tone-bad {
		--t-fg: var(--deficit-ink, #9a330a);
		--t-bg: var(--deficit-soft, #fdebe2);
		--t-line: var(--deficit, #c2410c);
	}
	.sc:hover {
		transform: translateY(-2px);
		box-shadow: var(--shadow-md, 0 6px 18px -6px rgba(16, 24, 40, 0.16));
		border-color: var(--card-line-hover, #d3dbe5);
	}
	.is-link {
		cursor: pointer;
	}
	.is-link:hover {
		color: var(--text);
		border-color: color-mix(in srgb, var(--accent) 35%, transparent);
	}
	.is-link:active {
		transform: translateY(0) scale(0.99);
		transition-duration: 80ms;
	}
	.sc-top {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		min-width: 0;
	}
	.sc-ico {
		display: grid;
		place-items: center;
		width: 2.25rem;
		height: 2.25rem;
		border-radius: 10px;
		background: var(--t-bg);
		color: var(--t-fg);
		flex: none;
	}
	.sc-label {
		flex: 1;
		min-width: 0;
		font-size: 0.95rem;
		font-weight: 600;
		color: var(--text-2, #3a4656);
		line-height: 1.3;
	}
	.sc-demo {
		flex: none;
		align-self: flex-start;
		padding: 0.05rem 0.45rem;
		border-radius: 999px;
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		color: var(--sun-ink, #8a4f00);
		background: var(--sun-soft, #fff4dc);
		border: 1px dashed #d08a1c;
		cursor: help;
	}
	.sc-value {
		display: flex;
		align-items: baseline;
		flex-wrap: wrap;
		gap: 0.1rem 0.4rem;
		line-height: 1;
	}
	.sc-num {
		font-size: var(--fs-stat, 2.25rem);
		font-weight: 700;
		letter-spacing: -0.025em;
		color: var(--ink, #0f1b2d);
	}
	.sc-unit {
		font-size: 1rem;
		font-weight: 600;
		color: var(--muted);
	}
	.sc-tone {
		align-self: center;
		display: grid;
		place-items: center;
		width: 1.6rem;
		height: 1.6rem;
		margin-left: 0.15rem;
		border-radius: 50%;
		background: var(--t-bg);
		color: var(--t-fg);
		box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--t-line) 45%, transparent);
	}
	.sc-hint {
		font-size: 0.9375rem;
		line-height: 1.45;
		color: var(--muted);
		max-width: 46ch;
	}
	.sc-extra {
		display: block;
		margin-top: 0.15rem;
	}
	.sc-go {
		position: absolute;
		right: 1rem;
		bottom: 1rem;
		display: grid;
		place-items: center;
		width: 2rem;
		height: 2rem;
		border-radius: 50%;
		background: var(--accent-soft);
		color: var(--accent);
		opacity: 0;
		transform: translateX(-6px);
		transition:
			opacity var(--dur-base, 240ms) var(--ease-out, ease),
			transform var(--dur-base, 240ms) var(--ease-out, ease);
	}
	.is-link:hover .sc-go,
	.is-link:focus-visible .sc-go {
		opacity: 1;
		transform: none;
	}
	.is-link .sc-hint {
		padding-right: 2rem;
	}
	/* Сенсорні екрани без hover: стрілку посилання видно завжди */
	@media (hover: none) {
		.sc-go {
			opacity: 0.6;
			transform: none;
		}
		.sc:hover {
			transform: none;
		}
	}
	/* --- Телефон: компактна картка для сітки 2×N --- */
	@media (max-width: 640px) {
		.sc {
			gap: 0.4rem;
			padding: 12px 12px 12px;
			border-radius: 14px;
		}
		.sc:hover {
			transform: none;
		}
		.sc-top {
			gap: 0.45rem;
			align-items: flex-start;
		}
		.sc-ico {
			width: 1.75rem;
			height: 1.75rem;
			border-radius: 8px;
		}
		.sc-ico :global(svg) {
			width: 16px;
			height: 16px;
		}
		.sc-label {
			font-size: 0.8125rem;
			line-height: 1.25;
			align-self: center;
			display: -webkit-box;
			-webkit-box-orient: vertical;
			-webkit-line-clamp: 2;
			line-clamp: 2;
			overflow: hidden;
		}
		.sc-demo {
			font-size: 0.75rem;
			padding: 0 0.35rem;
			letter-spacing: 0.04em;
		}
		.sc-num {
			font-size: var(--fs-stat, 1.6rem);
		}
		.sc-unit {
			font-size: 0.8125rem;
		}
		.sc-tone {
			width: 1.25rem;
			height: 1.25rem;
		}
		.sc-tone :global(svg) {
			width: 14px;
			height: 14px;
		}
		.sc-hint {
			font-size: 0.8125rem;
			line-height: 1.4;
			display: -webkit-box;
			-webkit-box-orient: vertical;
			-webkit-line-clamp: 2;
			line-clamp: 2;
			overflow: hidden;
		}
		.open .sc-hint {
			-webkit-line-clamp: unset;
			line-clamp: none;
		}
		.sc-go {
			right: 8px;
			bottom: 8px;
			width: 1.5rem;
			height: 1.5rem;
			opacity: 0.85;
			transform: none;
		}
		.sc-go svg {
			width: 14px;
			height: 14px;
		}
		.is-link .sc-hint {
			padding-right: 1.5rem;
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.sc,
		.sc-go {
			transition: none;
		}
		.sc:hover,
		.is-link:active {
			transform: none;
		}
	}
	@media print {
		.sc {
			box-shadow: none;
			border-color: #999;
			break-inside: avoid;
		}
	}
</style>
