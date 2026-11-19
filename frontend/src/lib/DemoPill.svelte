<script lang="ts">
	// Постійна позначка синтетичних даних із підказкою (працює з мишею, клавіатурою й дотиком)
	let {
		text = 'Даних про наявні СЕС у пакеті міста немає; показано змодельовані значення',
		tone = 'light',
		align = 'right'
	}: { text?: string; tone?: 'light' | 'dark'; align?: 'left' | 'right' } = $props();
	const id = `demo-tip-${Math.random().toString(36).slice(2, 8)}`;
</script>

<span class="demo {tone} {align}">
	<button type="button" class="pill-btn" aria-describedby={id}>
		<span class="dot" aria-hidden="true"></span>ДЕМО-ДАНІ
	</button>
	<span role="tooltip" {id} class="tip">{text}</span>
</span>

<style>
	.demo {
		position: relative;
		display: inline-flex;
		vertical-align: middle;
	}
	.pill-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.2rem 0.65rem;
		border-radius: 999px;
		font: inherit;
		font-size: 0.75rem;
		font-weight: 700;
		letter-spacing: 0.06em;
		line-height: 1.5;
		cursor: help;
		background: var(--sun-soft);
		color: var(--sun-ink);
		border: 1px dashed #d08a1c;
		white-space: nowrap;
		position: relative;
	}
	/* Зона натискання ≥ 40 px по висоті без зміни вигляду позначки */
	.pill-btn::after {
		content: '';
		position: absolute;
		inset: -8px -4px;
	}
	.dark .pill-btn {
		background: rgba(245, 165, 36, 0.14);
		color: #ffd894;
		border-color: rgba(255, 216, 148, 0.55);
	}
	.dot {
		width: 0.45rem;
		height: 0.45rem;
		border-radius: 50%;
		background: var(--sun-strong);
	}
	.tip {
		position: absolute;
		z-index: 40;
		top: calc(100% + 8px);
		width: max-content;
		max-width: min(19rem, calc(100vw - 2.5rem));
		padding: 0.6rem 0.8rem;
		border-radius: 10px;
		background: #142235;
		color: #fff;
		font-size: 0.8125rem;
		font-weight: 400;
		line-height: 1.45;
		letter-spacing: 0;
		text-transform: none;
		text-align: left;
		box-shadow: var(--shadow-lg);
		display: none;
		pointer-events: none;
	}
	.right .tip {
		right: 0;
	}
	.left .tip {
		left: 0;
	}
	.demo:hover .tip,
	.pill-btn:focus + .tip {
		display: block;
	}
</style>
