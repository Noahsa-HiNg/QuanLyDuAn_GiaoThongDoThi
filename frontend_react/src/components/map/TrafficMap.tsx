import React, { useEffect, useRef, useState } from 'react';
import mapboxgl from 'mapbox-gl';
import { DA_NANG_CENTER, DEFAULT_ZOOM } from '../../constants/map.constants';
import { useGeometry } from '../../hooks/useGeometry';
import { useTrafficData } from '../../hooks/useTrafficData';
import { buildGeoJSON } from '../../utils/buildGeoJSON';
import { getCongestionLabel } from '../../utils/congestionColor';
import { fmtTimestampVN, normalizeVN } from '../../utils/formatters';

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
  children?: (map: mapboxgl.Map) => React.ReactNode;
}

const TrafficMap: React.FC<TrafficMapProps> = ({
  districtId = null,
  congestionLevel = null,
  searchQuery = '',
  isPredictionMode = false,
  predictionData = null,
  children,
}) => {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<mapboxgl.Map | null>(null);
  const [mapInstance, setMapInstance] = useState<mapboxgl.Map | null>(null);

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

    // Click handler for popup
    map.on('click', 'traffic-lines', (e) => {
      if (!e.features || e.features.length === 0) return;
      const feat = e.features[0];
      const props = feat.properties;
      if (!props) return;

      const name = props.name || 'Không rõ tên đường';
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

    // Hover effect pointer
    map.on('mouseenter', 'traffic-lines', () => {
      map.getCanvas().style.cursor = 'pointer';
    });
    map.on('mouseleave', 'traffic-lines', () => {
      map.getCanvas().style.cursor = '';
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
      const geojson = buildGeoJSON(geometry, trafficState);

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

      const source = map.getSource('traffic');
      if (source) {
        (source as mapboxgl.GeoJSONSource).setData(geojson);
      } else {
        map.addSource('traffic', {
          type: 'geojson',
          data: geojson,
        });

        map.addLayer({
          id: 'traffic-lines',
          type: 'line',
          source: 'traffic',
          layout: { 'line-join': 'round', 'line-cap': 'round' },
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
    };

    if (map.isStyleLoaded()) {
      updateSource();
    } else {
      map.once('style.load', updateSource);
    }
  }, [geometry, trafficState, isPredictionMode, predictionData]);

  // 3. Apply Filters Dynamically
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    const applyFilters = () => {
      if (!map.getLayer('traffic-lines')) return;

      const filters: any[] = ['all'];

      if (districtId !== null) {
        const districtNames: Record<number, string> = {
          1: 'Quận Hải Châu',
          2: 'Quận Thanh Khê',
          3: 'Quận Sơn Trà',
          4: 'Quận Ngũ Hành Sơn',
          5: 'Quận Liên Chiểu',
          6: 'Huyện Hòa Vang',
          7: 'Quận Cẩm Lệ',
        };
        const selectedName = districtNames[districtId];
        if (selectedName) {
          filters.push(['==', ['get', 'district'], selectedName]);
        }
      }

      if (congestionLevel !== null) {
        filters.push(['==', ['get', 'congestion_level'], congestionLevel]);
      }

      if (searchQuery.trim() !== '') {
        const normalizedQuery = normalizeVN(searchQuery);
        // Note: Mapbox client side doesn't do complex string functions, but we can filter by checking includes
        // Or we can normalize the query here and use lower-case check if supported
        // Mapbox supports 'downcase' and 'in'
        filters.push(['in', normalizedQuery, ['downcase', ['get', 'name']]]);
      }

      map.setFilter('traffic-lines', filters.length > 1 ? filters : null);
    };

    if (map.isStyleLoaded()) {
      applyFilters();
    } else {
      map.once('style.load', applyFilters);
    }
  }, [districtId, congestionLevel, searchQuery, isPredictionMode, predictionData]);

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
