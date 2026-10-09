import { useState } from "react";
import { Check, ChevronDown, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

const MAX_DISEASES = 20;

export default function DiseaseMultiSelect({ options, value, onChange }: {
  options: string[];
  value: string[];
  onChange: (diseases: string[]) => void;
}) {
  const [search, setSearch] = useState("");
  const query = search.trim();
  const selected = new Set(value.map((name) => name.toLocaleLowerCase("vi-VN")));
  const filtered = options.filter((name) => name.toLocaleLowerCase("vi-VN").includes(query.toLocaleLowerCase("vi-VN"))).slice(0, 80);
  const canAdd = query.length > 0 && query.length <= 255 && !selected.has(query.toLocaleLowerCase("vi-VN")) && value.length < MAX_DISEASES;
  const hasExactOption = options.some((name) => name.toLocaleLowerCase("vi-VN") === query.toLocaleLowerCase("vi-VN"));

  const toggle = (name: string) => {
    const key = name.toLocaleLowerCase("vi-VN");
    onChange(selected.has(key) ? value.filter((item) => item.toLocaleLowerCase("vi-VN") !== key) : [...value, name]);
  };

  return <div className="space-y-2">
    <Popover>
      <PopoverTrigger asChild>
        <Button type="button" variant="outline" className="w-full justify-between text-left" aria-label="Chọn nhiều bệnh đúng">
          {value.length ? `Đã chọn ${value.length} bệnh` : "Chọn bệnh đúng"}
          <ChevronDown className="h-4 w-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[min(92vw,360px)] space-y-2 p-3">
        <Input value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => {
          if (event.key === "Enter" && canAdd && !hasExactOption) {
            event.preventDefault();
            onChange([...value, query]);
            setSearch("");
          }
        }} placeholder="Tìm hoặc nhập bệnh khác..." aria-label="Tìm bệnh" />
        <div className="max-h-60 space-y-1 overflow-y-auto" role="group" aria-label="Danh sách bệnh">
          {filtered.map((name) => <button key={name} type="button" onClick={() => toggle(name)}
            disabled={!selected.has(name.toLocaleLowerCase("vi-VN")) && value.length >= MAX_DISEASES}
            aria-pressed={selected.has(name.toLocaleLowerCase("vi-VN"))}
            className="flex w-full items-center justify-between rounded-md px-2 py-2 text-left text-sm hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50">
            <span>{name}</span>{selected.has(name.toLocaleLowerCase("vi-VN")) && <Check className="h-4 w-4 text-primary" />}
          </button>)}
          {filtered.length === 0 && <p className="px-2 py-3 text-sm text-muted-foreground">Không thấy trong danh sách gợi ý.</p>}
        </div>
        {canAdd && !hasExactOption && <Button type="button" size="sm" variant="secondary" className="w-full" onClick={() => { onChange([...value, query]); setSearch(""); }}>Thêm “{query}”</Button>}
        <p className="text-xs text-muted-foreground">Gợi ý từ danh sách từ khóa. Có thể thêm bệnh chưa có; tối đa {MAX_DISEASES} bệnh.</p>
      </PopoverContent>
    </Popover>
    {value.length > 0 && <div className="flex flex-wrap gap-2" aria-label="Bệnh đã chọn">
      {value.map((name) => <Badge key={name} variant="secondary" className="gap-1 py-1 text-sm">{name}
        <button type="button" onClick={() => toggle(name)} aria-label={`Bỏ bệnh ${name}`} className="rounded-full hover:text-destructive focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"><X className="h-3.5 w-3.5" /></button>
      </Badge>)}
    </div>}
  </div>;
}

