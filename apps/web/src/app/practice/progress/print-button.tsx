"use client";

import { Button } from "@/components/button";
import { PracticeIcon } from "@/components/practice-ui";

export function PrintButton() {
  return (
    <Button variant="secondary" onClick={() => window.print()} className="print:hidden">
      <PracticeIcon name="printer" size={18} />
      Print or save as PDF
    </Button>
  );
}
