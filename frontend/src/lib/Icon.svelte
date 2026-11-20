<script module lang="ts">
	// Невеликий набір лінійних іконок (24×24, stroke = currentColor). Завжди декоративні.
	export type IconName =
		| 'sun'
		| 'battery'
		| 'bolt'
		| 'plug'
		| 'building'
		| 'search'
		| 'pin'
		| 'panel'
		| 'inverter'
		| 'check'
		| 'alert'
		| 'arrow-left'
		| 'arrow-right'
		| 'logout'
		| 'clock'
		| 'grid'
		| 'chart'
		| 'wallet'
		| 'gauge'
		| 'info'
		| 'users'
		| 'lock'
		| 'x'
		| 'plus'
		| 'circle'
		| 'help'
		| 'arrow-up'
		| 'arrow-down';
</script>

<script lang="ts">
	let { name, size = 20, stroke = 1.8 }: { name: IconName; size?: number; stroke?: number } =
		$props();
</script>

<svg
	class="icon"
	width={size}
	height={size}
	viewBox="0 0 24 24"
	fill="none"
	stroke="currentColor"
	stroke-width={stroke}
	stroke-linecap="round"
	stroke-linejoin="round"
	aria-hidden="true"
	focusable="false"
>
	{#if name === 'sun'}
		<circle cx="12" cy="12" r="4.2" />
		<path
			d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M5.3 18.7l1.6-1.6M17.1 6.9l1.6-1.6"
		/>
	{:else if name === 'battery'}
		<rect x="2.5" y="7" width="17" height="10" rx="2.2" />
		<path d="M21.5 10.5v3M6 10v4M9.5 10v4" />
	{:else if name === 'bolt'}
		<path d="M13 2.5 4.5 13.5H11l-1 8 8.5-11H12l1-8Z" />
	{:else if name === 'plug'}
		<path d="M9 2.5v5M15 2.5v5M6.5 7.5h11v3.5a5.5 5.5 0 0 1-11 0V7.5ZM12 16.5v5" />
	{:else if name === 'building'}
		<path
			d="M4 21V5.5L12 3l8 2.5V21M2.5 21h19M8.5 8.5h.01M12 8.5h.01M15.5 8.5h.01M8.5 12.5h.01M12 12.5h.01M15.5 12.5h.01M10 21v-4.5h4V21"
		/>
	{:else if name === 'search'}
		<circle cx="11" cy="11" r="6.5" />
		<path d="m20.5 20.5-4.8-4.8" />
	{:else if name === 'pin'}
		<path d="M12 21.5s-7-6.2-7-11.5a7 7 0 0 1 14 0c0 5.3-7 11.5-7 11.5Z" />
		<circle cx="12" cy="10" r="2.5" />
	{:else if name === 'panel'}
		<path d="M5.5 4h13l3 10h-19l3-10ZM2.5 14h19M12 4v10M4 9h16M9 14l-1 6.5h8L15 14" />
	{:else if name === 'inverter'}
		<rect x="4" y="3" width="16" height="18" rx="2.5" />
		<path d="M8 8.5c1-1.4 2-1.4 3 0s2 1.4 3 0 2-1.4 2 0M8 15.5h8" />
	{:else if name === 'check'}
		<path d="m4.5 12.5 5 5 10-11" />
	{:else if name === 'alert'}
		<path d="M12 3.5 2.5 20h19L12 3.5Z" />
		<path d="M12 10v4.5M12 17.2h.01" />
	{:else if name === 'arrow-left'}
		<path d="M19 12H5M11 6l-6 6 6 6" />
	{:else if name === 'arrow-right'}
		<path d="M5 12h14M13 6l6 6-6 6" />
	{:else if name === 'logout'}
		<path
			d="M14 4.5h4.5a1.5 1.5 0 0 1 1.5 1.5v12a1.5 1.5 0 0 1-1.5 1.5H14M9.5 16.5 5 12l4.5-4.5M5 12h10.5"
		/>
	{:else if name === 'clock'}
		<circle cx="12" cy="12" r="8.5" />
		<path d="M12 7.5V12l3 2" />
	{:else if name === 'grid'}
		<path d="M8 21.5 12 2.5l4 19M9.2 15.5h5.6M10.3 10h3.4M5 6.5h14M3.5 6.5l1.5 3M20.5 6.5l-1.5 3" />
	{:else if name === 'chart'}
		<path d="M3.5 3.5v17h17M7.5 15l3.5-4.5 3 3 5-6.5" />
	{:else if name === 'wallet'}
		<path
			d="M4 6.5h14.5a1.5 1.5 0 0 1 1.5 1.5v10.5a1.5 1.5 0 0 1-1.5 1.5H5.5A1.5 1.5 0 0 1 4 18.5V6.5Zm0 0 11-3V6.5M16 13.5h.01"
		/>
	{:else if name === 'gauge'}
		<path d="M4.2 17.5a8.5 8.5 0 1 1 15.6 0M12 13l3.5-4" />
		<circle cx="12" cy="13.5" r="1.2" />
	{:else if name === 'info'}
		<circle cx="12" cy="12" r="8.5" />
		<path d="M12 11v5.5M12 7.8h.01" />
	{:else if name === 'users'}
		<circle cx="9" cy="8.5" r="3.5" />
		<path d="M2.5 20c.6-3.5 3.2-5.5 6.5-5.5s5.9 2 6.5 5.5M16 5.2a3.5 3.5 0 0 1 0 6.6M18 14.8c2 .7 3.2 2.4 3.5 5.2" />
	{:else if name === 'lock'}
		<rect x="5" y="10.5" width="14" height="10" rx="2" />
		<path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" />
	{:else if name === 'x'}
		<path d="M6 6l12 12M18 6 6 18" />
	{:else if name === 'plus'}
		<path d="M12 4.5v15M4.5 12h15" />
	{:else if name === 'circle'}
		<circle cx="12" cy="12" r="7" />
	{:else if name === 'help'}
		<path d="M9.2 9a2.9 2.9 0 0 1 5.6 1c0 1.9-2.8 2.4-2.8 4.2M12 18h.01" />
	{:else if name === 'arrow-up'}
		<path d="M12 19V5M6 11l6-6 6 6" />
	{:else if name === 'arrow-down'}
		<path d="M12 5v14M6 13l6 6 6-6" />
	{/if}
</svg>

<style>
	.icon {
		flex: none;
		display: inline-block;
		vertical-align: -0.2em;
	}
</style>
