/**
 * TypeScript utilities for LiveDoc demo.
 */

export function add(a: number, b: number): number {
  return a + b;
}

export function subtract(a: number, b: number): number {
  return a - b;
}

export const multiply = (x: number, y: number): number => x * y;

export class Calculator {
  divide(a: number, b: number): number {
    return a / b;
  }
}

export default function createCalculator(): Calculator {
  return new Calculator();
}
