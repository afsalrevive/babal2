import { iconMap, type IconName } from '@/utils/iconMap'
import type { Component } from 'vue' 


export function normalize(name: string): string {
  const result = name.toLowerCase()
  return result
}

export function hasPermission(
  perms: string[],
  resource: string,
  operation: 'read' | 'write' | 'modify' | 'full'
): boolean {
  const base = resource.toLowerCase();
  const hasFull = perms.includes(`${base}.full`);
  const hasModify = hasFull || perms.includes(`${base}.modify`);
  const hasWrite = hasModify || perms.includes(`${base}.write`);
  const hasRead = hasWrite || perms.includes(`${base}.read`);
  const hasNone = perms.includes(`${base}.none`);

  if (hasNone) return false;

  switch (operation) {
    case 'full':
      return hasFull;
    case 'modify':
      return hasModify;
    case 'write':
      return hasWrite;
    case 'read':
      return hasRead;
    default:
      return false;
  }
}

export function getIcon(resource: string): Component {
  const baseKey = normalize(resource)
  
  // Type-safe check
const iconKey = Object.keys(iconMap).find(k => 
    k.toLowerCase() === baseKey
  ) as IconName | undefined

  return iconKey ? iconMap[iconKey] : iconMap.default
}
