// /map → / (мапа тепер на головній)
import { redirect } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ url }) => {
	redirect(307, '/' + url.search);
};
