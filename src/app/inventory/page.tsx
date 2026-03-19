"use client";

import { useState } from "react";
// @ 경로 대신 상대 경로../../를 사용하여 경로 오류 방지
import { DecimalStepper } from "../../components/ui/decimal-stepper";

export default function InventoryPage() {
  const [stock, setStock] = useState<number>(1.5);

  return (
    <div className="p-10 flex flex-col items-center justify-center min-h-screen gap-6 bg-gray-50">
      <div className="bg-white p-8 rounded-2xl shadow-xl border border-gray-200">
        <h1 className="text-xl font-bold mb-6 text-gray-800 text-center">재고 수량 설정</h1>
        
        <DecimalStepper 
          value={stock} 
          onChange={setStock} 
          min={0} 
          max={100} 
        />
        
        <div className="mt-6 pt-6 border-t border-gray-100 text-center">
          <p className="text-sm text-gray-500">현재 확정된 수량</p>
          <p className="text-3xl font-black text-blue-600">{stock} <span className="text-lg">kg</span></p>
        </div>
      </div>
      
      <p className="text-xs text-gray-400 font-medium">
        TIP: +/- 버튼을 길게 누르면 빠르게 조절됩니다.
      </p>
    </div>
  );
}
