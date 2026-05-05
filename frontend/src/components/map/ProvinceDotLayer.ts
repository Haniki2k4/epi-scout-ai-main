import { GeoJsonLayer, ScatterplotLayer } from '@deck.gl/layers';
import type { Layer } from '@deck.gl/core';
import { mapLocationToGeo } from '../../utils/location-mapper';

export interface MappedLocation {
  name: string;
  lng: number;
  lat: number;
  cases: number;
  mentions: number;
  riskScore: number;
  diseases: { disease_name: string; mentions: number }[];
}

export function prepareLocationData(rawData: any[]): MappedLocation[] {
  const rs: MappedLocation[] = [];
  for (const item of rawData) {
    const geo = mapLocationToGeo(item.location);
    if (geo) {
      rs.push({
        name: geo.name,
        lng: geo.lng,
        lat: geo.lat,
        cases: item.total_cases || 0,
        mentions: item.total_mentions || 0,
        riskScore: item.risk_score || (item.total_mentions || 0),
        diseases: item.diseases || []
      });
    }
  }
  return rs;
}

/**
 * Tạo danh sách các layer bao gồm: đường viền toàn tỉnh và 3 lớp Scatterplot đồng tâm
 */
export function createProvinceDotLayers(
  geoJson: any,
  data: MappedLocation[],
  maxRiskScore: number,
  onHoverFunc?: (info: any) => void
): Layer[] {
  const layers: Layer[] = [];

  // 1. Layer đường viền 34 cụm tỉnh thành
  if (geoJson) {
    layers.push(
      new GeoJsonLayer({
        id: 'province-borders',
        data: geoJson,
        filled: false,
        stroked: true,
        getLineColor: [150, 150, 150, 100],
        lineWidthMinPixels: 1,
        pickable: false,
      })
    );
  }

  // Nếu không có data thì chỉ trả về viền
  if (data.length === 0) return layers;

  // Tính max value để scale kích thước. Tránh chia cho 0
  const maxM = Math.max(maxRiskScore, 1);

  // 2. Layer Vành đai (Outer Ring) - Lan toả nhạt và rộng nhất
  layers.push(
    new ScatterplotLayer<MappedLocation>({
      id: 'epicenter-outer',
      data,
      getPosition: d => [d.lng, d.lat],
      getFillColor: [239, 68, 68, 40], // Đỏ mờ (Tailwind đỏ 500)
      getRadius: d => {
        const ratio = d.riskScore / maxM;
        // Bán kính cơ sở 8000m + phình ra tối đa 40000m tùy mức độ
        return 8000 + ratio * 40000;
      },
      radiusMinPixels: 10,
      radiusMaxPixels: 60,
      pickable: true,
      onHover: onHoverFunc,
    })
  );

  // 3. Layer Vòng đệm (Mid Ring)
  layers.push(
    new ScatterplotLayer<MappedLocation>({
      id: 'epicenter-mid',
      data,
      getPosition: d => [d.lng, d.lat],
      getFillColor: [239, 68, 68, 100],
      getRadius: d => {
        const ratio = d.riskScore / maxM;
        return 4000 + ratio * 20000;
      },
      radiusMinPixels: 5,
      radiusMaxPixels: 35,
      pickable: false, // Để lớp ngoài cùng handle hover là đủ
    })
  );

  // 4. Layer Lõi (Core Ring) - Nhỏ và rực nhất
  layers.push(
    new ScatterplotLayer<MappedLocation>({
      id: 'epicenter-core',
      data,
      getPosition: d => [d.lng, d.lat],
      getFillColor: [220, 38, 38, 220],
      getRadius: d => {
        const ratio = d.riskScore / maxM;
        return 2000 + ratio * 10000;
      },
      radiusMinPixels: 3,
      radiusMaxPixels: 15,
      pickable: false,
    })
  );

  return layers;
}
