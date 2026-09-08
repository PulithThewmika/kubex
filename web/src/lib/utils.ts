// shadcn-style class name helper. Dependency-free: the project doesn't pull
// clsx/tailwind-merge, and a filtered join covers every current use.
export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ')
}
