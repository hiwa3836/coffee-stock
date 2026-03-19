"use client";

import { useState, useEffect } from "react";
import { DecimalStepper } from "../../components/ui/decimal-stepper";

export default function RCSDashboard() {
  const [stock, setStock] = useState<number>(0.0);
  const [loading, setLoading] = useState(false);

  // 나중에 Supabase에서 데이터를 가져오는 로직이 들어갈 자리입니다.
  const handleSave = async () => {
    setLoading(true);
    // TODO: Supabase 업데이트 로직
    console.log("저장된 수량:", stock);
    setTimeout(() => setLoading(false), 500); // 저장 시뮬레이션
    alert(`재고 ${stock}kg이 RCS 시스템에 저장되었습니다.`);
  };

  return (
    <div className="p-6 max-w-md mx-auto bg-white rounded-xl shadow-lg mt-10 border border-slate-200">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-slate-800 text-center flex-1">
          RCS 재고 관리 시스템
        </h1>
      </div>

      <div className="bg-slate-50 p-6 rounded-lg mb-6 border border-dashed border-slate-300">
        <label className="block text-sm font-medium text-slate-600 mb-4 text-center">
          현재 재고량 조절 (0.5단위)
        </label>
        <div className="flex justify-center">
          <DecimalStepper value={stock} onChange={setStock} min={0} max={100} />
        </div>
      </div>

      <div className="space-y-4">
        <div className="flex justify-between text-sm py-2 border-b">
          <span className="text-slate-500">최종 확정 수량</span>
          <span className="font-mono font-bold text-blue-600">{stock.toFixed(1)} kg</span>
        </div>
        
        <button
          onClick={handleSave}
          disabled={loading}
          className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-bold transition-all active:scale-95 disabled:opacity-50"
        >
          {loading ? "저장 중..." : "RCS 시스템에 반영하기"}
        </button>
      </div>
    </div>
  );
}
