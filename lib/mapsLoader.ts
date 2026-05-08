// Kairos AI — Google Maps Loader
// Singleton loader for the Google Maps JS API

import { Loader } from '@googlemaps/js-api-loader';

let loader: Loader | null = null;

export function getMapsLoader(): Loader {
  if (!loader) {
    loader = new Loader({
      apiKey: process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY || '',
      version: 'weekly',
      libraries: ['places', 'geometry'],
    });
  }
  return loader;
}

export async function loadGoogleMaps(): Promise<typeof google> {
  const l = getMapsLoader();
  return l.load();
}
