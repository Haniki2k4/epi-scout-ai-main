export interface ProvinceCoordinate {
  name: string;
  lng: number;
  lat: number;
  aliases: string[];
}

// Tọa độ Centroid theo Box Center cho 34 cụm địa danh trong vn_map_lite.geojson
// Danh sách alias được lấy trực tiếp từ thuộc tính "sap_nhap" của bản đồ
const PROVINCE_MAP: ProvinceCoordinate[] = [
  { name: 'An Giang', lng: 104.516, lat: 10.108, aliases: ['An Giang', 'Kiên Giang'] },
  { name: 'Bắc Ninh', lng: 106.457, lat: 21.298, aliases: ['Bắc Ninh', 'Bắc Giang'] },
  { name: 'Cà Mau', lng: 105.191, lat: 9.025, aliases: ['Cà Mau', 'Bạc Liêu'] },
  { name: 'Cần Thơ', lng: 105.762, lat: 9.785, aliases: ['Cần Thơ', 'Sóc Trăng', 'Hậu Giang'] },
  { name: 'Cao Bằng', lng: 106.052, lat: 22.738, aliases: ['Cao Bằng'] },
  { name: 'Đà Nẵng', lng: 108.202, lat: 15.8, aliases: ['Đà Nẵng', 'Quảng Nam'] },
  { name: 'Đắk Lắk', lng: 108.472, lat: 12.928, aliases: ['Đắk Lắk', 'Phú Yên', 'Dak Lak'] },
  { name: 'Điện Biên', lng: 103.018, lat: 21.39, aliases: ['Điện Biên'] },
  { name: 'Đồng Nai', lng: 107.0, lat: 11.439, aliases: ['Đồng Nai', 'Bình Phước'] },
  { name: 'Đồng Tháp', lng: 105.998, lat: 10.554, aliases: ['Tiền Giang', 'Đồng Tháp'] },
  { name: 'Gia Lai', lng: 108.407, lat: 13.85, aliases: ['Gia Lai', 'Bình Định'] },
  { name: 'Hà Nội', lng: 105.85, lat: 21.028, aliases: ['Hà Nội', 'Hanoi'] },
  { name: 'Hà Tĩnh', lng: 105.807, lat: 18.34, aliases: ['Hà Tĩnh'] },
  { name: 'Hải Phòng', lng: 106.68, lat: 20.85, aliases: ['Hải Dương', 'Hải Phòng'] },
  { name: 'Huế', lng: 107.615, lat: 16.369, aliases: ['Huế', 'Thừa Thiên Huế', 'Thừa Thiên - Huế'] },
  { name: 'Hưng Yên', lng: 106.276, lat: 20.628, aliases: ['Hưng Yên', 'Thái Bình'] },
  { name: 'Khánh Hòa', lng: 109.19, lat: 12.25, aliases: ['Khánh Hòa', 'Ninh Thuận'] }, // tinh chỉnh
  { name: 'Lai Châu', lng: 103.153, lat: 22.248, aliases: ['Lai Châu'] },
  { name: 'Lâm Đồng', lng: 108.146, lat: 11.391, aliases: ['Lâm Đồng', 'Đắk Nông', 'Bình Thuận', 'Dak Nong'] },
  { name: 'Lạng Sơn', lng: 106.73, lat: 21.893, aliases: ['Lạng Sơn'] },
  { name: 'Lào Cai', lng: 104.316, lat: 22.085, aliases: ['Lào Cai', 'Yên Bái'] },
  { name: 'Nghệ An', lng: 104.932, lat: 19.275, aliases: ['Nghệ An'] },
  { name: 'Ninh Bình', lng: 106.07, lat: 20.286, aliases: ['Hà Nam', 'Ninh Bình', 'Nam Định'] },
  { name: 'Phú Thọ', lng: 105.336, lat: 21.012, aliases: ['Vĩnh Phúc', 'Phú Thọ', 'Hòa Bình'] },
  { name: 'Quảng Ngãi', lng: 108.24, lat: 14.678, aliases: ['Quảng Ngãi', 'Kon Tum'] },
  { name: 'Quảng Ninh', lng: 107.266, lat: 21.19, aliases: ['Quảng Ninh'] },
  { name: 'Quảng Trị', lng: 106.499, lat: 17.195, aliases: ['Quảng Trị', 'Quảng Bình'] },
  { name: 'Sơn La', lng: 104.122, lat: 21.302, aliases: ['Sơn La'] },
  { name: 'Tây Ninh', lng: 106.124, lat: 11.089, aliases: ['Tây Ninh', 'Long An'] },
  { name: 'Thái Nguyên', lng: 105.839, lat: 22.034, aliases: ['Bắc Kạn', 'Thái Nguyên', 'Bac Kan'] },
  { name: 'Thanh Hóa', lng: 105.225, lat: 19.979, aliases: ['Thanh Hóa'] },
  { name: 'TP. Hồ Chí Minh', lng: 106.69, lat: 10.776, aliases: ['Thành phố Hồ Chí Minh', 'Hồ Chí Minh', 'TPHCM', 'TP. Hồ Chí Minh', 'TP HCM', 'Sài Gòn', 'Bà Rịa - Vũng Tàu', 'Bà Rịa Vũng Tàu', 'Vũng Tàu', 'Bình Dương'] }, // Tinh chỉnh
  { name: 'Tuyên Quang', lng: 104.967, lat: 22.445, aliases: ['Tuyên Quang', 'Hà Giang'] },
  { name: 'Vĩnh Long', lng: 106.237, lat: 9.934, aliases: ['Vĩnh Long', 'Bến Tre', 'Trà Vinh'] }
];

/**
 * Tiền xử lý, chuẩn hoá tên Tỉnh (Cắt chữ Tỉnh, TP, chuyển về chữ thường)
 */
export function normalizeProvinceName(rawName: string): string {
  if (!rawName) return '';
  let name = rawName.toLowerCase().trim();
  // Bỏ các tiền tố
  const prefixesToRemove = ['tỉnh ', 'thành phố ', 'tp ', 'tp. ', 'tx ', 'tx. '];
  for (const prefix of prefixesToRemove) {
    if (name.startsWith(prefix)) {
      name = name.replace(prefix, '').trim();
      break;
    }
  }
  return name;
}

/**
 * Map tên dịa danh thô từ Backend sang 34 Tỉnh hợp lệ trong vn_map_lite.geojson
 * Trả về Data nếu khớp đúng hoặc undefined nếu không thuộc bản map
 */
export function mapLocationToGeo(rawName: string): ProvinceCoordinate | undefined {
  const normalized = normalizeProvinceName(rawName);

  for (const province of PROVINCE_MAP) {
    // So khớp trực tiếp với name hoặc aliases (cũng cần chuẩn hóa alias)
    if (normalizeProvinceName(province.name) === normalized) {
      return province;
    }

    for (const alias of province.aliases) {
      if (normalizeProvinceName(alias) === normalized) {
        return province;
      }
    }
  }

  return undefined;
}
