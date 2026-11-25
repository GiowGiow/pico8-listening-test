// @ts-check
import { defineConfig } from 'astro/config';
import { paraglideVitePlugin } from "@inlang/paraglide-js";
import node from "@astrojs/node";

import react from '@astrojs/react';
import tailwindcss from '@tailwindcss/vite';


// https://astro.build/config
export default defineConfig({
  integrations: [
	react(),
	],
  vite: {
    plugins: [
tailwindcss(),
		paraglideVitePlugin({
			project: "./project.inlang",
			outdir: "./src/paraglide",
			strategy: ["cookie","preferredLanguage", "baseLocale"]
		}),
		],
  },
  site: 'https://hpc.uai.science',
  output: "server",
  adapter: node({ mode: "standalone" }),
	experimental: {
		session: true,
	},
});