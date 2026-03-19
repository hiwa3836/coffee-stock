"use client";

import { useState } from "react";
// 생성하신 컴포넌트를 불러옵니다. 경로가 정확해야 합니다.
import { DecimalStepper } from "@/components/ui/decimal-stepper";

export default function InventoryPage() {
  const [stock, setStock] = useState<number>(1.5);

  return (
    <div className="p-10 flex flex-col items-center justify-center min-h-screen gap-6">
      <h1 className="text-2xl font-bold">커피 재고 관리</h1>
      
      <div className="bg-slate-50 p-6 rounded-lg border shadow-sm">
        <p className="text-sm text-slate-500 mb-2 text-center">현재 재고 (kg)</p>
        <DecimalStepper 
          value={stock} 
          onChange={setStock} 
          min={0} 
          max={100} 
        />
        <div className="mt-4 text-center font-mono text-lg">
          최종 수량: <span className="text-blue-600 font-bold">{stock}</span> kg
        </div>
      </div>

      <p className="text-xs text-slate-400">
        (+/- 버튼을 꾹 누르면 0.5씩 빠르게 변경됩니다)
      </p>
    </div>
  );
}
