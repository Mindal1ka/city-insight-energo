// Кольори та підписи статусів зон — узгоджені з K_CLASSES (api-ses.ts).
import { K_CLASSES } from './api-ses.ts';
import type { Zone } from './api-v2.ts';

const c = (id: string) => K_CLASSES.find((k) => k.id === id)!.color;

export const ZONE_COLORS: Record<NonNullable<Zone['status']>, string> = {
	surplus: c('Надлишок'),
	balanced: c('Ефективно'),
	deficit: c('Не вистачає'),
	no_ses: c('Без СЕС')
};

export const ZONE_LABELS: Record<NonNullable<Zone['status']>, string> = {
	surplus: 'Надлишок',
	balanced: 'Баланс',
	deficit: 'Не вистачає',
	no_ses: 'Без СЕС'
};
