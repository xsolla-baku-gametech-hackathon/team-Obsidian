export function money(value: number | null, currency: string | null): string {
  if (value === null || !currency) return 'Unavailable';
  return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(value / 100);
}

export function prettyPlan(plan: string | null): string {
  return plan ? plan[0].toUpperCase() + plan.slice(1) : 'No plan selected';
}

export function prettyRole(role: string | null): string {
  if (role === 'game_developer') return 'Game developer';
  if (role === 'content_creator') return 'Content creator';
  return 'Choose role';
}

export function formatDate(value: string): string {
  return new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}
