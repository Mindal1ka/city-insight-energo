<script lang="ts">
	import '../app.css';
	import favicon from '#lib/assets/favicon.svg';
	import { page } from '$app/state';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();

	// Пункти верхнього меню
	const nav = [
		{ href: '/', label: 'Огляд' },
		{ href: '/rating', label: 'Рейтинг будівель' },
		{ href: '/defects', label: 'Якість даних' },
		{ href: '/solar', label: 'Нові СЕС' },
		{ href: '/upload', label: 'Оновити дані' }
	];

	function isActive(href: string): boolean {
		const p = page.url.pathname;
		if (href === '/') return p === '/';
		// Картка будівлі логічно належить до рейтингу
		if (href === '/rating' && p.startsWith('/building/')) return true;
		return p === href || p.startsWith(href + '/');
	}
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>City Insight Map · Енергія</title>
</svelte:head>

<a class="skip no-print" href="#main">Перейти до змісту</a>

<header class="site-header no-print">
	<div class="wrap head-row">
		<a class="brand" href="/">
			<span class="logo" aria-hidden="true">⚡</span>
			<span>
				<span class="brand-name">City Insight Map · Енергія</span>
				<span class="brand-sub">Полтавська громада · енергоменеджмент</span>
			</span>
		</a>
		<!-- Місце для імені та ролі користувача (вхід і ролі додамо пізніше) -->
		<div class="user" aria-label="Користувач">
			<span class="user-role">Енергоменеджер громади</span>
			<span class="user-note">демо, без входу</span>
		</div>
	</div>
	<nav class="wrap" aria-label="Основне меню">
		<ul>
			{#each nav as item (item.href)}
				<li>
					<a href={item.href} aria-current={isActive(item.href) ? 'page' : undefined}>{item.label}</a>
				</li>
			{/each}
		</ul>
	</nav>
</header>

<main id="main" class="wrap" tabindex="-1">
	{@render children()}
</main>

<footer class="site-footer">
	<div class="wrap">
		<p>
			Аналітична оцінка на даних UMUNI. Не є офіційним енергосертифікатом.
		</p>
		<p class="muted small no-print">Poltava Open Data Hackathon · трек 2 «Енергетичний менеджмент»</p>
	</div>
</footer>

<style>
	:global(.wrap) {
		max-width: 1280px;
		margin: 0 auto;
		padding: 0 1.5rem;
	}
	@media (max-width: 700px) {
		:global(.wrap) {
			padding: 0 1rem;
		}
	}
	.skip {
		position: absolute;
		left: -9999px;
		top: 0.5rem;
		background: #fff;
		padding: 0.5rem 1rem;
		z-index: 100;
	}
	.skip:focus {
		left: 0.5rem;
	}
	.site-header {
		background: #0f2f52;
		color: #fff;
	}
	.head-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
		padding-top: 0.9rem;
		padding-bottom: 0.6rem;
	}
	.brand {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		color: #fff;
		text-decoration: none;
	}
	.brand:hover {
		color: #fff;
	}
	.logo {
		display: grid;
		place-items: center;
		width: 2.4rem;
		height: 2.4rem;
		border-radius: 8px;
		background: #ffd34d;
		color: #0f2f52;
		font-size: 1.3rem;
	}
	.brand-name {
		display: block;
		font-size: 1.2rem;
		font-weight: 700;
		letter-spacing: 0.01em;
	}
	.brand-sub {
		display: block;
		font-size: 0.85rem;
		color: #c9d6e6;
	}
	.user {
		text-align: right;
		font-size: 0.875rem;
		line-height: 1.3;
	}
	.user-role {
		display: block;
		font-weight: 600;
	}
	.user-note {
		color: #c9d6e6;
	}
	nav ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem;
	}
	nav a {
		display: block;
		padding: 0.6rem 0.9rem;
		color: #e8eef6;
		text-decoration: none;
		font-weight: 500;
		border-bottom: 3px solid transparent;
	}
	nav a:hover {
		color: #fff;
		background: rgba(255, 255, 255, 0.08);
	}
	nav a[aria-current='page'] {
		color: #fff;
		font-weight: 700;
		border-bottom-color: #ffd34d;
	}
	main {
		padding-top: 1.5rem;
		padding-bottom: 2.5rem;
		min-height: 60vh;
	}
	main:focus {
		outline: none;
	}
	.site-footer {
		border-top: 1px solid var(--line);
		background: var(--surface);
		padding: 1rem 0;
		font-size: 0.9rem;
	}
	.site-footer p {
		margin: 0.2rem 0;
	}
	@media print {
		.site-footer {
			border-top: 1px solid #999;
		}
	}
</style>
