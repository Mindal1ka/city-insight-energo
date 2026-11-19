<script lang="ts">
	// Використання ліміту: «використано / ліміт», смуга прогресу, попередження при перевищенні
	import { num } from './format.ts';
	import Icon from './Icon.svelte';

	let {
		label,
		used,
		limit,
		unit,
		pct = null,
		over = false,
		digits = 0,
		hint = ''
	}: {
		label: string;
		used: number;
		limit: number;
		unit: string;
		pct?: number | null;
		over?: boolean;
		digits?: number;
		hint?: string;
	} = $props();

	const p = $derived(pct ?? (limit > 0 ? (used / limit) * 100 : null));
	const level = $derived(
		p === null ? 'none' : over || p > 100 ? 'over' : p >= 85 ? 'near' : 'ok'
	);
</script>

<div class="meter {level}">
	<div class="top">
		<span class="label">{label}</span>
		<span class="pct tnum">{p === null ? '—' : `${num(p, 0)} %`}</span>
	</div>
	<p class="vals">
		<span class="big-num used">{num(used, digits)}</span>
		<span class="of">з {num(limit, digits)} {unit}</span>
	</p>
	<div
		class="bar"
		role="meter"
		aria-label={label}
		aria-valuemin="0"
		aria-valuemax={limit || 1}
		aria-valuenow={Math.min(used, limit || used)}
		aria-valuetext="{num(used, digits)} з {num(limit, digits)} {unit}"
	>
		<span class="fill" style="width: {Math.min(100, p ?? 0)}%"></span>
		<span class="mark" style="left: 85%" aria-hidden="true"></span>
	</div>
	{#if level === 'over'}
		<p class="msg"><Icon name="alert" size={16} /> Ліміт перевищено на {num(used - limit, digits)} {unit}</p>
	{:else if level === 'near'}
		<p class="msg"><Icon name="alert" size={16} /> Наближається до ліміту: лишилось {num(limit - used, digits)} {unit}</p>
	{:else if p !== null}
		<p class="msg"><Icon name="check" size={16} /> У межах ліміту: лишилось {num(limit - used, digits)} {unit}</p>
	{:else}
		<p class="msg">Ліміт не встановлено</p>
	{/if}
	{#if hint}<p class="hint">{hint}</p>{/if}
</div>

<style>
	.top {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 0.5rem;
	}
	.label {
		font-weight: 600;
		color: #2b3645;
	}
	.pct {
		font-weight: 700;
		font-size: 0.95rem;
	}
	.vals {
		margin: 0.2rem 0 0.55rem;
		display: flex;
		align-items: baseline;
		gap: 0.45rem;
		flex-wrap: wrap;
	}
	.used {
		font-size: 1.9rem;
	}
	.of {
		color: var(--muted);
		font-weight: 500;
	}
	.bar {
		position: relative;
		height: 12px;
		border-radius: 999px;
		background: #e8edf3;
		overflow: hidden;
	}
	.fill {
		position: absolute;
		inset: 0 auto 0 0;
		border-radius: 999px;
		background: linear-gradient(90deg, #2f6db0, #1f4f84);
		transition: width 0.8s var(--ease);
	}
	.mark {
		position: absolute;
		top: 0;
		bottom: 0;
		width: 2px;
		background: rgba(255, 255, 255, 0.9);
	}
	.near .fill {
		background: linear-gradient(90deg, #f5a524, #e08a00);
	}
	.over .fill {
		background: repeating-linear-gradient(-45deg, #c2410c 0 8px, #a8370a 8px 16px);
	}
	.msg {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		margin: 0.55rem 0 0;
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--surplus-ink);
	}
	.near .msg {
		color: var(--sun-ink);
	}
	.over .msg {
		color: var(--deficit-ink);
	}
	.none .msg {
		color: var(--muted);
		font-weight: 500;
	}
	.over .pct {
		color: var(--deficit-ink);
	}
	.hint {
		margin: 0.25rem 0 0;
		font-size: 0.8125rem;
		color: var(--muted);
	}
</style>
