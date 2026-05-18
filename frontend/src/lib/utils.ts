import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const isDomestic = (link: string | null | undefined, source: string | null | undefined) => {
  if (!link && !source) return true;
  const tLink = (link || "").toLowerCase();
  const tSource = (source || "").toLowerCase();
  
  // Các dấu hiệu nguồn quốc tế
  if (tLink.includes('who.int') || tLink.includes('cdc.gov') || tSource.includes('who ') || tSource.includes('reuters') || tSource.includes('promed') || tSource.includes('global') || tLink.includes('nytimes') || tLink.includes('bbc.co')) {
    return false;
  }
  
  // Các dấu hiệu nguồn trong nước
  if (tLink.includes('.vn') || tSource.includes('vnexpress') || tSource.includes('tuổi trẻ') || tSource.includes('dân trí') || tSource.includes('sức khỏe') || tSource.includes('thanh niên')) {
    return true;
  }
  
  // Mặc định
  return true; 
};
