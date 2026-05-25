export interface ProvinceCoordinate {
  name: string;
  lng: number;
  lat: number;
  aliases: string[];
}

const PROVINCE_MAP: ProvinceCoordinate[] = [
  { name: 'An Giang', lng: 104.516, lat: 10.108, aliases: ['An Giang', 'Kiên Giang', 'Long Xuyên', 'Rạch Giá', 'Phú Quốc', 'Hà Tiên', 'Châu Đốc'] },
  { name: 'Bắc Ninh', lng: 106.457, lat: 21.298, aliases: ['Bắc Ninh', 'Bắc Giang'] },
  { name: 'Cà Mau', lng: 105.191, lat: 9.025, aliases: ['Cà Mau', 'Bạc Liêu'] },
  { name: 'Cần Thơ', lng: 105.762, lat: 9.785, aliases: ['Cần Thơ', 'Sóc Trăng', 'Hậu Giang', 'Tây Đô'] },
  { name: 'Cao Bằng', lng: 106.052, lat: 22.738, aliases: ['Cao Bằng'] },
  { name: 'Đà Nẵng', lng: 108.202, lat: 15.800, aliases: ['Đà Nẵng', 'Da Nang', 'Quảng Nam', 'Hội An'] },
  { name: 'Đắk Lắk', lng: 108.472, lat: 12.928, aliases: ['Đắk Lắk', 'Dak Lak', 'Daklak', 'Phú Yên', 'Buôn Ma Thuột'] },
  { name: 'Điện Biên', lng: 103.018, lat: 21.390, aliases: ['Điện Biên', 'Điện Biên Phủ', 'Dien Bien'] },
  { name: 'Đồng Nai', lng: 107.000, lat: 11.439, aliases: ['Đồng Nai', 'Bình Phước', 'Biên Hòa'] },
  { name: 'Đồng Tháp', lng: 105.998, lat: 10.554, aliases: ['Đồng Tháp', 'Tiền Giang', 'Mỹ Tho', 'Cao Lãnh', 'Sa Đéc'] },
  { name: 'Gia Lai', lng: 108.407, lat: 13.850, aliases: ['Gia Lai', 'Bình Định', 'Quy Nhơn', 'Pleiku'] },
  { name: 'Hà Nội', lng: 105.850, lat: 21.028, aliases: ['Hà Nội', 'Hanoi'] },
  { name: 'Hà Tĩnh', lng: 105.807, lat: 18.340, aliases: ['Hà Tĩnh'] },
  { name: 'Hải Phòng', lng: 106.680, lat: 20.850, aliases: ['Hải Phòng', 'Hải Dương', 'Hai Phong'] },
  { name: 'Thừa Thiên Huế', lng: 107.615, lat: 16.369, aliases: ['Huế', 'Thừa Thiên Huế', 'Thừa Thiên - Huế', 'Thừa Thiên–Huế', 'Hue'] },
  { name: 'Hưng Yên', lng: 106.276, lat: 20.628, aliases: ['Hưng Yên', 'Thái Bình'] },
  { name: 'Khánh Hòa', lng: 109.190, lat: 12.250, aliases: ['Khánh Hòa', 'Ninh Thuận', 'Nha Trang', 'Cam Ranh', 'Phan Rang'] },
  { name: 'Lai Châu', lng: 103.153, lat: 22.248, aliases: ['Lai Châu'] },
  { name: 'Lâm Đồng', lng: 108.146, lat: 11.391, aliases: ['Lâm Đồng', 'Đắk Nông', 'Dak Nong', 'Bình Thuận', 'Phan Thiết', 'Đà Lạt', 'Bảo Lộc'] },
  { name: 'Lạng Sơn', lng: 106.730, lat: 21.893, aliases: ['Lạng Sơn'] },
  { name: 'Lào Cai', lng: 104.316, lat: 22.085, aliases: ['Lào Cai', 'Yên Bái', 'Sa Pa'] },
  { name: 'Nghệ An', lng: 104.932, lat: 19.275, aliases: ['Nghệ An', 'Vinh'] },
  { name: 'Ninh Bình', lng: 106.070, lat: 20.286, aliases: ['Ninh Bình', 'Hà Nam', 'Nam Định'] },
  { name: 'Phú Thọ', lng: 105.336, lat: 21.012, aliases: ['Phú Thọ', 'Vĩnh Phúc', 'Vĩnh Yên', 'Hoà Bình', 'Hòa Bình', 'Hoa Binh', 'Việt Trì'] },
  { name: 'Quảng Ngãi', lng: 108.240, lat: 14.678, aliases: ['Quảng Ngãi', 'Kon Tum', 'Kontum'] },
  { name: 'Quảng Ninh', lng: 107.266, lat: 21.190, aliases: ['Quảng Ninh', 'Hạ Long'] },
  { name: 'Quảng Trị', lng: 106.499, lat: 17.195, aliases: ['Quảng Trị', 'Quảng Bình', 'Đồng Hới', 'Đông Hà'] },
  { name: 'Sơn La', lng: 104.122, lat: 21.302, aliases: ['Sơn La'] },
  { name: 'Tây Ninh', lng: 106.124, lat: 11.089, aliases: ['Tây Ninh', 'Long An'] },
  { name: 'Thái Nguyên', lng: 105.839, lat: 22.034, aliases: ['Thái Nguyên', 'Bắc Kạn', 'Bac Kan'] },
  { name: 'Thanh Hóa', lng: 105.225, lat: 19.979, aliases: ['Thanh Hóa'] },
  { name: 'Hồ Chí Minh', lng: 106.690, lat: 10.776, aliases: ['Hồ Chí Minh', 'TP. Hồ Chí Minh', 'TP Hồ Chí Minh', 'Thành phố Hồ Chí Minh', 'TPHCM', 'TP.HCM', 'TP HCM', 'Sài Gòn', 'Saigon', 'Ho Chi Minh', 'Bà Rịa - Vũng Tàu', 'Bà Rịa Vũng Tàu', 'Vũng Tàu', 'Bình Dương', 'Thủ Dầu Một', 'Dĩ An'] },
  { name: 'Tuyên Quang', lng: 104.967, lat: 22.445, aliases: ['Tuyên Quang', 'Hà Giang'] },
  { name: 'Vĩnh Long', lng: 106.237, lat: 9.934, aliases: ['Vĩnh Long', 'Bến Tre', 'Trà Vinh'] },
];

export function normalizeProvinceName(rawName: string): string {
  if (!rawName) return '';
  let name = rawName.toLowerCase().trim();
  const prefixesToRemove = ['tỉnh ', 'thành phố ', 'tp ', 'tp. ', 'tx ', 'tx. ', 'thị xã ', 'huyện ', 'quận ', 'phường ', 'xã ', 'thị trấn '];
  for (const prefix of prefixesToRemove) {
    if (name.startsWith(prefix)) {
      name = name.slice(prefix.length).trim();
      break;
    }
  }
  return name;
}

export function mapLocationToGeo(rawName: string): ProvinceCoordinate | undefined {
  const normalized = normalizeProvinceName(rawName);

  for (const province of PROVINCE_MAP) {
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
