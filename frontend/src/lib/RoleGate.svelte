<script lang="ts">
	// Показує вміст лише тим ролям, кому можна; іншим — маленька примітка із замком.
	// Використання:
	//   <RoleGate>…лише після входу…</RoleGate>
	//   <RoleGate need="battery" cat={b.category_short} id={b.id}>…акумулятори…</RoleGate>
	//   <RoleGate allow={canEdit(auth.user, id)} inline>…кнопка «Редагувати»…</RoleGate>
	//   <RoleGate need="upload" hide>…пункт, якого не має бути видно…</RoleGate>
	import type { Snippet } from 'svelte';
	import { page } from '$app/state';
	import { auth } from './auth.svelte.ts';
	import {
		isInternal,
		canSeeSensitive,
		canSeeSes,
		canSeeFinance,
		canEdit,
		canUpload
	} from './roles.ts';
	import Icon from './Icon.svelte';

	let {
		children,
		fallback,
		allow,
		need = 'login',
		cat = null,
		id = null,
		inline = false,
		hide = false
	}: {
		children: Snippet;
		/** Власна заглушка замість примітки із замком */
		fallback?: Snippet;
		/** Готове рішення (має пріоритет над need) */
		allow?: boolean;
		/** Яке правило з roles.ts перевірити */
		need?: 'login' | 'sensitive' | 'battery' | 'ses' | 'finance' | 'edit' | 'upload';
		/** category_short об'єкта — для sensitive / battery / ses / finance */
		cat?: string | null;
		/** id об'єкта — для sensitive / battery / finance / edit */
		id?: number | string | null;
		/** Примітка в рядку (для таблиць і чипів) */
		inline?: boolean;
		/** Нічого не показувати замість вмісту */
		hide?: boolean;
	} = $props();

	const ok = $derived.by(() => {
		if (allow !== undefined) return allow;
		const u = auth.user;
		switch (need) {
			case 'sensitive':
				return canSeeSensitive(u, cat, id);
			case 'battery':
				return canSeeSensitive(u, cat, id);
			case 'ses':
				return canSeeSes(u, cat, id);
			case 'finance':
				return canSeeFinance(u, cat, id);
			case 'edit':
				return canEdit(u, id);
			case 'upload':
				return canUpload(u);
			default:
				return isInternal(u);
		}
	});

	const loggedIn = $derived(isInternal(auth.user));
	const loginHref = $derived.by(() => {
		const back = page.url.pathname + page.url.search;
		return '/login' + (back !== '/' ? `?next=${encodeURIComponent(back)}` : '');
	});
</script>

{#if ok}
	{@render children()}
{:else if fallback}
	{@render fallback()}
{:else if !hide}
	{#if loggedIn}
		<span class="gate" class:inline title="Ці дані не входять до вашої ролі">
			<Icon name="lock" size={inline ? 13 : 15} />
			<span>Недоступно для вашої ролі</span>
		</span>
	{:else}
		<a class="gate link" class:inline href={loginHref} title="Увійти, щоб побачити">
			<Icon name="lock" size={inline ? 13 : 15} />
			<span>Доступно після входу</span>
		</a>
	{/if}
{/if}

<style>
	.gate {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.35rem 0.7rem;
		border-radius: 999px;
		border: 1px dashed var(--line-strong, #b9c4d2);
		background: var(--surface-2, #f5f7fa);
		color: var(--muted, #5b6878);
		font-size: 0.8125rem;
		font-weight: 600;
		line-height: 1.2;
		text-decoration: none;
		white-space: nowrap;
	}
	.gate.inline {
		padding: 0.1rem 0.5rem;
		font-size: 0.75rem;
		gap: 0.3rem;
	}
	.link {
		cursor: pointer;
		transition:
			color var(--dur-fast, 120ms),
			border-color var(--dur-fast, 120ms),
			background var(--dur-fast, 120ms);
	}
	.link:hover {
		color: var(--navy, #0f2f52);
		border-color: var(--navy, #0f2f52);
		background: var(--sun-soft, #fff4d6);
		text-decoration: none;
	}
</style>
