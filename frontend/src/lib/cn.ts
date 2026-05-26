/**
 * Canonical home of the `cn()` class-merge helper.
 * See ui-prototype.md §8.3 (folder structure).
 */

import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
