/** Capitalises the plan name. */
export function capitalisePlanName(name: string): string {
  return name.charAt(0).toUpperCase() + name.slice(1);
}

export function totalWithTax(subtotal: number, taxRate: number): number {
  return subtotal * (1 + taxRate);
}
