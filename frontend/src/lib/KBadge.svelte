<!--
	K-бейдж: значення K + клас (колір + значок + коротке слово). Колір ніколи не єдиний сигнал.
	<KBadge k={0.94} cls="Ефективно" />            → «✓ 0,94 Ефективно»
	<KBadge cls="Без СЕС" size="sm" />             → «○ Без СЕС»
	<KBadge k={1.4} cls="Надлишок" showWord={false} />
	Розміри: sm (у рядку таблиці), md (картка), lg (шапка об'єкта).
-->
<script lang="ts">
	import { kClassMeta, kText, type KClass } from './api-ses.ts';

	let {
		k = null,
		cls,
		size = 'md',
		showWord = true,
		showK = true
	}: {
		k?: number | null;
		cls: KClass | null | undefined;
		size?: 'sm' | 'md' | 'lg';
		showWord?: boolean;
		showK?: boolean;
	} = $props();

	const m = $derived(kClassMeta(cls ?? 'Немає даних'));
	const hasK = $derived(showK && k != null && isFinite(k));
	const label = $derived(`${hasK ? `Покриття сонцем ${kText(k)}, ` : ''}${m.short}`);
</script>

<span
	class="kb {size}"
	style="--c: {m.color}; --soft: {m.soft}; --ink: {m.ink}"
	role="img"
	aria-label={label}
	title={label}
>
	<span class="ico" aria-hidden="true">{m.icon}</span>
	{#if hasK}<span class="k" aria-hidden="true">{kText(k)}</span>{/if}
	{#if showWord}<span class="w" aria-hidden="true">{m.short}</span>{/if}
</span>

<style>
	.kb {
		display: inline-flex;
		align-items: center;
		gap: 0.35em;
		padding: 0.2em 0.6em 0.2em 0.25em;
		border-radius: 999px;
		background: var(--soft);
		color: #1a2433;
		font-weight: 600;
		line-height: 1.2;
		white-space: nowrap;
		border: 1px solid color-mix(in srgb, var(--c) 35%, transparent);
		font-variant-numeric: tabular-nums;
	}
	.ico {
		display: inline-grid;
		place-items: center;
		width: 1.45em;
		height: 1.45em;
		border-radius: 50%;
		background: var(--c);
		color: var(--ink);
		font-size: 0.85em;
		font-weight: 800;
		flex: none;
	}
	.k {
		font-weight: 800;
		color: #0f1b2d;
	}
	.w {
		color: #36425a;
		font-weight: 600;
	}
	.sm {
		font-size: 0.78rem;
	}
	.md {
		font-size: 0.875rem;
	}
	.lg {
		font-size: 1.05rem;
		padding: 0.3em 0.8em 0.3em 0.3em;
	}
	.lg .k {
		font-size: 1.25em;
	}
	.kb:not(:has(.k)):not(:has(.w)) {
		padding: 0.15em;
	}
</style>
