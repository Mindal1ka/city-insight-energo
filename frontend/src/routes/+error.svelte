<script lang="ts">
	// Сторінка помилки (404 та інші) — українською, з виходом на головні розділи.
	import { page } from '$app/state';
	import Icon from '#lib/Icon.svelte';

	const notFound = $derived(page.status === 404);
</script>

<svelte:head><title>{notFound ? 'Сторінку не знайдено' : 'Помилка'} · City Insight Map · Енергія</title></svelte:head>

<section class="err-page" aria-labelledby="err-h">
	<span class="code" aria-hidden="true">{page.status}</span>
	<h1 id="err-h">{notFound ? 'Такої сторінки немає' : 'Щось пішло не так'}</h1>
	<p class="lead">
		{#if notFound}
			Можливо, посилання застаріло або в адресі помилка. Будівлю можна знайти через пошук чи на мапі.
		{:else}
			Не вдалося показати сторінку{page.error?.message ? `: ${page.error.message}` : ''}. Спробуйте оновити її
			або поверніться на головну.
		{/if}
	</p>
	<div class="acts">
		<a class="btn" href="/"><Icon name="building" size={18} /> До переліку об’єктів</a>
		<a class="btn btn-secondary" href="/map"><Icon name="pin" size={18} /> Відкрити мапу</a>
	</div>
</section>

<style>
	.err-page {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.5rem;
		max-width: 40rem;
		margin: 2rem auto 3rem;
		padding: 2rem;
		background: var(--surface);
		border: 1px solid var(--card-line);
		border-radius: var(--radius-xl);
		box-shadow: var(--shadow-md);
	}
	.code {
		font-family: var(--font-display);
		font-size: 3.5rem;
		font-weight: 800;
		line-height: 1;
		letter-spacing: -0.04em;
		background: linear-gradient(90deg, var(--navy-3), var(--sun-strong));
		-webkit-background-clip: text;
		background-clip: text;
		color: transparent;
	}
	h1 {
		margin: 0.25rem 0 0;
	}
	.lead {
		margin: 0 0 0.75rem;
	}
	.acts {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem;
	}
	@media (max-width: 640px) {
		.err-page {
			margin: 0.5rem 0 1.5rem;
			padding: 1.25rem;
		}
		.code {
			font-size: 2.75rem;
		}
		.acts,
		.acts .btn {
			width: 100%;
		}
	}
</style>
