import React, { useEffect, useRef, useState } from 'react';
import mapboxgl from 'mapbox-gl';
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

interface PredictionItem {
  street_id: number;
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
  children,
}) => {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<mapboxgl.Map | null>(null);
  const [mapInstance, setMapInstance] = useState<mapboxgl.Map | null>(null);

  const onStreetClickRef = useRef(onStreetClick);
  const isReportModeRef = useRef(isReportMode);
  const onReportClickRef = useRef(onReportClick);

  useEffect(() => {
    onStreetClickRef.current = onStreetClick;
    isReportModeRef.current = isReportMode;
    onReportClickRef.current = onReportClick;
  }, [onStreetClick, isReportMode, onReportClick]);

  const { data: geometry, isLoading: isGeomLoading, error: geomError } = useGeometry();
  const { data: trafficState, isLoading: isStateLoading, error: stateError } = useTrafficData();

  // 1. Initialize Map
  useEffect(() => {
    if (!mapRef.current || mapInstanceRef.current || !mapboxToken) return;

    const map = new mapboxgl.Map({
      container: mapRef.current,
      style: 'mapbox://styles/mapbox/light-v11',
      center: DA_NANG_CENTER,
      zoom: DEFAULT_ZOOM,
    });

    map.addControl(new mapboxgl.NavigationControl({ showCompass: false }), 'bottom-right');
    map.addControl(new mapboxgl.GeolocateControl({
      positionOptions: { enableHighAccuracy: true },
      trackUserLocation: true,
    }), 'bottom-right');

    mapInstanceRef.current = map;
    setMapInstance(map);

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
      const maxSpeed = props.max_speed !== null && props.max_speed !== undefined ? `${props.max_speed} km/h` : 'N/A';
      const level = props.congestion_level;
      const timeStr = props.timestamp ? fmtTimestampVN(props.timestamp) : 'N/A';

      const popupContent = `
        <div class="p-1">
          <h4 class="font-bold text-base text-gray-900 border-b pb-1 mb-2">${name}</h4>
          <p class="text-sm text-gray-600 mb-1"><b>Quận:</b> ${district}</p>
          <p class="text-sm text-gray-600 mb-1"><b>Trạng thái:</b> <span class="font-semibold">${getCongestionLabel(level)}</span></p>
          <p class="text-sm text-gray-600 mb-1"><b>Tốc độ TB:</b> ${speed} (Tối đa: ${maxSpeed})</p>
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
            predMap.set(p.street_id, p.predicted_level);
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
              hideTrafficLines ? 'none' : 'visible'
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
              'visibility': hideTrafficLines ? 'none' : 'visible'
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
  }, [geometry, trafficState, isPredictionMode, predictionData, hideTrafficLines, districtId, congestionLevel, searchQuery]);


  // Apply layer visibility based on hideTrafficLines prop
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    const updateVisibility = () => {
      if (map.getLayer('traffic-lines')) {
        map.setLayoutProperty(
          'traffic-lines',
          'visibility',
          hideTrafficLines ? 'none' : 'visible'
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
  }, [hideTrafficLines, mapInstance]);

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
      el.className = 'incident-marker flex items-center justify-center w-8 h-8 rounded-full bg-slate-900/90 backdrop-blur-md border border-white/20 shadow-xl cursor-pointer text-sm hover:scale-110 transition-transform duration-200';
      
      let emoji = '⚠️';
      if (incident.type === 'accident') emoji = '🚗💥';
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
            <span>Trạng thái: <b>${incident.status === 'dispatched' ? 'Đã điều động 🚔' : 'Đang xảy ra ⚠️'}</b></span>
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

  // Handle report mode cursor on canvas
  useEffect(() => {
    const map = mapInstance;
    if (!map) return;
    map.getCanvas().style.cursor = isReportMode ? 'crosshair' : '';
  }, [isReportMode, mapInstance]);


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
    </div>
  );
};

export default TrafficMap;
