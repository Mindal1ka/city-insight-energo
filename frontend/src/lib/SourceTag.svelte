<!-- Позначка походження даних: реальні (UMUNI / openbudget) · МОК · оцінка -->
<script lang="ts">
	let {
		kind,
		label,
		href,
		title
	}: { kind: 'umuni' | 'openbudget' | 'mok' | 'manual' | 'estimate'; label?: string; href?: string; title?: string } = $props();

	const text = $derived(
		label ?? { umuni: 'UMUNI', openbudget: 'openbudget.gov.ua', mok: 'ДЕМО', manual: 'введено вручну', estimate: 'оцінка' }[kind]
	);
	const link = $derived(href ?? (kind === 'openbudget' ? 'https://openbudget.gov.ua/local-budget?id=1657010000' : undefined));
	const tip = $derived(
		title ??
			{
				umuni: 'Реальні дані UMUNI',
				openbudget: 'Реальні дані openbudget.gov.ua',
				mok: 'Демонстраційні (змодельовані) дані, не фактичні',
				manual: 'Введено вручну',
				estimate: 'Оцінка'
			}[kind]
	);
</script>

{#if link}
	<a class="st {kind}" href={link} target="_blank" rel="noopener noreferrer" title={tip}>{text}</a>
{:else}
	<span class="st {kind}" title={tip}>{text}</span>
{/if}

<style>
	.st {
		display: inline-flex;
		align-items: center;
		padding: 0.05rem 0.5rem;
		border-radius: var(--r-pill);
		font-size: 0.7rem;
		font-weight: 700;
		letter-spacing: 0.02em;
		white-space: nowrap;
		text-decoration: none;
		cursor: help;
		background: var(--neutral-soft);
		color: var(--muted);
	}
	a.st {
		cursor: pointer;
	}
	a.st:hover {
		text-decoration: underline;
	}
	.umuni,
	.openbudget {
		background: var(--ok-soft);
		color: var(--ok);
	}
	.mok {
		background: var(--sun-soft);
		color: var(--sun-ink);
		border: 1px dashed #d08a1c;
	}
	.estimate {
		background: var(--accent-soft);
		color: var(--cons);
	}
</style>
