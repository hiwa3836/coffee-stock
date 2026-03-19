import { useState } from "react";
import { DecimalStepper } from "@/components/ui/decimal-stepper";

export default function InventoryEdit() {
  const [stock, setStock] = useState(1.5); // 초기값 1.5

  return (
    <div>
      <label>재고 수량 (kg)</label>
      <DecimalStepper 
        value={stock} 
        onChange={setStock} 
        min={0} 
        max={50} 
      />
    </div>
  );
}
