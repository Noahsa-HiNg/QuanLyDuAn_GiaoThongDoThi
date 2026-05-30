import React, { useEffect, useRef } from 'react';
import mapboxgl from 'mapbox-gl';
import { useMapStore } from '../../store/mapStore';

interface RouteLayerProps {
  map: mapboxgl.Map;
}

const RouteLayer: React.FC<RouteLayerProps> = ({ map }) => {
  const { fromPos, toPos, routeShortest, routeFastest, selectedMode } = useMapStore();
  const startMarkerRef = useRef<mapboxgl.Marker | null>(null);
  const endMarkerRef = useRef<mapboxgl.Marker | null>(null);

  // Helper to round coordinates
  const roundCoord = (val: number) => Number(val.toFixed(6));

  // 0. Handle Map Clicks to Select Coordinates
  useEffect(() => {
    const handleMapClick = (e: mapboxgl.MapMouseEvent) => {
      const lat = roundCoord(e.lngLat.lat);
      const lng = roundCoord(e.lngLat.lng);

      const state = useMapStore.getState();
      if (!state.fromPos) {
        state.setFromPos([lat, lng]);
        state.setFromName(`Tọa độ: ${lat}, ${lng}`);
        state.clearRoute();
      } else if (!state.toPos) {
        state.setToPos([lat, lng]);
        state.setToName(`Tọa độ: ${lat}, ${lng}`);
        state.clearRoute();
      } else {
        // Reset and set as new start point
        state.setFromPos([lat, lng]);
        state.setFromName(`Tọa độ: ${lat}, ${lng}`);
        state.setToPos(null);
        state.setToName('');
        state.clearRoute();
      }
    };

    map.on('click', handleMapClick);
    return () => {
      map.off('click', handleMapClick);
    };
  }, [map]);

  // 1. Draw Start and End Markers
  useEffect(() => {
    // Clear existing markers
    if (startMarkerRef.current) {
      startMarkerRef.current.remove();
      startMarkerRef.current = null;
    }
    if (endMarkerRef.current) {
      endMarkerRef.current.remove();
      endMarkerRef.current = null;
    }

    // Add Start Marker (🟢 - Emerald Green)
    if (fromPos) {
      // fromPos is [lat, lng] in store, Mapbox expects [lng, lat]
      const el = document.createElement('div');
      el.className = 'w-4 h-4 rounded-full border-2 border-white shadow-lg';
      el.style.backgroundColor = '#4ade80'; // Emerald 400
      el.style.boxShadow = '0 0 12px rgba(74, 222, 128, 0.7)';

      startMarkerRef.current = new mapboxgl.Marker({ element: el })
        .setLngLat([fromPos[1], fromPos[0]])
        .addTo(map);
    }

    // Add End Marker (🔴 - Red)
    if (toPos) {
      // toPos is [lat, lng] in store, Mapbox expects [lng, lat]
      const el = document.createElement('div');
      el.className = 'w-4 h-4 rounded-full border-2 border-white shadow-lg';
      el.style.backgroundColor = '#ef4444'; // Red 500
      el.style.boxShadow = '0 0 12px rgba(239, 68, 68, 0.7)';

      endMarkerRef.current = new mapboxgl.Marker({ element: el })
        .setLngLat([toPos[1], toPos[0]])
        .addTo(map);
    }

    return () => {
      if (startMarkerRef.current) startMarkerRef.current.remove();
      if (endMarkerRef.current) endMarkerRef.current.remove();
    };
  }, [map, fromPos, toPos]);

  // 2. Draw Route Geometry Line
  useEffect(() => {
    const activeRoute = selectedMode === 'shortest' ? routeShortest : routeFastest;
    const color = selectedMode === 'shortest' ? '#818cf8' : '#4ade80'; // Indigo vs Emerald

    const updateRoute = () => {
      // If no route or path, remove existing layer/source
      if (!activeRoute || !activeRoute.path || activeRoute.path.length === 0) {
        if (map.getLayer('route-line')) map.removeLayer('route-line');
        if (map.getSource('route')) map.removeSource('route');
        return;
      }

      const geojson: GeoJSON.Feature<GeoJSON.LineString> = {
        type: 'Feature',
        properties: {},
        geometry: {
          type: 'LineString',
          coordinates: activeRoute.path, // Path coordinates are already [[lng, lat], ...]
        },
      };

      const source = map.getSource('route');
      if (source) {
        (source as mapboxgl.GeoJSONSource).setData(geojson);
        map.setPaintProperty('route-line', 'line-color', color);
      } else {
        map.addSource('route', {
          type: 'geojson',
          data: geojson,
        });

        map.addLayer({
          id: 'route-line',
          type: 'line',
          source: 'route',
          layout: {
            'line-join': 'round',
            'line-cap': 'round',
          },
          paint: {
            'line-color': color,
            'line-width': 6,
            'line-opacity': 0.85,
          },
        });
      }

      // Adjust camera bounds to fit the route path
      const coordinates = activeRoute.path;
      if (coordinates.length > 0) {
        const bounds = new mapboxgl.LngLatBounds();
        coordinates.forEach((coord) => bounds.extend(coord as [number, number]));
        map.fitBounds(bounds, {
          padding: 50,
          maxZoom: 15,
        });
      }
    };

    if (map.isStyleLoaded()) {
      updateRoute();
    } else {
      map.on('style.load', updateRoute);
    }

    return () => {
      if (map.getLayer('route-line')) map.removeLayer('route-line');
      if (map.getSource('route')) map.removeSource('route');
    };
  }, [map, routeShortest, routeFastest, selectedMode]);

  return null; // Component does not render DOM itself
};

export default RouteLayer;
