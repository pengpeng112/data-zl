export function parseInfectiousSyncItemCodes(input: string): string[] {
  return [...new Set(input.split(/[\s,，;；]+/).map(code => code.trim()).filter(Boolean))];
}
