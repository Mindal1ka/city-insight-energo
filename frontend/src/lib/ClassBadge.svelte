<script lang="ts">
	// Бейдж класу: літера + текст, колір лише допоміжний (WCAG 1.4.1)
	import { classInfo } from './classes.ts';

	let { cls, short = false }: { cls: string | null | undefined; short?: boolean } = $props();
	const info = $derived(classInfo(cls));
</script>

{#if info}
	<span class="badge cls-{info.letter}" title="Клас {info.letter} — {info.text} (умовна оцінка)">
		<b>{info.letter}</b>{#if !short}<span class="txt"> — {info.text}</span>{/if}
	</span>
{:else}
	<span class="muted">немає класу</span>
{/if}

<style>
	.badge {
		display: inline-flex;
		align-items: baseline;
		gap: 0.15em;
		padding: 0.1rem 0.5rem;
		border-radius: 999px;
		border: 1px solid var(--c-fg);
		background: var(--c-bg);
		color: var(--c-fg);
		font-size: 0.875rem;
		line-height: 1.5;
		white-space: nowrap;
	}
	b {
		font-weight: 700;
	}
</style>
