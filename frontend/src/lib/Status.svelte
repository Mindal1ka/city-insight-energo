<script lang="ts">
	// Стан завантаження або помилки для сторінок, що чекають дані з API
	let {
		loading = false,
		error = null,
		retry
	}: { loading?: boolean; error?: string | null; retry?: () => void } = $props();
</script>

{#if loading}
	<p class="status" role="status" aria-live="polite">
		<span class="spinner" aria-hidden="true"></span> Завантаження даних…
	</p>
{:else if error}
	<div class="notice notice-error" role="alert">
		<p><strong>Не вдалося отримати дані.</strong> {error}</p>
		{#if retry}<button type="button" class="btn" onclick={retry}>Спробувати ще раз</button>{/if}
	</div>
{/if}

<style>
	.status {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		color: var(--muted);
		padding: 2rem 0;
	}
	.spinner {
		width: 1.1rem;
		height: 1.1rem;
		border: 2px solid var(--line);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.spinner {
			animation: none;
		}
	}
</style>
