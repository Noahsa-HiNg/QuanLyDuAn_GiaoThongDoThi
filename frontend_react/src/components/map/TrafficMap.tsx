import React, { useEffect, useRef, useState } from 'react';
import mapboxgl from 'mapbox-gl';
import Papa from 'papaparse';
import { Camera, Layers, Box, Eye, EyeOff } from 'lucide-react';
import { DA_NANG_CENTER, DEFAULT_ZOOM } from '../../constants/map.constants';
import { useGeometry } from '../../hooks/useGeometry';
import { useTrafficData } from '../../hooks/useTrafficData';
import { buildGeoJSON } from '../../utils/buildGeoJSON';
import { getCongestionLabel } from '../../utils/congestionColor';
import { fmtTimestampVN, normalizeVN } from '../../utils/formatters';
import type { Incident } from '../../types/api.types';

// Set Mapbox access token
const mapboxToken = import.meta.env.VITE_MAPBOX_TOKEN || '';
mapboxgl.accessToken = mapboxToken;
const getDistance = (lat1: number, lon1: number, lat2: number, lon2: number): number => {
  const R = 6371; // Earth's radius in km
  const dLat = (lat2 - lat1) * (Math.PI / 180);
  const dLon = (lon2 - lon1) * (Math.PI / 180);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(lat1 * (Math.PI / 180)) * Math.cos(lat2 * (Math.PI / 180)) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
};

interface PredictionItem {
  street_id?: number;
  road_id?: number;
  predicted_level: 0 | 1 | 2;
  confidence: number;
}

interface TrafficMapProps {
  districtId?: number | null;
  congestionLevel?: number | null;
  searchQuery?: string;
  isPredictionMode?: boolean;
  predictionData?: PredictionItem[] | null;
  hideTrafficLines?: boolean;
  activeIncidents?: Incident[];
  onStreetClick?: (streetName: string, coords?: { lat: number; lng: number }) => void;
  isReportMode?: boolean;
  onReportClick?: (lat: number, lng: number, streetName?: string) => void;
  is3D?: boolean;
  trafficState?: any;
  communityReports?: any[];
  showCommunityReports?: boolean;
  flyToCoords?: { lat: number; lng: number } | null;
  fitBoundsCoords?: [number, number][] | null;
  isCsgtView?: boolean;
  onVerifyReport?: (id: number) => void;
  onVerifyCluster?: (ids: number[]) => void;
  hasActiveAlert?: boolean;
  pageContext?: 'home' | 'route-finder' | 'csgt';
  children?: (map: mapboxgl.Map) => React.ReactNode;
}

