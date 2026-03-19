"use client";

import * as React from "react";
import { Minus, Plus } from "lucide-react";
import { Button } from "@/components/ui/button"; 
import { Input } from "@/components/ui/input";
import { useLongPress } from "@/hooks/use-long-press";

interface DecimalStepperProps {
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
}

export function DecimalStepper({ value, onChange, min = 0, max = 100 }: DecimalStepperProps) {
  const [inputValue, setInputValue] = React.useState(value.toFixed(1));

  React.useEffect(() => {
    setInputValue(value.toFixed(1));
  }, [value]);

  const updateValue = (val: number) => {
    const fixed = Math.round(Math.max(min, Math.min(max, val)) * 10) / 10;
    onChange(fixed);
  };

  const incrementProps = useLongPress(() => updateValue(value + 0.5));
  const decrementProps = useLongPress(() => updateValue(value - 0.5));

  return (
    <div className="flex items-center gap-2">
      <Button variant="outline" size="icon" {...decrementProps} className="select-none touch-manipulation">
        <Minus className="h-4 w-4" />
      </Button>
      <Input
        type="text"
        inputMode="decimal"
        pattern="[0-9\.]*"
        className="w-20 text-center"
        value={inputValue}
        onChange={(e) => {
          if (/^-?\d*\.?\d{0,1}$/.test(e.target.value)) {
            setInputValue(e.target.value);
            const p = parseFloat(e.target.value);
            if (!isNaN(p)) updateValue(p);
          }
        }}
        onBlur={() => setInputValue(value.toFixed(1))}
      />
      <Button variant="outline" size="icon" {...incrementProps} className="select-none touch-manipulation">
        <Plus className="h-4 w-4" />
      </Button>
    </div>
  );
}
