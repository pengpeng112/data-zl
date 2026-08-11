export interface PermissionProfile {
  permissions?: string[];
  roles?: string[];
}

/** Match the dot/colon permission-code contract used by the API. */
export function permissionCodeMatches(granted: string, requested: string): boolean {
  const normalize = (value: string) => value.replace(/[./]/g, ":");
  const actual = normalize(granted);
  const expected = normalize(requested);
  if (!actual || !expected) return false;
  // Keep the client no broader than backend _permission_matches: only exact
  // normalized codes and the three global wildcard forms are accepted.
  return actual === expected || ["*", "*:*", "*:*:*"].includes(actual);
}

export function hasUserPermission(
  requested: string,
  profile: PermissionProfile | null | undefined
): boolean {
  const roles = profile?.roles ?? [];
  if (roles.some(role => ["admin", "platform_admin", "super_admin"].includes(role))) {
    return true;
  }
  return (profile?.permissions ?? []).some(granted =>
    permissionCodeMatches(granted, requested)
  );
}

export function hasUserPermissions(
  requested: string | string[],
  profile: PermissionProfile | null | undefined
): boolean {
  return typeof requested === "string"
    ? hasUserPermission(requested, profile)
    : requested.length > 0 && requested.every(code => hasUserPermission(code, profile));
}