const TrafficMap: React.FC<TrafficMapProps> = ({
  districtId = null,
  congestionLevel = null,
  searchQuery = '',
  isPredictionMode = false,
  predictionData = null,
  hideTrafficLines = false,
  activeIncidents = [],
  onStreetClick,
  isReportMode = false,
  onReportClick,
  is3D = false,
  trafficState: propsTrafficState = null,
  communityReports = [],
  showCommunityReports = false,
  flyToCoords = null,
  fitBoundsCoords = null,
  isCsgtView = false,
  onVerifyReport,
  onVerifyCluster,
  hasActiveAlert = false,
  pageContext = 'home',
  children,
}) => {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<mapboxgl.Map | null>(null);
  const [mapInstance, setMapInstance] = useState<mapboxgl.Map | null>(null);
  const [currentZoom, setCurrentZoom] = useState(DEFAULT_ZOOM);

  const [localIs3D, setLocalIs3D] = useState(is3D);
  const [localHideTraffic, setLocalHideTraffic] = useState(hideTrafficLines);

  useEffect(() => {
    setLocalIs3D(is3D);
  }, [is3D]);

  useEffect(() => {
    setLocalHideTraffic(hideTrafficLines);
  }, [hideTrafficLines]);

  useEffect(() => {
    const map = mapInstance;
    if (map && flyToCoords) {
      map.flyTo({
        center: [flyToCoords.lng, flyToCoords.lat],
        zoom: 16,
        essential: true,
      });
    }
  }, [mapInstance, flyToCoords]);

  useEffect(() => {
    const map = mapInstance;
    if (map && fitBoundsCoords && fitBoundsCoords.length > 0) {
      const bounds = new mapboxgl.LngLatBounds();
      fitBoundsCoords.forEach((coord) => bounds.extend(coord as [number, number]));
      map.fitBounds(bounds, {
        padding: 80,
        maxZoom: 17,
        essential: true,
      });
    }
  }, [mapInstance, fitBoundsCoords]);

  const onStreetClickRef = useRef(onStreetClick);
  const isReportModeRef = useRef(isReportMode);
  const onReportClickRef = useRef(onReportClick);

  useEffect(() => {
    onStreetClickRef.current = onStreetClick;
    isReportModeRef.current = isReportMode;
    onReportClickRef.current = onReportClick;
  }, [onStreetClick, isReportMode, onReportClick]);

  const [snapshotData, setSnapshotData] = useState<any[] | null>(null);
  const { data: geometry, isLoading: isGeomLoading, error: geomError } = useGeometry();
  const { data: liveTrafficState, isLoading: isStateLoading, error: stateError } = useTrafficData();
  const trafficState = snapshotData
    ? { total: snapshotData.length, streets: snapshotData }
    : (propsTrafficState || liveTrafficState);

  // 1. Initialize Map
  useEffect(() => {
    if (!mapRef.current || mapInstanceRef.current || !mapboxToken) return;

    const map = new mapboxgl.Map({
      container: mapRef.current,
      style: 'mapbox://styles/mapbox/light-v11',
      center: DA_NANG_CENTER,
      zoom: DEFAULT_ZOOM,
      preserveDrawingBuffer: true,
    });

    map.addControl(new mapboxgl.NavigationControl({ showCompass: false }), 'bottom-right');
    map.addControl(new mapboxgl.GeolocateControl({
      positionOptions: { enableHighAccuracy: true },
      trackUserLocation: true,
    }), 'bottom-right');

    mapInstanceRef.current = map;
    setMapInstance(map);
    map.on('zoom', () => {
      setCurrentZoom(map.getZoom());
    });

    // Click handler for popup and dispatch trigger
    map.on('click', 'traffic-lines', (e) => {
      if (isReportModeRef.current) return;

      if (!e.features || e.features.length === 0) return;
      const feat = e.features[0];
      const props = feat.properties;
      if (!props) return;

      const name = props.name || 'Không rõ tên đường';
      
      // Fire callback to open dispatch modal with coordinates
      if (onStreetClickRef.current) {
        onStreetClickRef.current(name, { lat: e.lngLat.lat, lng: e.lngLat.lng });
      }

      const district = props.district || 'Không rõ quận';
      const speed = props.avg_speed !== null && props.avg_speed !== undefined ? `${props.avg_speed} km/h` : 'N/A';
      const level = props.congestion_level;
      const timeStr = props.timestamp ? fmtTimestampVN(props.timestamp) : 'N/A';

      const popupContent = `
        <div class="p-1">
          <h4 class="font-bold text-base text-gray-900 border-b pb-1 mb-2">${name}</h4>
          <p class="text-sm text-gray-600 mb-1"><b>Quận:</b> ${district}</p>
          <p class="text-sm text-gray-600 mb-1"><b>Trạng thái:</b> <span class="font-semibold">${getCongestionLabel(level)}</span></p>
          <p class="text-sm text-gray-600 mb-1"><b>Tốc độ TB:</b> ${speed}</p>
          <p class="text-xs text-gray-400 mt-2">Cập nhật: ${timeStr}</p>
        </div>
      `;

      new mapboxgl.Popup()
        .setLngLat(e.lngLat)
        .setHTML(popupContent)
        .addTo(map);
    });

    // General map click listener for report mode
    map.on('click', (e) => {
      if (isReportModeRef.current) {
        const lat = e.lngLat.lat;
        const lng = e.lngLat.lng;
        const features = map.queryRenderedFeatures(e.point, { layers: ['traffic-lines'] });
        let streetName = '';
        if (features && features.length > 0) {
          streetName = features[0].properties?.name || '';
        }
        if (onReportClickRef.current) {
          onReportClickRef.current(lat, lng, streetName);
        }
      }
    });

    // Hover effect pointer
    map.on('mouseenter', 'traffic-lines', () => {
      if (isReportModeRef.current) {
        map.getCanvas().style.cursor = 'crosshair';
      } else {
        map.getCanvas().style.cursor = 'pointer';
      }
    });
    map.on('mouseleave', 'traffic-lines', () => {
      map.getCanvas().style.cursor = isReportModeRef.current ? 'crosshair' : '';
    });

    return () => {
      setMapInstance(null);
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  // 2. Load and Update GeoJSON Data Source
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !geometry || !trafficState) return;

    const updateSource = () => {
      try {
        if (!mapInstanceRef.current) return;
        let geojson = buildGeoJSON(geometry, trafficState);

        // Handle AI prediction overlay modifications
        if (isPredictionMode && predictionData) {
          const predMap = new Map<number, number>();
          for (const p of predictionData) {
            const id = p.road_id ?? p.street_id;
            if (id !== undefined && id !== null) {
              predMap.set(id, p.predicted_level);
            }
          }
          geojson.features.forEach((f) => {
            if (f.properties) {
              const predLevel = predMap.get(f.properties.street_id);
              f.properties.congestion_level = predLevel !== undefined ? predLevel : null;
            }
          });
        }

        // Apply Filters (District, Congestion Level, Street Search) in Javascript/Typescript
        let filteredFeatures = geojson.features;

        // A. Filter by District
        if (districtId !== null) {
          const districtNames: Record<number, string> = {
            1: 'Hải Châu',
            2: 'Thanh Khê',
            3: 'Sơn Trà',
            4: 'Ngũ Hành Sơn',
            5: 'Liên Chiểu',
            6: 'Cẩm Lệ',
            7: 'Hòa Vang',
            8: 'Hoàng Sa',
          };
          const selectedName = districtNames[districtId];
          if (selectedName) {
            filteredFeatures = filteredFeatures.filter(
              (f) => f.properties?.district === selectedName
            );
          }
        }

        // B. Filter by Congestion Level
        if (congestionLevel !== null) {
          filteredFeatures = filteredFeatures.filter(
            (f) => f.properties?.congestion_level === congestionLevel
          );
        }

        // C. Filter by Search Query
        if (searchQuery.trim() !== '') {
          const normalizedQuery = normalizeVN(searchQuery);
          filteredFeatures = filteredFeatures.filter((f) => {
            const streetName = f.properties?.name || '';
            return normalizeVN(streetName).includes(normalizedQuery);
          });
        }

        geojson = {
          ...geojson,
          features: filteredFeatures,
        };

        const source = map.getSource('traffic');
        if (source) {
          (source as mapboxgl.GeoJSONSource).setData(geojson);
          if (map.getLayer('traffic-lines')) {
            map.setLayoutProperty(
              'traffic-lines',
              'visibility',
              localHideTraffic ? 'none' : 'visible'
            );
          }
        } else {
          map.addSource('traffic', {
            type: 'geojson',
            data: geojson,
          });

          map.addLayer({
            id: 'traffic-lines',
            type: 'line',
            source: 'traffic',
            layout: { 
              'line-join': 'round', 
              'line-cap': 'round',
              'visibility': localHideTraffic ? 'none' : 'visible'
            },
            paint: {
              'line-color': [
                'case',
                ['==', ['get', 'congestion_level'], 0], '#22c55e',
                ['==', ['get', 'congestion_level'], 1], '#f59e0b',
                ['==', ['get', 'congestion_level'], 2], '#ef4444',
                '#94a3b8',
              ],
              'line-width': [
                'interpolate', ['linear'], ['zoom'],
                10, 2,
                14, 5,
                18, 8,
              ],
              'line-opacity': 0.9,
            },
          });
        }
      } catch (err) {
        console.warn('Map source update failed:', err);
      }
    };

    if (map.isStyleLoaded()) {
      updateSource();
    } else {
      map.on('style.load', updateSource);
    }

    return () => {
      try {
        map.off('style.load', updateSource);
      } catch (e) {}
    };
  }, [geometry, trafficState, isPredictionMode, predictionData, localHideTraffic, districtId, congestionLevel, searchQuery]);


  // Apply layer visibility based on localHideTraffic state
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    const updateVisibility = () => {
      if (map.getLayer('traffic-lines')) {
        map.setLayoutProperty(
          'traffic-lines',
          'visibility',
          localHideTraffic ? 'none' : 'visible'
        );
      }
    };

    if (map.isStyleLoaded()) {
      updateVisibility();
    } else {
      map.on('style.load', updateVisibility);
    }

    return () => {
      try {
        map.off('style.load', updateVisibility);
      } catch (e) {}
    };
  }, [localHideTraffic, mapInstance]);

  // Handle 3D buildings toggle and map pitch rotation
  useEffect(() => {
    const map = mapInstance;
    if (!map) return;

    // Camera tilt transition
    map.easeTo({
      pitch: localIs3D ? 60 : 0,
      bearing: localIs3D ? -15 : 0,
      duration: 1000,
    });

    const toggle3DBuildings = (mapObj: mapboxgl.Map, show3D: boolean) => {
      try {
        const layers = mapObj.getStyle().layers;
        let labelLayerId;
        if (layers) {
          for (let i = 0; i < layers.length; i++) {
            if (layers[i].type === 'symbol' && layers[i].layout && (layers[i].layout as any)['text-field']) {
              labelLayerId = layers[i].id;
              break;
            }
          }
        }

        // 1. Enable realistic ambient and directional lighting in 3D mode
        if (show3D) {
          mapObj.setLight({
            anchor: 'viewport',
            color: '#f8fafc',
            intensity: 0.45,
            position: [1.15, 210, 30] // radial, azimuthal, polar
          });
        } else {
          // Reset light in 2D mode
          mapObj.setLight({
            anchor: 'viewport',
            color: '#ffffff',
            intensity: 0.1,
            position: [1, 0, 45]
          });
        }

        // 2. Add realistic glassmorphism style 3D buildings
        if (!mapObj.getLayer('3d-buildings')) {
          mapObj.addLayer(
            {
              'id': '3d-buildings',
              'source': 'composite',
              'source-layer': 'building',
              'filter': ['==', 'extrude', 'true'],
              'type': 'fill-extrusion',
              'minzoom': 14.5,
              'paint': {
                // Glass-blue building shading based on height
                'fill-extrusion-color': [
                  'interpolate',
                  ['linear'],
                  ['get', 'height'],
                  0, '#e2e8f0',   // low building: Slate-200
                  15, '#94a3b8',  // medium building: Slate-400
                  30, '#38bdf8',  // tall glass tower: Sky-400
                  60, '#0284c7',  // massive skyscrapers: Sky-600
                  100, '#6366f1'  // iconic tower: Indigo-500
                ],
                'fill-extrusion-height': [
                  'interpolate',
                  ['linear'],
                  ['zoom'],
                  15,
                  0,
                  15.05,
                  ['get', 'height']
                ],
                'fill-extrusion-base': [
                  'interpolate',
                  ['linear'],
                  ['zoom'],
                  15,
                  0,
                  15.05,
                  ['get', 'min_height']
                ],
                'fill-extrusion-opacity': 0.85
              }
            },
            labelLayerId
          );
        }

        // 3. Add Custom 3D Cầu Rồng (Dragon Bridge) Structure
        const dragonBridgeGeoJSON: any = {
          type: 'FeatureCollection',
          features: [
            // Wave segments of the Golden Dragon
            {
              type: 'Feature',
              properties: { height: 18, base: 7, color: '#facc15' },
              geometry: {
                type: 'Polygon',
                coordinates: [[
                  [108.2268, 16.06103],
                  [108.2271, 16.06103],
                  [108.2271, 16.06122],
                  [108.2268, 16.06122],
                  [108.2268, 16.06103]
                ]]
              }
            },
            {
              type: 'Feature',
              properties: { height: 26, base: 7, color: '#eab308' },
              geometry: {
                type: 'Polygon',
                coordinates: [[
                  [108.2271, 16.06103],
                  [108.2274, 16.06103],
                  [108.2274, 16.06122],
                  [108.2271, 16.06122],
                  [108.2271, 16.06103]
                ]]
              }
            },
            {
              type: 'Feature',
              properties: { height: 18, base: 7, color: '#facc15' },
              geometry: {
                type: 'Polygon',
                coordinates: [[
                  [108.2274, 16.06103],
                  [108.2277, 16.06103],
                  [108.2277, 16.06122],
                  [108.2274, 16.06122],
                  [108.2274, 16.06103]
                ]]
              }
            },
            {
              type: 'Feature',
              properties: { height: 26, base: 7, color: '#eab308' },
              geometry: {
                type: 'Polygon',
                coordinates: [[
                  [108.2277, 16.06103],
                  [108.2280, 16.06103],
                  [108.2280, 16.06122],
                  [108.2277, 16.06122],
                  [108.2277, 16.06103]
                ]]
              }
            },
            {
              type: 'Feature',
              properties: { height: 18, base: 7, color: '#facc15' },
              geometry: {
                type: 'Polygon',
                coordinates: [[
                  [108.2280, 16.06103],
                  [108.2283, 16.06103],
                  [108.2283, 16.06122],
                  [108.2280, 16.06122],
                  [108.2280, 16.06103]
                ]]
              }
            },
            // Glowing Orange Dragon Head facing West
            {
              type: 'Feature',
              properties: { height: 23, base: 7, color: '#ea580c' },
              geometry: {
                type: 'Polygon',
                coordinates: [[
                  [108.2264, 16.06101],
                  [108.2268, 16.06101],
                  [108.2268, 16.06124],
                  [108.2264, 16.06124],
                  [108.2264, 16.06101]
                ]]
              }
            },
            // Dragon Tail facing East
            {
              type: 'Feature',
              properties: { height: 15, base: 7, color: '#ca8a04' },
              geometry: {
                type: 'Polygon',
                coordinates: [[
                  [108.2283, 16.06105],
                  [108.2286, 16.06105],
                  [108.2286, 16.06120],
                  [108.2283, 16.06120],
                  [108.2283, 16.06105]
                ]]
              }
            }
          ]
        };

        if (!mapObj.getSource('dragon-bridge-source')) {
          mapObj.addSource('dragon-bridge-source', {
            type: 'geojson',
            data: dragonBridgeGeoJSON
          });
        }

        if (!mapObj.getLayer('dragon-bridge-layer')) {
          mapObj.addLayer({
            id: 'dragon-bridge-layer',
            type: 'fill-extrusion',
            source: 'dragon-bridge-source',
            paint: {
              'fill-extrusion-color': ['get', 'color'],
              'fill-extrusion-height': ['get', 'height'],
              'fill-extrusion-base': ['get', 'base'],
              'fill-extrusion-opacity': 0.95
            }
          });
        }

        mapObj.setLayoutProperty('3d-buildings', 'visibility', show3D ? 'visible' : 'none');
        mapObj.setLayoutProperty('dragon-bridge-layer', 'visibility', show3D ? 'visible' : 'none');
      } catch (err) {
        console.warn('Failed to toggle 3D settings:', err);
      }
    };

    const handleStyleLoad = () => {
      toggle3DBuildings(map, localIs3D);
    };

    if (map.isStyleLoaded()) {
      toggle3DBuildings(map, localIs3D);
    } else {
      map.on('style.load', handleStyleLoad);
    }

    return () => {
      try {
        map.off('style.load', handleStyleLoad);
      } catch (e) {}
    };
  }, [localIs3D, mapInstance]);

  // Render incident markers on the map
  const markersRef = useRef<mapboxgl.Marker[]>([]);
  useEffect(() => {
    const map = mapInstance;
    if (!map) return;

    // Clear existing markers
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    if (!geometry || !activeIncidents || activeIncidents.length === 0) return;

    activeIncidents.forEach((incident) => {
      // Find the corresponding street path
      const street = (geometry.streets ?? []).find((s) => s.street_id === incident.street_id);
      if (!street || !street.path || street.path.length === 0) return;

      // Compute midpoint of the path
      const midIdx = Math.floor(street.path.length / 2);
      // Determine marker coordinate: custom click position or street midpoint
      let markerCoords: [number, number];
      if (
        incident.latitude !== undefined && 
        incident.latitude !== null && 
        incident.longitude !== undefined && 
        incident.longitude !== null
      ) {
        markerCoords = [incident.longitude, incident.latitude];
      } else {
        const midpoint = street.path[midIdx];
        if (!midpoint) return;
        markerCoords = [midpoint[0], midpoint[1]];
      }

      // Create marker element
      const el = document.createElement('div');
      let markerClass = 'incident-marker flex items-center justify-center w-8 h-8 rounded-full bg-slate-900/90 backdrop-blur-md border shadow-xl cursor-pointer text-sm hover:scale-110 transition-transform duration-200';
      if (incident.status === 'declined') {
        markerClass += ' border-red-500 shadow-[0_0_12px_rgba(239,68,68,0.7)] animate-pulse';
      } else {
        markerClass += ' border-white/20';
      }
      el.className = markerClass;
      
      let emoji = '⚠️';
      if (incident.status === 'declined') emoji = '❌';
      else if (incident.type === 'accident') emoji = '🚗💥';
      else if (incident.type === 'roadblock') emoji = '🚧';
      else if (incident.type === 'event') emoji = '🎪';
      else if (incident.type === 'community') emoji = '👥';

      el.innerHTML = emoji;
      el.title = `${incident.description || 'Sự cố'} - ${street.street_name}`;

      // Create popup
      const popup = new mapboxgl.Popup({ offset: 25 }).setHTML(`
        <div class="p-1 text-slate-800 text-xs">
          <strong class="block text-slate-900 font-bold mb-1">${street.street_name}</strong>
          <p class="mb-1 text-slate-600">${incident.description || 'Đang điều phối xử lý.'}</p>
          <div class="mt-2 pt-1.5 border-t border-slate-100 flex items-center justify-between text-[10px] text-slate-500">
            <span>Trạng thái: <b>${
              incident.status === 'declined'
                ? '<span class="text-red-500 font-bold">Bị từ chối ❌</span>'
                : incident.status === 'dispatched'
                  ? 'Đã điều động 🚔'
                  : 'Đang xảy ra ⚠️'
            }</b></span>
          </div>
        </div>
      `);

      const marker = new mapboxgl.Marker(el)
        .setLngLat(markerCoords)
        .setPopup(popup)
        .addTo(map);

      markersRef.current.push(marker);
    });

    return () => {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
    };
  }, [mapInstance, geometry, activeIncidents]);

  // Render community reports on the map
  const communityMarkersRef = useRef<mapboxgl.Marker[]>([]);
  useEffect(() => {
    const map = mapInstance;
    if (!map) return;

    // Clear existing community markers
    communityMarkersRef.current.forEach((m) => m.remove());
    communityMarkersRef.current = [];

    if (!showCommunityReports || !communityReports || communityReports.length === 0) return;

    const unverifiedReports = communityReports.filter((r) => !r.is_verified);

    // Time ago helper
    const timeAgo = (dateStr: string) => {
      const diffMs = new Date().getTime() - new Date(dateStr).getTime();
      const diffMins = Math.max(0, Math.floor(diffMs / 60000));
      if (diffMins < 1) return 'Vừa xong';
      return `${diffMins} phút trước`;
    };

    if (currentZoom < 15) {
      // Clustering logic (unverified reports within 500m / 0.5km)
      const clusters: any[][] = [];
      const visited = new Set<number>();

      unverifiedReports.forEach((r1) => {
        if (visited.has(r1.id)) return;
        const cluster = [r1];
        visited.add(r1.id);

        unverifiedReports.forEach((r2) => {
          if (visited.has(r2.id)) return;
          const dist = getDistance(r1.latitude, r1.longitude, r2.latitude, r2.longitude);
          if (dist <= 0.5) { // 500m
            cluster.push(r2);
            visited.add(r2.id);
          }
        });
        clusters.push(cluster);
      });

      clusters.forEach((cluster) => {
        if (cluster.length >= 3) {
          // Render cluster marker
          const avgLat = cluster.reduce((sum, r) => sum + r.latitude, 0) / cluster.length;
          const avgLng = cluster.reduce((sum, r) => sum + r.longitude, 0) / cluster.length;

          const el = document.createElement('div');
          el.className = 'flex items-center justify-center bg-red-600/90 text-white rounded-full px-2.5 py-1 text-[11px] font-black border border-white/50 shadow-2xl animate-pulse cursor-pointer';
          el.innerHTML = `🚨 ${cluster.length} pings`;
          el.title = `Cụm ${cluster.length} phản ánh kẹt xe (Dblclick/Right-click để phóng to)`;

          // Right-click to zoom
          el.addEventListener('contextmenu', (evt) => {
            evt.preventDefault();
            map.flyTo({
              center: [avgLng, avgLat],
              zoom: 17,
              essential: true
            });
          });

          // Double-click to zoom
          el.addEventListener('dblclick', (evt) => {
            evt.stopPropagation();
            map.flyTo({
              center: [avgLng, avgLat],
              zoom: 17,
              essential: true
            });
          });

          const popupDiv = document.createElement('div');
          popupDiv.className = 'p-2 text-slate-800 text-xs min-w-[200px]';

          const pTitle = document.createElement('strong');
          pTitle.className = 'block text-red-600 font-bold mb-1';
          pTitle.innerText = `🚨 Cụm ${cluster.length} báo cáo kẹt xe`;
          popupDiv.appendChild(pTitle);

          const pDesc = document.createElement('p');
          pDesc.className = 'mb-2 text-slate-600 text-[11px]';
          pDesc.innerText = 'Phát hiện nhiều báo cáo kẹt xe từ người dân gần nhau trong phạm vi 500m.';
          popupDiv.appendChild(pDesc);

          const zoomBtn = document.createElement('button');
          zoomBtn.className = 'w-full py-1 bg-slate-800 hover:bg-slate-700 text-white rounded text-[10px] font-semibold cursor-pointer transition mb-1.5 border-0';
          zoomBtn.innerText = '🔍 Phóng to xem chi tiết';
          zoomBtn.onclick = () => {
            map.flyTo({
              center: [avgLng, avgLat],
              zoom: 16.5,
              essential: true
            });
            popup.remove();
          };
          popupDiv.appendChild(zoomBtn);

          if (isCsgtView && onVerifyCluster) {
            const verifyBtn = document.createElement('button');
            verifyBtn.className = 'w-full py-1.5 bg-red-600 hover:bg-red-500 text-white rounded text-[10px] font-bold cursor-pointer transition border-0';
            verifyBtn.innerText = '✅ Duyệt kẹt cả cụm';
            verifyBtn.onclick = () => {
              onVerifyCluster(cluster.map(r => r.id));
              popup.remove();
            };
            popupDiv.appendChild(verifyBtn);
          }

          const popup = new mapboxgl.Popup({ offset: 25 }).setDOMContent(popupDiv);

          const marker = new mapboxgl.Marker(el)
            .setLngLat([avgLng, avgLat])
            .setPopup(popup)
            .addTo(map);

          communityMarkersRef.current.push(marker);
        } else {
          // Render individual reports in the cluster
          cluster.forEach((report) => {
            const el = document.createElement('div');
            el.className = 'community-report-marker flex items-center justify-center w-7 h-7 rounded-full bg-rose-500 text-white shadow-lg border border-white/50 cursor-pointer hover:scale-110 transition-transform duration-200 text-xs font-bold';
            el.innerHTML = '📍';
            el.title = report.description || 'Báo cáo kẹt xe';

            const popupDiv = document.createElement('div');
            popupDiv.className = 'p-2 text-slate-800 text-xs min-w-[180px]';

            const pTitle = document.createElement('strong');
            pTitle.className = 'block text-amber-600 font-bold mb-1';
            pTitle.innerText = '📍 Báo cáo từ người dân';
            popupDiv.appendChild(pTitle);

            const pDesc = document.createElement('p');
            pDesc.className = 'mb-1 text-slate-600';
            pDesc.innerText = report.description || 'Kẹt xe / Ún ứ tại khu vực này.';
            popupDiv.appendChild(pDesc);

            const pMeta = document.createElement('div');
            pMeta.className = 'mt-2 pt-1 border-t border-slate-100 flex items-center justify-between text-[10px] text-slate-500 gap-2';
            pMeta.innerHTML = `
              <span>Mức: <b>${report.severity === 3 ? 'Nặng 🔴' : report.severity === 2 ? 'Vừa 🟡' : 'Nhẹ 🟢'}</b></span>
              <span>${timeAgo(report.reported_at)}</span>
            `;
            popupDiv.appendChild(pMeta);

            if (isCsgtView && onVerifyReport) {
              const verifyBtn = document.createElement('button');
              verifyBtn.className = 'mt-3 w-full py-1.5 bg-amber-600 hover:bg-amber-500 text-white rounded text-[10px] font-bold cursor-pointer transition border-0';
              verifyBtn.innerText = '✅ Duyệt kẹt xe';
              verifyBtn.onclick = () => {
                onVerifyReport(report.id);
                popup.remove();
              };
              popupDiv.appendChild(verifyBtn);
            }

            const popup = new mapboxgl.Popup({ offset: 25 }).setDOMContent(popupDiv);

            const marker = new mapboxgl.Marker(el)
              .setLngLat([report.longitude, report.latitude])
              .setPopup(popup)
              .addTo(map);

            communityMarkersRef.current.push(marker);
          });
        }
      });
    } else {
      // Render all individual reports at high zoom
      unverifiedReports.forEach((report) => {
        const el = document.createElement('div');
        el.className = 'community-report-marker flex items-center justify-center w-7 h-7 rounded-full bg-rose-500 text-white shadow-lg border border-white/50 cursor-pointer hover:scale-110 transition-transform duration-200 text-xs font-bold';
        el.innerHTML = '📍';
        el.title = report.description || 'Báo cáo kẹt xe';

        const popupDiv = document.createElement('div');
        popupDiv.className = 'p-2 text-slate-800 text-xs min-w-[180px]';

        const pTitle = document.createElement('strong');
        pTitle.className = 'block text-amber-600 font-bold mb-1';
        pTitle.innerText = '📍 Báo cáo từ người dân';
        popupDiv.appendChild(pTitle);

        const pDesc = document.createElement('p');
        pDesc.className = 'mb-1 text-slate-600';
        pDesc.innerText = report.description || 'Kẹt xe / Ún ứ tại khu vực này.';
        popupDiv.appendChild(pDesc);

        const pMeta = document.createElement('div');
        pMeta.className = 'mt-2 pt-1 border-t border-slate-100 flex items-center justify-between text-[10px] text-slate-500 gap-2';
        pMeta.innerHTML = `
          <span>Mức: <b>${report.severity === 3 ? 'Nặng 🔴' : report.severity === 2 ? 'Vừa 🟡' : 'Nhẹ 🟢'}</b></span>
          <span>${timeAgo(report.reported_at)}</span>
        `;
        popupDiv.appendChild(pMeta);

        if (isCsgtView && onVerifyReport) {
          const verifyBtn = document.createElement('button');
          verifyBtn.className = 'mt-3 w-full py-1.5 bg-amber-600 hover:bg-amber-500 text-white rounded text-[10px] font-bold cursor-pointer transition border-0';
          verifyBtn.innerText = '✅ Duyệt kẹt xe';
          verifyBtn.onclick = () => {
            onVerifyReport(report.id);
            popup.remove();
          };
          popupDiv.appendChild(verifyBtn);
        }

        const popup = new mapboxgl.Popup({ offset: 25 }).setDOMContent(popupDiv);

        const marker = new mapboxgl.Marker(el)
          .setLngLat([report.longitude, report.latitude])
          .setPopup(popup)
          .addTo(map);

        communityMarkersRef.current.push(marker);
      });
    }

    return () => {
      communityMarkersRef.current.forEach((m) => m.remove());
      communityMarkersRef.current = [];
    };
  }, [mapInstance, communityReports, showCommunityReports, currentZoom, isCsgtView, onVerifyReport, onVerifyCluster]);

  // Handle report mode cursor on canvas
  useEffect(() => {
    const map = mapInstance;
    if (!map) return;
    map.getCanvas().style.cursor = isReportMode ? 'crosshair' : '';
  }, [isReportMode, mapInstance]);

  // Snapshot UI and action handlers
  const [snapshotMenuOpen, setSnapshotMenuOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleExportPNG = () => {
    const map = mapInstanceRef.current;
    if (!map) return;
    try {
      const canvas = map.getCanvas();
      const dataUrl = canvas.toDataURL('image/png');
      const link = document.createElement('a');
      const filename = `traffic-map-snapshot-${new Date().toISOString().replace(/:/g, '-').replace(/\./g, '_')}.png`;
      link.download = filename;
      link.href = dataUrl;
      link.click();
      setSnapshotMenuOpen(false);
    } catch (err) {
      console.error(err);
      alert('Không thể xuất ảnh chụp bản đồ. Đảm bảo bản đồ đã tải xong.');
    }
  };

  const handleExportCSV = () => {
    if (!trafficState || !trafficState.streets) return;
    try {
      const data = trafficState.streets.map((s: any) => ({
        street_id: s.street_id,
        street_name: s.street_name || '',
        congestion_level: s.congestion_level ?? 0,
        avg_speed: s.avg_speed ?? 0,
        max_speed: s.max_speed ?? 0,
      }));
      const csv = Papa.unparse(data);
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      const filename = `traffic-data-snapshot-${new Date().toISOString().replace(/:/g, '-').replace(/\./g, '_')}.csv`;
      link.download = filename;
      link.href = URL.createObjectURL(blob);
      link.click();
      setSnapshotMenuOpen(false);
    } catch (err) {
      console.error(err);
      alert('Lỗi khi xuất dữ liệu CSV.');
    }
  };

  const handleImportCSV = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    Papa.parse(file, {
      header: true,
      dynamicTyping: true,
      skipEmptyLines: true,
      complete: (results) => {
        try {
          const parsed = results.data as any[];
          // Validate structure
          const valid = parsed.every(row => 'street_id' in row && 'congestion_level' in row);
          if (!valid) {
            alert('Tệp CSV không đúng định dạng. Cần có cột street_id và congestion_level.');
            return;
          }
          const mapped = parsed.map(row => ({
            street_id: Number(row.street_id),
            street_name: row.street_name || '',
            congestion_level: row.congestion_level !== undefined ? Number(row.congestion_level) : 0,
            avg_speed: row.avg_speed !== undefined ? Number(row.avg_speed) : 0,
            max_speed: row.max_speed !== undefined ? Number(row.max_speed) : 0,
          }));
          setSnapshotData(mapped);
          setSnapshotMenuOpen(false);
        } catch (err) {
          console.error(err);
          alert('Lỗi phân tích cú pháp tệp CSV.');
        }
      },
      error: (err) => {
        console.error(err);
        alert('Không thể đọc tệp CSV.');
      }
    });
    e.target.value = '';
  };

  if (!mapboxToken) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-gray-100 text-red-500 font-semibold p-4 text-center">
        Lỗi: Chưa cấu hình VITE_MAPBOX_TOKEN trong tệp .env.
      </div>
    );
  }

  if (geomError || stateError) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-gray-100 text-red-500 font-semibold p-4 text-center">
        Lỗi tải dữ liệu giao thông từ máy chủ. Vui lòng kiểm tra lại backend.
      </div>
    );
  }

  return (
    <div className="relative w-full h-full">
      <div ref={mapRef} className="w-full h-full" />
      {mapInstance && children && children(mapInstance)}
      {(isGeomLoading || isStateLoading) && (
        <div className="absolute inset-0 bg-white/70 flex items-center justify-center z-50">
          <div className="flex flex-col items-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mb-3"></div>
            <p className="text-gray-600 font-medium">Đang tải bản đồ Đà Nẵng...</p>
          </div>
        </div>
      )}

      {/* Snapshot Active Warning Banner */}
      {snapshotData && (
        <div className="absolute top-20 left-1/2 -translate-x-1/2 z-[40] w-fit max-w-[90%] bg-amber-950/90 backdrop-blur-md border border-amber-500/30 rounded-xl px-4 py-2 flex items-center gap-3 text-xs text-white animate-slide-in-down shadow-2xl">
          <span className="text-sm">⚠️</span>
          <div>
            <strong className="block text-amber-400 font-bold">Chế độ Xem Snapshot</strong>
            <span className="text-[10px] text-amber-200/80">Đang hiển thị dữ liệu trạng thái từ tệp CSV đã nhập.</span>
          </div>
          <button
            onClick={() => setSnapshotData(null)}
            className="ml-2 bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold px-2 py-1 rounded text-[10px] transition cursor-pointer"
          >
            Khôi phục thực tế
          </button>
        </div>
      )}

      {/* Map Control Buttons Stack (2D/3D, Snapshot, Traffic Lines Toggle) */}
      {mapInstance && (
        <>
          {/* Helper function to get top offsets based on pageContext and hasActiveAlert */}
          {(() => {
            const getTopOffset = (baseHome: number, baseOther: number) => {
              if (pageContext === 'home') {
                return hasActiveAlert ? `${baseHome + 36}px` : `${baseHome}px`;
              }
              return `${baseOther}px`;
            };

            return (
              <>
                {/* 1. 2D/3D Toggle Button */}
                <button
                  id="btn-3d-toggle"
                  onClick={() => setLocalIs3D(!localIs3D)}
                  style={{ top: getTopOffset(208, 16) }}
                  className={`absolute left-4 z-30 w-11 h-11 flex items-center justify-center rounded-full backdrop-blur-sm border shadow-lg transition-all duration-300 cursor-pointer ${
                    localIs3D
                      ? 'bg-indigo-600 hover:bg-indigo-500 border-indigo-500 text-white shadow-indigo-500/20'
                      : 'bg-slate-900/80 hover:bg-slate-800/80 border-white/10 text-slate-200 hover:text-white'
                  }`}
                  title={localIs3D ? 'Chuyển sang bản đồ 2D' : 'Chuyển sang bản đồ 3D'}
                >
                  {localIs3D ? <Layers size={20} /> : <Box size={20} />}
                </button>

                {/* 2. Snapshot floating menu */}
                <div
                  style={{ top: getTopOffset(336, 80) }}
                  className="absolute left-4 z-30 flex flex-col items-start"
                >
                  <button
                    id="btn-snapshot-menu"
                    onClick={() => setSnapshotMenuOpen(!snapshotMenuOpen)}
                    className="w-11 h-11 flex items-center justify-center rounded-full bg-slate-900/80 hover:bg-slate-800/80 text-slate-200 hover:text-white backdrop-blur-sm border border-white/10 shadow-lg transition-all duration-300 cursor-pointer"
                    title="Quản lý Snapshots"
                  >
                    <Camera size={20} />
                  </button>

                  {snapshotMenuOpen && (
                    <div className="absolute left-14 top-0 bg-slate-950/95 border border-white/10 rounded-xl shadow-2xl p-2 flex flex-col gap-1 w-48 backdrop-blur-md animate-slide-in-right">
                      <button
                        onClick={handleExportPNG}
                        className="w-full text-left px-3 py-2 text-xs font-semibold hover:bg-white/5 rounded-lg text-slate-200 hover:text-white transition flex items-center gap-2 cursor-pointer"
                      >
                        <span>🖼️</span> Xuất ảnh bản đồ (PNG)
                      </button>
                      <button
                        onClick={handleExportCSV}
                        className="w-full text-left px-3 py-2 text-xs font-semibold hover:bg-white/5 rounded-lg text-slate-200 hover:text-white transition flex items-center gap-2 cursor-pointer"
                      >
                        <span>📤</span> Xuất dữ liệu CSV
                      </button>
                      <button
                        onClick={() => fileInputRef.current?.click()}
                        className="w-full text-left px-3 py-2 text-xs font-semibold hover:bg-white/5 rounded-lg text-slate-200 hover:text-white transition flex items-center gap-2 cursor-pointer"
                      >
                        <span>📥</span> Nhập dữ liệu CSV
                      </button>
                      <input
                        type="file"
                        ref={fileInputRef}
                        onChange={handleImportCSV}
                        accept=".csv"
                        className="hidden"
                      />
                    </div>
                  )}
                </div>

                {/* 3. Traffic Lines Toggle Button (New 7th Button) */}
                <button
                  id="btn-traffic-toggle"
                  onClick={() => setLocalHideTraffic(!localHideTraffic)}
                  style={{ top: getTopOffset(400, 144) }}
                  className={`absolute left-4 z-30 w-11 h-11 flex items-center justify-center rounded-full backdrop-blur-sm border shadow-lg transition-all duration-300 cursor-pointer ${
                    localHideTraffic
                      ? 'bg-amber-600 hover:bg-amber-500 border-amber-500 text-white shadow-amber-500/20'
                      : 'bg-slate-900/80 hover:bg-slate-800/80 border-white/10 text-slate-200 hover:text-white'
                  }`}
                  title={localHideTraffic ? 'Bật chế độ hiển thị làn đường kẹt xe' : 'Tắt chế độ hiển thị làn đường kẹt xe'}
                >
                  {localHideTraffic ? <EyeOff size={20} /> : <Eye size={20} />}
                </button>
              </>
            );
          })()}
        </>
      )}
    </div>
  );
};

export default TrafficMap;
