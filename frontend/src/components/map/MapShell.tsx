import { useEffect, useRef, useImperativeHandle, forwardRef } from 'react';
import maplibregl from 'maplibre-gl';
import { MapboxOverlay } from '@deck.gl/mapbox';
import type { Layer } from '@deck.gl/core';
import 'maplibre-gl/dist/maplibre-gl.css';

const BASEMAP_PRIMARY = 'https://tiles.openfreemap.org/styles/bright';
const BASEMAP_FALLBACK = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';
const DEFAULT_CENTER: [number, number] = [107.5, 15.5];
const DEFAULT_ZOOM = 5;

export interface MapShellRef {
  setLayers: (layers: Layer[]) => void;
  flyTo: (center: [number, number], zoom?: number) => void;
}

interface MapShellProps {
  className?: string;
}

export const MapShell = forwardRef<MapShellRef, MapShellProps>(({ className }, ref) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);

  useImperativeHandle(ref, () => ({
    setLayers: (layers: Layer[]) => {
      if (overlayRef.current) {
        overlayRef.current.setProps({ layers });
      }
    },
    flyTo: (center: [number, number], zoom?: number) => {
      if (mapRef.current) {
        mapRef.current.flyTo({ center, zoom: zoom ?? mapRef.current.getZoom() });
      }
    }
  }));

  useEffect(() => {
    if (!containerRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: BASEMAP_PRIMARY,
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
      minZoom: 4,
      maxZoom: 14,
      maxBounds: [[95.0, 5.0], [118.0, 26.0]],
      attributionControl: false,
      dragRotate: false,
      pitchWithRotate: false,
    });

    map.on('error', (e) => {
      const msg = String(e?.error?.message ?? '');
      if (msg.includes('404') || msg.includes('Failed')) {
        console.warn('[MapShell] Primary basemap failed, switching to fallback');
        map.setStyle(BASEMAP_FALLBACK);
      }
    });

    const applyVietnameseLabels = () => {
      const style = map.getStyle();
      if (!style?.layers) return;

      const waterPatterns = /water|marine|ocean|place[-_]sea/i;
      for (const layer of style.layers) {
        if (layer.type !== 'symbol' || !waterPatterns.test(layer.id)) continue;
        try {
          map.setLayoutProperty(layer.id, 'text-field', [
            'let', 'raw', ['coalesce', ['get', 'name:vi'], ['get', 'name:en'], ['get', 'name']],
            [
              'case',
              ['==', ['var', 'raw'], 'South China Sea'], 'Biển Đông',
              ['==', ['var', 'raw'], 'Nam Hải'], 'Biển Đông',
              ['var', 'raw']
            ]
          ]);
        } catch { } // Ignore expression errors
      }

      if (!map.getSource('vn-sea-labels')) {
        map.addSource('vn-sea-labels', {
          type: 'geojson',
          data: {
            type: 'FeatureCollection',
            features: [
              { type: 'Feature', properties: { name: 'Biển Đông', size: 18 }, geometry: { type: 'Point', coordinates: [112.5, 15.0] } },
              { type: 'Feature', properties: { name: 'Quần đảo Hoàng Sa\n(Việt Nam)', size: 12 }, geometry: { type: 'Point', coordinates: [112.0, 16.5] } },
              { type: 'Feature', properties: { name: 'Quần đảo Trường Sa\n(Việt Nam)', size: 12 }, geometry: { type: 'Point', coordinates: [114.0, 10.0] } }
            ]
          }
        });
      }

      if (!map.getLayer('vn-sea-labels-text')) {
        map.addLayer({
          id: 'vn-sea-labels-text',
          type: 'symbol',
          source: 'vn-sea-labels',
          layout: {
            'text-field': ['get', 'name'],
            'text-size': ['get', 'size'],
            'text-font': ['Noto Sans Regular'],
            'text-anchor': 'center'
          },
          paint: {
            'text-color': '#1e3a5f',
            'text-halo-color': 'rgba(255,255,255,0.9)',
            'text-halo-width': 1.5,
          }
        });
      }
    };

    map.on('style.load', applyVietnameseLabels);
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');

    const overlay = new MapboxOverlay({ layers: [] });
    // Fix TypeScript definitions mismatch for maplibre vs mapbox
    map.addControl(overlay as unknown as maplibregl.IControl);

    mapRef.current = map;
    overlayRef.current = overlay;

    return () => {
      map.remove();
    };
  }, []);

  return <div ref={containerRef} className={className} />;
});

MapShell.displayName = 'MapShell';
