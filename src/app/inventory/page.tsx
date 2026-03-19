"use client";

import { useState, useEffect } from "react";
import { DecimalStepper } from "../../components/ui/decimal-stepper";
import { supabase } from "../../lib/supabase";

export default function RCSDashboard() {
  const [stock, setStock] = useState<number>(0.0);
  const [loading, setLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  // 1. 起動時にDBから 'ハリオ V60 01' (id: 53) の在庫データを取得
  useEffect(() => {
    async function fetchInitialStock() {
      const { data, error } = await supabase
        .from('inventory')
        .select('current_stock')
        .eq('id', 53)
        .single();

      if (data) {
        setStock(data.current_stock);
      }
      setLoading(false);
    }
    fetchInitialStock();
  }, []);

  // 2. 保存ボタン押下時にDBを更新
  const handleSave = async () => {
    setIsSaving(true);
    const { error } = await supabase
      .from('inventory')
      .update({ 
        current_stock: stock,
        updated_at: new Date() 
      })
      .eq('id', 53);

    if (error) {
      alert("保存に失敗しました: " + error.message);
    } else {
      alert(`成功！在庫が ${stock}kg に更新されました。`);
    }
    setIsSaving(false);
  };

  if (loading) return <div className="p-10 text-center text-slate-500 font-bold italic text-lg">データを読み込み中...</div>;

  return (
    <div className="p-6 max-w-md mx-auto bg-white rounded-xl shadow-lg mt-10 border border-slate-200">
      <h1 className="text-xl font-bold text-slate-800 text-center mb-6 font-sans">
        RCS 在庫管理システム
      </h1>

      <div className="bg-slate-50 p-6 rounded-lg mb-6 border border-dashed border-slate-300">
        <label className="block text-sm font-medium text-slate-600 mb-4 text-center">
          在庫量の調整 (0.5単位)
        </label>
        <div className="flex justify-center">
          <DecimalStepper value={stock} onChange={setStock} min={0} max={100} />
        </div>
      </div>

      <div className="space-y-4">
        <div className="flex justify-between text-sm py-2 border-b">
          <span className="text-slate-500 font-medium font-sans">選択中の項目</span>
          <span className="text-slate-800 font-bold font-sans text-lg">ハリオ V60 01</span>
        </div>
        <div className="flex justify-between text-sm py-2 border-b">
          <span className="text-slate-500 font-medium font-sans">確定在庫数</span>
          <span className="font-mono font-bold text-blue-600 text-xl">{stock.toFixed(1)} kg</span>
        </div>
        
        <button
          onClick={handleSave}
          disabled={isSaving}
          className="w-full py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-bold text-lg shadow-md transition-all active:scale-95 disabled:opacity-50"
        >
          {isSaving ? "データを送信中..." : "RCSシステムに保存"}
        </button>
      </div>

      <p className="mt-4 text-[10px] text-gray-400 text-center">
        ※ボタンを長押しすると、数値を素早く調整できます。
      </p>
    </div>
  );
}
