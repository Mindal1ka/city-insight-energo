// Атачмент для сторінок аналітики: додає клас `grown`, коли блок з'являється на екрані.
// У CSS смужки стартують із scaleX(0) і «виростають», коли батько отримав .grown.
// Без IntersectionObserver або за prefers-reduced-motion — клас додається одразу.
//
//   <ul {@attach grow}> … <span class="fill" style="--i:{i}"></span> … </ul>
//   .fill { transform: scaleX(0); transition: transform .7s var(--ease) calc(var(--i, 0) * 45ms); }
//   :global(.grown) .fill { transform: none; }
import { isReduced } from '#lib/motion.ts';

export function grow(node: HTMLElement): () => void {
	if (isReduced() || typeof IntersectionObserver === 'undefined') {
		node.classList.add('grown');
		return () => {};
	}
	const io = new IntersectionObserver(
		(entries) => {
			if (entries.some((e) => e.isIntersecting)) {
				// Наступний кадр: щоб початковий scaleX(0) встиг застосуватися
				requestAnimationFrame(() => node.classList.add('grown'));
				io.disconnect();
			}
		},
		{ threshold: 0.15 }
	);
	io.observe(node);
	return () => io.disconnect();
}
