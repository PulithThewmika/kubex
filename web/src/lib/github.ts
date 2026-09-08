// The GitHub App's slug is a separate identity from this repo's name (set at
// app registration, not touched by EPIC-025's DeployLens -> KubeX rename) —
// override via VITE_GITHUB_APP_SLUG if the registered app isn't "kubex-dev".
export const GITHUB_APP_SLUG = import.meta.env.VITE_GITHUB_APP_SLUG ?? 'kubex-dev'
export const GITHUB_APP_INSTALL_URL = `https://github.com/apps/${GITHUB_APP_SLUG}/installations/new`
